#!/usr/bin/env python3
"""Publish verified release assets. Run only from the serialized trusted workflow."""
import base64
import gzip
import hashlib
import json
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


def build_indexes(root):
    binary = root / 'dists/stable/main/binary-amd64'
    binary.mkdir(parents=True, exist_ok=True)
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


def main():
    required = ['GH_TOKEN', 'GH_REPO', 'RELEASE_TAG', 'AWS_ACCESS_KEY_ID',
                'AWS_SECRET_ACCESS_KEY', 'R2_ACCOUNT_ID', 'R2_BUCKET_NAME',
                'APT_REPOSITORY_URL', 'APT_SIGNING_KEY_B64']
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError('Missing required secrets/variables: ' + ', '.join(missing))
    tag = os.environ['RELEASE_TAG']
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
        raise ValueError('stable requires an official numeric release tag')
    release = json.loads(run('gh', 'api', f'repos/{os.environ["GH_REPO"]}/releases/tags/{tag}'))
    if release['draft'] or release['prerelease']:
        raise ValueError('Drafts and prereleases cannot publish to stable')
    version = run('bash', str(PROJECT / 'packaging/release-version.sh'), tag, text=True).strip()
    endpoint = os.environ.get('R2_ENDPOINT_URL') or f'https://{os.environ["R2_ACCOUNT_ID"]}.r2.cloudflarestorage.com'
    bucket = os.environ['R2_BUCKET_NAME']
    aws = ['aws', '--endpoint-url', endpoint, '--region', 'auto']
    with tempfile.TemporaryDirectory(prefix='ptos-apt-') as temporary:
        temp = Path(temporary)
        assets = temp / 'assets'
        assets.mkdir()
        run('gh', 'release', 'download', tag, '--repo', os.environ['GH_REPO'],
            '--pattern', '*.deb', '--pattern', 'SHA256SUMS', '--dir', str(assets))
        files = verify_assets(assets, version)
        root = temp / 'repository'
        pool = root / 'pool/main'
        pool.mkdir(parents=True)
        # A failed list/download is fatal, never interpreted as an empty archive.
        subprocess.run([*aws, 's3', 'sync', f's3://{bucket}/pool/', str(root / 'pool')], check=True)
        merge(pool, files)
        build_indexes(root)
        home = temp / 'gnupg'
        home.mkdir(mode=0o700)
        try:
            sign(root, home)
            # All immutable data precedes the mutable indexes and signed metadata.
            for path in sorted(root.rglob('*')):
                if path.is_file() and ('pool' in path.relative_to(root).parts or 'by-hash' in path.parts):
                    key = path.relative_to(root).as_posix()
                    content_type = 'application/vnd.debian.binary-package' if key.endswith('.deb') else 'application/octet-stream'
                    subprocess.run([*aws, 's3', 'cp', str(path), f's3://{bucket}/{key}',
                                    '--content-type', content_type, '--cache-control', 'public,max-age=31536000,immutable'], check=True)
            ordered = ['ptos-archive-keyring.gpg', 'dists/stable/main/binary-amd64/Packages',
                       'dists/stable/main/binary-amd64/Packages.gz', 'dists/stable/Release',
                       'dists/stable/Release.gpg', 'dists/stable/InRelease']
            for key in ordered:
                content_type = ('application/pgp-keys' if key.endswith('.gpg') and key.startswith('ptos-')
                                else 'application/gzip' if key.endswith('.gz') else 'text/plain')
                subprocess.run([*aws, 's3', 'cp', str(root / key), f's3://{bucket}/{key}',
                                '--content-type', content_type, '--cache-control',
                                'public,max-age=300' if key.startswith('ptos-') else 'no-store'], check=True)
            # Verify bytes, signatures and every newly published package via HTTPS.
            public = temp / 'public'
            public.mkdir()
            for key in ordered + [p.relative_to(root).as_posix() for p in
                                  (root / 'dists/stable/main/binary-amd64/by-hash/SHA256').iterdir()] + [f'pool/main/{p.name}' for p in files]:
                destination = public / Path(key).name
                url = os.environ['APT_REPOSITORY_URL'].rstrip('/') + '/' + key
                run('curl', '--fail', '--silent', '--show-error', '--retry', '5', '--head', url)
                run('curl', '--fail', '--silent', '--show-error', '--retry', '5', url, '-o', str(destination))
                if digest(destination) != digest(root / key):
                    raise ValueError(f'Public HTTPS content mismatch: {key}')
            # A real GET warms the package cache; subsequent GETs must show
            # that Cloudflare caches the otherwise non-default .deb extension.
            url = os.environ['APT_REPOSITORY_URL'].rstrip('/') + '/pool/main/' + files[0].name
            headers = temp / 'cache-headers'
            for attempt in range(3):
                run('curl', '--fail', '--silent', '--show-error', '--dump-header', str(headers),
                    '--output', '/dev/null', url)
                if re.search(r'^cf-cache-status:\s*HIT\s*$', headers.read_text(), re.I | re.M):
                    break
            else:
                raise ValueError('Package GETs did not achieve a Cloudflare CDN cache HIT')
            run('gpgv', '--keyring', str(public / 'ptos-archive-keyring.gpg'), str(public / 'InRelease'))
            run('gpgv', '--keyring', str(public / 'ptos-archive-keyring.gpg'),
                str(public / 'Release.gpg'), str(public / 'Release'))
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'all'], check=False)
    print(f'Published and verified {tag} via HTTPS')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'APT publication failed: {error}')
