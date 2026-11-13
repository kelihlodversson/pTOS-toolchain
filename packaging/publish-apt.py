#!/usr/bin/env python3
"""Publish verified release assets. Run only from the serialized trusted workflow."""
import base64
import gzip
from functools import cmp_to_key
import time
import urllib.error
import urllib.request
import hashlib
import json
import io
import zipfile
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGES = {'ptos-sdk-m68k', 'ptos-sdk-arm', 'ptos-sdk-x86-64'}
PROJECT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.check_output(args, **kwargs)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(path):
    values = run('dpkg-deb', '-f', str(path), 'Package', 'Version', 'Architecture', text=True)
    fields = dict(line.split(': ', 1) for line in values.splitlines())
    result = tuple(fields[k] for k in ('Package', 'Version', 'Architecture'))
    name, version, arch = result
    if name not in PACKAGES or arch != 'amd64':
        raise ValueError(f'Unexpected package identity: {result}')
    if path.name != f'{name}_{version}_{arch}.deb':
        raise ValueError(f'Noncanonical package filename: {path.name}')
    return result


def verify_assets(directory, version):
    checksums = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', line)
        if not match or match[2] in checksums:
            raise ValueError('Invalid or duplicate SHA256SUMS entry')
        checksums[match[2]] = match[1]
    files = sorted(directory.glob('*.deb'))
    if len(files) != 3:
        raise ValueError('Expected exactly three Debian assets')
    identities = set()
    for path in files:
        if checksums.get(path.name) != digest(path):
            raise ValueError(f'Checksum mismatch or missing checksum: {path.name}')
        name, actual, arch = identity(path)
        if actual != version:
            raise ValueError(f'Expected version {version}, got {actual}')
        identities.add(name)
    if identities != PACKAGES:
        raise ValueError('Release must contain all three SDKs')
    return files


def merge(pool, assets):
    pool.mkdir(parents=True, exist_ok=True)
    for source in assets:
        destination = pool / source.name
        if destination.exists() and digest(destination) != digest(source):
            raise ValueError(f'Immutable package conflict: {source.name}')
        if not destination.exists():
            shutil.copyfile(source, destination)
    seen = set()
    for path in sorted(pool.glob('*.deb')):
        key = identity(path)
        if key in seen:
            raise ValueError(f'Duplicate package identity: {key}')
        seen.add(key)


def build_indexes(root, contents=None):
    binary = root / 'dists/stable/main/binary-amd64'
    binary.mkdir(parents=True, exist_ok=True)
    if contents is None:
        contents = run('dpkg-scanpackages', '--multiversion', 'pool', '/dev/null', cwd=root)
    (binary / 'Packages').write_bytes(contents)
    (binary / 'Packages.gz').write_bytes(gzip.compress(contents, mtime=0))
    hashes = binary / 'by-hash/SHA256'
    hashes.mkdir(parents=True, exist_ok=True)
    for name in ('Packages', 'Packages.gz'):
        source = binary / name
        shutil.copyfile(source, hashes / digest(source))
    options = {'Origin': 'pTOS', 'Label': 'pTOS SDK', 'Suite': 'stable',
               'Codename': 'stable', 'Architectures': 'amd64', 'Components': 'main',
               'Description': 'pTOS cross-development SDK', 'Acquire-By-Hash': 'yes'}
    args = [item for k, v in options.items() for item in ('-o', f'APT::FTPArchive::Release::{k}={v}')]
    # Generate from a clean staging directory so stale signatures/Release files
    # are never included in the checksums of the new Release.
    release = run('apt-ftparchive', *args, 'release', 'dists/stable', cwd=root)
    for name in ('Packages', 'Packages.gz'):
        source = binary / name
        if digest(source).encode() not in release:
            raise ValueError(f'Release is missing SHA256 for {name}')
    (root / 'dists/stable/Release').write_bytes(release)


