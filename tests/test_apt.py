#!/usr/bin/env python3
"""Real .deb/index/signature tests without compiler builds or production secrets."""
import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publish_apt', PROJECT / 'packaging/publish-apt.py')
apt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apt)


class AptRepository(unittest.TestCase):
    def package(self, root, name, version, payload='hello'):
        stage = root / 'stage'
        (stage / 'DEBIAN').mkdir(parents=True, exist_ok=True)
        (stage / 'DEBIAN').chmod(0o755)
        (stage / 'DEBIAN/control').write_text(
            f'Package: {name}\nVersion: {version}\nArchitecture: amd64\n'
            'Maintainer: Test <test@example.org>\nDescription: test SDK\n')
        (stage / 'payload').write_text(payload)
        out = root / f'{name}_{version}_amd64.deb'
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(stage), str(out)],
                       check=True, stdout=subprocess.DEVNULL)
        return out

    def test_versions_conflicts_checksums_and_by_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / 'assets'
            assets.mkdir()
            files = [self.package(assets, name, '0.1.0') for name in sorted(apt.PACKAGES)]
            checksums = assets / 'SHA256SUMS'
            checksums.write_text(''.join(f'{apt.digest(p)}  {p.name}\n' for p in files))
            apt.verify_assets(assets, '0.1.0')
            with self.assertRaisesRegex(ValueError, 'Expected version'):
                apt.verify_assets(assets, '0.2.0')
            checksums.write_text(''.join(f'{"0" * 64}  {p.name}\n' for p in files))
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                apt.verify_assets(assets, '0.1.0')
            repository = root / 'repo'
            pool = repository / 'pool/main'
            apt.merge(pool, files)
            apt.merge(pool, files)  # Exact rerun is harmless.
            newer = self.package(assets, 'ptos-sdk-arm', '0.2.0')
            apt.merge(pool, [newer])
            conflict = self.package(assets, 'ptos-sdk-arm', '0.1.0', 'different bytes')
            with self.assertRaisesRegex(ValueError, 'Immutable package conflict'):
                apt.merge(pool, [conflict])
            apt.build_indexes(repository)
            binary = repository / 'dists/stable/main/binary-amd64'
            text = (binary / 'Packages').read_text()
            self.assertEqual(text.count('Package: '), 4)
            self.assertIn('Filename: pool/main/ptos-sdk-arm_0.1.0_amd64.deb', text)
            self.assertIn('Version: 0.2.0', text)
            for name in ['Packages', 'Packages.gz']:
                self.assertEqual((binary / name).read_bytes(),
                                 (binary / 'by-hash/SHA256' / apt.digest(binary / name)).read_bytes())
            release = (repository / 'dists/stable/Release').read_text()
            for line in ['Origin: pTOS', 'Label: pTOS SDK', 'Suite: stable',
                         'Codename: stable', 'Architectures: amd64', 'Components: main',
                         'Acquire-By-Hash: yes', 'Description: pTOS cross-development SDK']:
                self.assertIn(line, release)

    def test_real_signatures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generation = root / 'generation'
            generation.mkdir(mode=0o700)
            env = dict(os.environ, GNUPGHOME=str(generation))
            try:
                subprocess.run(['gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                                '--quick-generate-key', 'Test APT <apt@example.org>', 'rsa2048', 'sign', '1d'],
                               env=env, check=True, stderr=subprocess.DEVNULL)
                key = subprocess.check_output(['gpg', '--batch', '--export-secret-keys'], env=env)
                repository = root / 'repository'
                pool = repository / 'pool/main'
                pool.mkdir(parents=True)
                for name in sorted(apt.PACKAGES):
                    self.package(pool, name, '0.1.0')
                __import__('shutil').rmtree(pool / 'stage')
                apt.build_indexes(repository)
                home = root / 'signing'
                home.mkdir(mode=0o700)
                with patch.dict(os.environ, APT_SIGNING_KEY_B64=base64.b64encode(key).decode(),
                                APT_SIGNING_KEY_PASSPHRASE=''):
                    apt.sign(repository, home)
                # APT itself must accept the repository with signed-by and
                # reject tampered detached metadata below.
                lists = root / 'lists'
                (lists / 'partial').mkdir(parents=True)
                sources = root / 'sources.list'
                sources.write_text(f'deb [signed-by={repository / "ptos-archive-keyring.gpg"}] file:{repository} stable main\n')
                subprocess.run(['apt-get', '-o', f'Dir::Etc::sourcelist={sources}',
                                '-o', 'Dir::Etc::sourceparts=-', '-o', f'Dir::State::lists={lists}',
                                '-o', 'APT::Sandbox::User=' + __import__('getpass').getuser(),
                                '-o', 'APT::Update::Error-Mode=any', 'update'], check=True)
                release = repository / 'dists/stable/Release'
                release.write_text(release.read_text() + 'Tampered: yes\n')
                result = subprocess.run(['gpgv', '--keyring', str(repository / 'ptos-archive-keyring.gpg'),
                                         str(release.parent / 'Release.gpg'), str(release)], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
            finally:
                for home in [generation, root / 'signing']:
                    subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'all'], check=False)

    def release(self, version, size=10):
        return {'tag_name': 'v' + version, 'version': version, 'draft': False, 'prerelease': False,
                'assets': [{'name': f'{name}_{version}_amd64.deb', 'size': size} for name in sorted(apt.PACKAGES)]
                          + [{'name': 'SHA256SUMS', 'size': 100}]}

    def test_stable_release_sort_and_filter(self):
        releases = [self.release(v) for v in ['0.2.0', '0.10.0', '0.1.0']]
        releases += [dict(self.release('1.0.0'), prerelease=True),
                     dict(self.release('2.0.0'), draft=True),
                     dict(self.release('3.0.0'), assets=[])]
        self.assertEqual([r['version'] for r in apt.stable_releases(releases)], ['0.10.0', '0.2.0', '0.1.0'])
        with self.assertRaisesRegex(ValueError, 'Multiple release tags'):
            apt.stable_releases([self.release('0.1.0'), self.release('0.1.0')])

    def test_retention_and_size_budget(self):
        releases = [self.release(f'0.{n}.0') for n in range(5, 0, -1)]
        self.assertEqual(len(apt.select_releases(releases, 3, 1000, {})), 3)
        self.assertEqual(len(apt.select_releases(releases, 3, 65, {})), 2)
        self.assertEqual(len(apt.select_releases(releases, 1, 1000, {})), 1)
        with self.assertRaisesRegex(ValueError, 'grace packages exceed'):
            apt.select_releases(releases, 3, 40, {'old.deb': 20})
        with self.assertRaisesRegex(ValueError, 'Retention count'):
            apt.select_releases(releases, 0, 100, {})
        with self.assertRaisesRegex(ValueError, 'Retention count'):
            apt.select_releases(releases, 3, apt.DEFAULT_LIMIT + 1, {})

    def test_grace_preserves_current_and_expires_old_snapshots(self):
        state = {'snapshots': [{'id': 'old', 'last_active': 1},
                               {'id': 'recent', 'last_active': 199999},
                               {'id': 'current', 'last_active': 2}]}
        result = apt.retained_snapshots(state, 200000, 86400)
        self.assertEqual([s['id'] for s in result], ['recent', 'current'])
        self.assertEqual(result[-1]['last_active'], 200000)
        with self.assertRaisesRegex(ValueError, 'at least 24 hours'):
            apt.retained_snapshots(state, 200000, 1)

    def test_pages_root_size_and_immutable_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            apt.write_pages_root(root)
            self.assertTrue((root / '.nojekyll').is_file())
            self.assertIn('<!doctype html>', (root / 'index.html').read_text())
            self.assertEqual((root / 'CNAME').read_text(), 'apt.ptos.dev\n')
            size = apt.enforce_size(root, 10000)
            self.assertGreater(size, 0)
            with self.assertRaisesRegex(ValueError, 'above configured limit'):
                apt.enforce_size(root, size - 1)
        ledger = {}
        apt.remember(ledger, 'package.deb', 'first')
        apt.remember(ledger, 'package.deb', 'first')
        with self.assertRaisesRegex(ValueError, 'Immutable package conflict'):
            apt.remember(ledger, 'package.deb', 'changed')

    def test_index_references_require_actual_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pool = root / 'pool/main'
            pool.mkdir(parents=True)
            package = self.package(pool, 'ptos-sdk-arm', '0.1.0')
            __import__('shutil').rmtree(pool / 'stage')
            apt.build_indexes(root)
            apt.validate_index_references(root)
            package.unlink()
            with self.assertRaisesRegex(ValueError, 'missing or incorrect package'):
                apt.validate_index_references(root)

    def test_history_hashes_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b'old Packages index'
            sha = __import__('hashlib').sha256(content).hexdigest()
            apt.restore_history(root, [{'indexes': {sha: base64.b64encode(content).decode()}}])
            self.assertEqual((root / apt.BINARY / 'by-hash/SHA256' / sha).read_bytes(), content)
            with self.assertRaisesRegex(ValueError, 'Invalid historical'):
                apt.restore_history(root, [{'indexes': {sha: base64.b64encode(b'tampered').decode()}}])

    def test_previous_state_uses_successful_deploy_not_overall_run(self):
        import io
        import json
        import zipfile
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('apt-verification.json', json.dumps({'apt-state.json': 'expected-hash'}))
        responses = [json.dumps([{'artifacts': [
            {'expired': False, 'workflow_run': {'id': 10}, 'archive_download_url': 'archive'}]}]).encode(),
            json.dumps({'event': 'release', 'path': '.github/workflows/release-deb.yml'}).encode(),
            json.dumps([{'jobs': [{'name': 'publish-apt / deploy', 'conclusion': 'success'},
                                 {'name': 'publish-apt / verify', 'conclusion': 'failure'}]}]).encode(),
            archive.getvalue()]
        with patch.object(apt, 'run', side_effect=responses):
            self.assertEqual(apt.deployed_state_digest('fixture/repo'), 'expected-hash')

    def test_bootstrap_refuses_existing_deployment(self):
        import json
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, GH_REPO='fixture/repo'), \
                patch.object(apt, 'deployed_state_digest', return_value=None), \
                patch.object(apt, 'run', side_effect=[json.dumps([[{'statuses_url': 'statuses'}]]).encode(),
                                                     json.dumps([{'state': 'inactive'}]).encode()]):
            with self.assertRaisesRegex(ValueError, 'previous deployment'):
                apt.previous_state(Path(temporary), Path('keyring'), 'https://example.org', True)

    def test_initial_bootstrap_does_not_require_certificate(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, GH_REPO='fixture/repo'), \
                patch.object(apt, 'deployed_state_digest', return_value=None), \
                patch.object(apt, 'run', return_value=b'[[]]'), patch.object(apt, 'fetch') as fetch:
            state = apt.previous_state(Path(temporary), Path('keyring'), 'https://example.org', True)
            self.assertEqual(state, {'ledger': {}, 'snapshots': []})
            fetch.assert_not_called()

    def test_full_pages_generation_and_repeated_deployment(self):
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / 'key'
            home.mkdir(mode=0o700)
            env = dict(os.environ, GNUPGHOME=str(home))
            try:
                subprocess.run(['gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                                '--quick-generate-key', 'Fixture Pages <apt@example.org>', 'rsa2048', 'sign', '1d'],
                               check=True, env=env, stderr=subprocess.DEVNULL)
                key = subprocess.check_output(['gpg', '--batch', '--export-secret-keys'], env=env)
                releases = []
                for n in range(1, 5):
                    version = f'0.{n}.0'
                    directory = root / ('v' + version)
                    directory.mkdir()
                    files = [self.package(directory, name, version) for name in sorted(apt.PACKAGES)]
                    shutil.rmtree(directory / 'stage')
                    (directory / 'SHA256SUMS').write_text(''.join(f'{apt.digest(p)}  {p.name}\n' for p in files))
                    release = self.release(version)
                    for asset in release['assets']:
                        asset['size'] = (directory / asset['name']).stat().st_size
                    releases.append(release)
                original_run = apt.run
                available = releases[:3]

                def fake_run(*args, **kwargs):
                    if args[:2] == ('gh', 'api'):
                        return __import__('json').dumps([available]).encode()
                    if args[:3] == ('gh', 'release', 'download'):
                        destination = Path(args[args.index('--dir') + 1])
                        for file in (root / args[3]).iterdir():
                            shutil.copyfile(file, destination / file.name)
                        return b''
                    return original_run(*args, **kwargs)

                state = {'ledger': {}, 'snapshots': []}
                for attempt, tag in enumerate(['v0.3.0', 'v0.4.0', 'v0.4.0']):
                    site = root / f'site-{attempt}'
                    with patch.dict(os.environ, GH_TOKEN='fixture', GH_REPO='fixture/repo', RELEASE_TAG=tag,
                                    APT_SIGNING_KEY_B64=base64.b64encode(key).decode(),
                                    APT_SIGNING_KEY_PASSPHRASE='', APT_STAGING_DIR=str(site),
                                    APT_RETAIN_VERSIONS='3'), patch.object(apt, 'run', side_effect=fake_run), \
                            patch.object(apt, 'previous_state', return_value=state):
                        apt.main()
                    state = __import__('json').loads((site / 'apt-state.json').read_text())
                    apt.validate_index_references(site)
                    self.assertEqual((site / apt.BINARY / 'Packages').read_text().count('Package: '), 9)
                    self.assertTrue((site / 'index.html').exists())
                    if attempt:
                        self.assertEqual(len(list((site / 'pool/main').glob('*.deb'))), 12)
                        self.assertNotIn('Version: 0.1.0', (site / apt.BINARY / 'Packages').read_text())
                        for snapshot in state['snapshots']:
                            for sha in snapshot['indexes']:
                                self.assertTrue((site / apt.BINARY / 'by-hash/SHA256' / sha).exists())
                    available = releases
                self.assertEqual(len(state['snapshots']), 2)
            finally:
                subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'all'], check=False)

    def test_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'Missing required secrets/variables: GH_TOKEN'):
                apt.main()


if __name__ == '__main__':
    unittest.main()
