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

    def test_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'Missing required secrets/variables: GH_TOKEN'):
                apt.main()


if __name__ == '__main__':
    unittest.main()