def sign(root, home):
    env = dict(os.environ, GNUPGHOME=str(home))
    key = base64.b64decode(os.environ['APT_SIGNING_KEY_B64'], validate=True)
    subprocess.run(['gpg', '--batch', '--import'], input=key, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    listing = run('gpg', '--batch', '--with-colons', '--list-secret-keys', env=env, text=True)
    fingerprints = [line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')]
    if not fingerprints:
        raise ValueError('Signing secret contains no private key')
    fingerprint = fingerprints[0]
    keyring = root / 'ptos-archive-keyring.gpg'
    keyring.write_bytes(run('gpg', '--batch', '--export', fingerprint, env=env))
    release = root / 'dists/stable/Release'
    for output, mode in [('InRelease', '--clearsign'), ('Release.gpg', '--detach-sign')]:
        # Passphrase goes through stdin, never argv or logs.
        subprocess.run(['gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
                        '--passphrase-fd', '0', '--local-user', fingerprint,
                        '--digest-algo', 'SHA256', '--output', str(release.parent / output),
                        mode, str(release)], input=(os.environ.get('APT_SIGNING_KEY_PASSPHRASE', '') + '\n').encode(),
                       env=env, check=True)
    for args in [('InRelease',), ('Release.gpg', 'Release')]:
        subprocess.run(['gpgv', '--keyring', str(keyring),
                        *(str(release.parent / p) for p in args)], check=True, env=env)


BINARY = 'dists/stable/main/binary-amd64'
DEFAULT_LIMIT = 800 * 1024 * 1024


def stable_releases(releases):
    """Sort complete, official SDK releases by Debian version, not creation date."""
    result = []
    versions = set()
    for release in releases:
        tag = release['tag_name']
        if release['draft'] or release['prerelease'] or not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
            continue
        version = run('bash', str(PROJECT / 'packaging/release-version.sh'), tag, text=True).strip()
        names = {asset['name'] for asset in release['assets']}
        expected = {f'{name}_{version}_amd64.deb' for name in PACKAGES} | {'SHA256SUMS'}
        if not expected <= names:
            continue  # Another release build may still be uploading assets.
        if version in versions:
            raise ValueError(f'Multiple release tags have Debian version {version}')
        versions.add(version)
        result.append(dict(release, version=version))

    def compare(a, b):
        return -1 if subprocess.run(['dpkg', '--compare-versions', a['version'], 'gt', b['version']]).returncode == 0 else 1
    return sorted(result, key=cmp_to_key(compare))


def enforce_size(root, limit):
    size = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size > limit:
        raise ValueError(f'Pages deployment is {size} bytes, above configured limit {limit}')
    return size


def select_releases(releases, count, budget, pinned):
    """Keep newest versions, plus grace-period packages; never evict pinned data."""
    if count < 1 or budget < 1 or budget > DEFAULT_LIMIT:
        raise ValueError('Retention count must be positive; size limit must be 1..800 MiB')
    selected = []
    names = set(pinned)
    size = sum(pinned.values())
    for release in releases[:count]:
        assets = [a for a in release['assets'] if a['name'].endswith('.deb')]
        added = sum(a['size'] for a in assets if a['name'] not in names)
        if size + added > budget:
            if not selected:
                raise ValueError('Newest release and propagation-grace packages exceed Pages size budget')
            break
        selected.append(release)
        names.update(a['name'] for a in assets)
        size += added
    if not selected:
        raise ValueError('No complete official stable SDK releases available')
    return selected


def remember(ledger, name, sha256):
    if name in ledger and ledger[name] != sha256:
        raise ValueError(f'Immutable package conflict: {name}')
    ledger[name] = sha256


def write_pages_root(root):
    (root / '.nojekyll').touch()
    (root / 'CNAME').write_text('apt.ptos.dev\n')
    (root / 'index.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>pTOS SDK APT repository</title>'
        '<h1>pTOS SDK APT repository</h1><p>Ubuntu 24.04+, amd64 hosts.</p>'
        '<p><a href="ptos-archive-keyring.gpg">Archive signing key</a> · '
        '<a href="https://github.com/kelihlodversson/pTOS-toolchain#install-the-sdk-with-apt-ubuntu-2404-amd64">'
        'Installation instructions</a></p>'
        '<pre>deb [arch=amd64 signed-by=/usr/share/keyrings/ptos-archive-keyring.gpg] '
        'https://apt.ptos.dev stable main</pre></html>\n')


def fetch(url, destination):
    request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'pTOS-APT-publisher'})
    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open('wb') as output:
            shutil.copyfileobj(response, output)


def deployed_state_digest(repo):
    """Authenticated deployment manifest prevents a stale Pages state rollback.

    Only consider artifacts whose Pages deployment job actually succeeded; a
    failed public smoke test does not mean the deployment was rolled back.
    """
    pages = json.loads(run('gh', 'api', '--paginate', '--slurp',
                          f'repos/{repo}/actions/artifacts?name=apt-verification&per_page=100'))
    for artifact in (a for page in pages for a in page['artifacts']):
        if artifact['expired']:
            continue
        workflow_run = json.loads(run('gh', 'api', f'repos/{repo}/actions/runs/{artifact["workflow_run"]["id"]}'))
        if workflow_run['event'] not in ('release', 'workflow_dispatch') or workflow_run['path'] not in (
                '.github/workflows/publish-apt.yml', '.github/workflows/release-deb.yml'):
            continue
        jobs = json.loads(run('gh', 'api', '--paginate', '--slurp',
                              f'repos/{repo}/actions/runs/{artifact["workflow_run"]["id"]}/jobs?per_page=100'))
        if not any(j['conclusion'] == 'success' and
                   (j['name'] == 'deploy' or j['name'].endswith(' / deploy'))
                   for page in jobs for j in page['jobs']):
            continue
        archive = run('gh', 'api', artifact['archive_download_url'])
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            return json.loads(zipped.read('apt-verification.json'))['apt-state.json']
    return None


