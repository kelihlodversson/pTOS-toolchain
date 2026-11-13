#!/usr/bin/env python3
"""Assemble a reproducible dependency-only amd64 metapackage; no SDK build."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from debian_packages import dependencies, validate_version

PROJECT = Path(__file__).resolve().parents[1]


def build(version, output_dir):
    validate_version(version)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir.resolve() / f'ptos-toolchain_{version}_amd64.deb'
    environment = dict(os.environ)
    environment.setdefault('SOURCE_DATE_EPOCH', subprocess.check_output(
        ['git', '-C', str(PROJECT), 'show', '-s', '--format=%ct', 'HEAD'], text=True).strip())
    with tempfile.TemporaryDirectory(prefix='ptos-meta-') as temporary:
        root = Path(temporary) / 'ptos-toolchain'
        control = root / 'DEBIAN'
        control.mkdir(parents=True)
        (control / 'control').write_text(
            f'Package: ptos-toolchain\nVersion: {version}\nArchitecture: amd64\n'
            'Maintainer: Keli Hlodversson <keli@keli.dk>\n'
            'Section: devel\nPriority: optional\nInstalled-Size: 8\n'
            f'Depends: {dependencies(version)}\n'
            'Homepage: https://github.com/kelihlodversson/pTOS-toolchain\n'
            'Description: All-target cross-development SDK selection for pTOS\n'
            ' Installs the m68k, ARM and x86_64/x32 host-side cross-development SDKs\n'
            ' at the same release version. This dependency-only package contains\n'
            ' no compiler binaries and does not replace the host GCC.\n')
        docs = root / 'usr/share/doc/ptos-toolchain'
        docs.mkdir(parents=True)
        (docs / 'README').write_text(
            'This metapackage selects all three pTOS SDKs at one release version.\n'
            'Individual SDK packages can also be installed independently.\n'
            'The compilers run on the host and produce pTOS target programs.\n')
        shutil.copyfile(PROJECT / 'packaging/copyright', docs / 'copyright')
        for path in [root, *root.rglob('*')]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(root), str(destination)],
                       env=environment, check=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    try:
        print(build(args.version, args.output_dir))
    except ValueError as error:
        parser.error(str(error))
