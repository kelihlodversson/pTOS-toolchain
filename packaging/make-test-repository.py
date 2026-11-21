#!/usr/bin/env python3
"""Create an isolated signed CI repository from verified SDK artifacts, never production keys."""
import argparse
import base64
import importlib.util
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).with_name('publish-apt.py'))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('root', type=Path)
    parser.add_argument('--historical', type=Path)
    args = parser.parse_args()
    source, root = args.source.resolve(), args.root.resolve()
    version = subprocess.check_output(['dpkg-deb', '-f', str(next(source.glob('*.deb'))), 'Version'], text=True).strip()
    files = publisher.verify_assets(source, version)
    pool = root / 'pool/main'
    pool.mkdir(parents=True)
    publisher.merge(pool, files)
    if args.historical:
        historical = args.historical.resolve()
        old_version = subprocess.check_output(
            ['dpkg-deb', '-f', str(next(historical.glob('*.deb'))), 'Version'], text=True).strip()
        publisher.merge(pool, publisher.verify_assets(historical, old_version))
    if not (pool / f'ptos-toolchain_{version}_amd64.deb').exists():
        build = runpy.run_path(str(Path(__file__).with_name('package-toolchain.py')))['build']
        build(version, pool)
    publisher.build_indexes(root)
    publisher.validate_index_references(root)
    with tempfile.TemporaryDirectory(prefix='ptos-ci-key-') as temporary:
        home = Path(temporary)
        home.chmod(0o700)
        env = dict(os.environ, GNUPGHOME=str(home))
        try:
            subprocess.run(['gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                            '--quick-generate-key', 'pTOS CI fixture <ci@example.invalid>', 'rsa2048', 'sign', '1d'],
                           env=env, check=True)
            key = subprocess.check_output(['gpg', '--batch', '--export-secret-keys'], env=env)
            os.environ['APT_SIGNING_KEY_B64'] = base64.b64encode(key).decode()
            os.environ['APT_SIGNING_KEY_PASSPHRASE'] = ''
            publisher.sign(root, home)
        finally:
            os.environ.pop('APT_SIGNING_KEY_B64', None)
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'all'], check=False)
    print(version)


if __name__ == '__main__':
    main()