def previous_state(temp, keyring, url, bootstrap):
    expected = deployed_state_digest(os.environ['GH_REPO'])
    if bootstrap:
        # Do not require a certificate before the first Pages deployment. Prove
        # through GitHub that this environment has never been deployed instead.
        pages = json.loads(run('gh', 'api', '--paginate', '--slurp',
                              f'repos/{os.environ["GH_REPO"]}/deployments?environment=github-pages&per_page=100'))
        for deployment in (d for page in pages for d in page):
            statuses = json.loads(run('gh', 'api', deployment['statuses_url']))
            if any(s['state'] in ('success', 'inactive') for s in statuses):
                raise ValueError('Bootstrap refused: github-pages has a previous deployment')
        if expected:
            raise ValueError('Bootstrap refused: previous Pages verification manifest exists')
        return {'ledger': {}, 'snapshots': []}
    state = temp / 'previous.json'
    signature = temp / 'previous.sig'
    deadline = time.monotonic() + 1200
    while True:
        try:
            suffix = '?generation=' + str(time.time_ns())
            fetch(url + '/apt-state.json' + suffix, state)
            fetch(url + '/apt-state.json.gpg' + suffix, signature)
            if expected and digest(state) != expected:
                raise ValueError('Previous Pages state has not propagated')
            run('gpgv', '--keyring', str(keyring), str(signature), str(state))
            return json.loads(state.read_text())
        except (urllib.error.URLError, ValueError, subprocess.CalledProcessError):
            if time.monotonic() >= deadline:
                raise ValueError('Cannot verify previous Pages state; restore public state before retrying')
            print('Waiting for the previous signed Pages state to propagate', flush=True)
            time.sleep(15)


def retained_snapshots(state, now, grace):
    if grace < 86400:
        raise ValueError('Propagation grace must be at least 24 hours')
    snapshots = [s for s in state['snapshots'] if s['last_active'] + grace >= now]
    # The most recent snapshot is still live, even after months without releases.
    if state['snapshots']:
        current = state['snapshots'][-1]
        current = dict(current, last_active=now)
        snapshots = [s for s in snapshots if s['id'] != current['id']] + [current]
    return snapshots


def restore_history(root, snapshots):
    hashes = root / BINARY / 'by-hash/SHA256'
    hashes.mkdir(parents=True, exist_ok=True)
    for snapshot in snapshots:
        for sha256, encoded in snapshot['indexes'].items():
            value = base64.b64decode(encoded, validate=True)
            if hashlib.sha256(value).hexdigest() != sha256:
                raise ValueError('Invalid historical by-hash content')
            (hashes / sha256).write_bytes(value)


def validate_index_references(root):
    for paragraph in (root / BINARY / 'Packages').read_text().strip().split('\n\n'):
        if not paragraph:
            continue
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
        relative = Path(fields['Filename'])
        if relative.is_absolute() or '..' in relative.parts or relative.parent != Path('pool/main'):
            raise ValueError('Unsafe package index reference')
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(fields['Size']) or digest(path) != fields['SHA256']:
            raise ValueError(f'Index references missing or incorrect package: {relative}')


