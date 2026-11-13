#!/usr/bin/env python3
"""Create an isolated signed CI repository from verified SDK artifacts, never production keys."""
import base64
import importlib.util
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).with_name('publish-apt.py'))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def main():
    source, root = map(lambda s: Path(s).resolve(), sys.argv[1:])
    version = subprocess.check_output(['dpkg-deb', '-f', str(next(source.glob('*.deb'))), 'Version'], text=True).strip()
    files = publisher.verify_assets(source, version)
    pool = root / 'pool/main'
    pool.mkdir(parents=True)
    publisher.merge(pool, files)
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