def main():
    required = ['GH_TOKEN', 'GH_REPO', 'RELEASE_TAG', 'APT_SIGNING_KEY_B64']
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError('Missing required secrets/variables: ' + ', '.join(missing))
    url = os.environ.get('APT_REPOSITORY_URL', 'https://apt.ptos.dev').rstrip('/')
    tag = os.environ['RELEASE_TAG']
    pages = json.loads(run('gh', 'api', '--paginate', '--slurp',
                           f'repos/{os.environ["GH_REPO"]}/releases?per_page=100'))
    releases = stable_releases([release for page in pages for release in page])
    if tag not in {r['tag_name'] for r in releases}:
        raise ValueError('Requested release must be official, stable and contain complete SDK assets')
    count = int(os.environ.get('APT_RETAIN_VERSIONS', '3'))
    limit = int(os.environ.get('APT_MAX_BYTES', str(DEFAULT_LIMIT)))
    grace = int(os.environ.get('APT_GRACE_SECONDS', '172800'))
    root = Path(os.environ.get('APT_STAGING_DIR', '_apt-site')).resolve()
    if root.exists():
        raise ValueError('Staging directory must not already exist')
    root.mkdir()
    with tempfile.TemporaryDirectory(prefix='ptos-apt-') as temporary:
        temp = Path(temporary)
        home = temp / 'gnupg'
        home.mkdir(mode=0o700)
        try:
            # Import/export the trusted key before reading previous signed state.
            env = dict(os.environ, GNUPGHOME=str(home))
            subprocess.run(['gpg', '--batch', '--import'], input=base64.b64decode(os.environ['APT_SIGNING_KEY_B64'], validate=True),
                           env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            trusted = temp / 'trusted.gpg'
            trusted.write_bytes(run('gpg', '--batch', '--export', env=env))
            state = previous_state(temp, trusted, url, os.environ.get('APT_BOOTSTRAP') == 'true')
            now = int(time.time())
            snapshots = retained_snapshots(state, now, grace)
            pinned = {name: entry['size'] for s in snapshots for name, entry in s['packages'].items()}
            # Reserve 8 MiB for signatures, manifests and retained indexes.
            selected = select_releases(releases, count, limit - 8 * 1024 * 1024, pinned)
            if tag not in {r['tag_name'] for r in selected}:
                raise ValueError('Requested release is outside retention; dispatch a retained release tag')
            needed_tags = {r['tag_name'] for r in selected} | {e['tag'] for s in snapshots for e in s['packages'].values()}
            ledger = state['ledger'].copy()
            entries = {}
            for release_tag in sorted(needed_tags):
                release = next((r for r in releases if r['tag_name'] == release_tag), None)
                if release is None:
                    raise ValueError(f'Previously published release is missing or no longer official: {release_tag}')
                assets = temp / release_tag
                assets.mkdir()
                run('gh', 'release', 'download', release_tag, '--repo', os.environ['GH_REPO'],
                    '--pattern', '*.deb', '--pattern', 'SHA256SUMS', '--dir', str(assets))
                files = verify_assets(assets, release['version'])
                for path in files:
                    remember(ledger, path.name, digest(path))
                    entries[path.name] = {'tag': release_tag, 'size': path.stat().st_size, 'sha256': digest(path)}
                merge(root / 'pool/main', files)
            # Current indexes contain retained versions only; grace-period
            # objects remain in the deployment for old by-hash clients.
            selected_names = {a['name'] for r in selected for a in r['assets'] if a['name'].endswith('.deb')}
            index_root = temp / 'current'
            (index_root / 'pool/main').mkdir(parents=True)
            for name in selected_names:
                os.link(root / 'pool/main' / name, index_root / 'pool/main' / name)
            contents = run('dpkg-scanpackages', '--multiversion', 'pool', '/dev/null', cwd=index_root)
            restore_history(root, snapshots)
            build_indexes(root, contents)
            validate_index_references(root)
            binary = root / BINARY
            indexes = {digest(binary / name): base64.b64encode((binary / name).read_bytes()).decode()
                       for name in ('Packages', 'Packages.gz')}
            snapshot = {'id': digest(binary / 'Packages'), 'last_active': now, 'indexes': indexes,
                        'packages': {name: entries[name] for name in selected_names}}
            snapshots = [s for s in snapshots if s['id'] != snapshot['id']] + [snapshot]
            (root / 'apt-state.json').write_text(json.dumps({'ledger': ledger, 'snapshots': snapshots}, sort_keys=True))
            write_pages_root(root)
            sign(root, home)
            subprocess.run(['gpg', '--batch', '--yes', '--pinentry-mode', 'loopback', '--passphrase-fd', '0',
                            '--output', str(root / 'apt-state.json.gpg'), '--detach-sign', str(root / 'apt-state.json')],
                           input=(os.environ.get('APT_SIGNING_KEY_PASSPHRASE', '') + '\n').encode(), env=env, check=True)
            run('gpgv', '--keyring', str(root / 'ptos-archive-keyring.gpg'),
                str(root / 'apt-state.json.gpg'), str(root / 'apt-state.json'))
            size = enforce_size(root, limit)
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'all'], check=False)
    print(f'Generated signed Pages deployment: {size} bytes; {len(selected)} stable versions')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, urllib.error.URLError) as error:
        sys.exit(f'APT generation failed: {error}')
