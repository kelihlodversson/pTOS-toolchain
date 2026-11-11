#!/usr/bin/env python3
"""Exercise real .deb assembly with a small SDK fixture; no compiler build."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
TARGETS = {
    'm68k': 'm68k-unknown-ptos-prgelf',
    'arm': 'arm-unknown-ptos-elf',
    'x86_64': 'x86_64-unknown-ptos-elfx32',
}


class DebianPackages(unittest.TestCase):
    def test_assembly_dependencies_and_coexistence(self):
        recipes = json.loads((PROJECT / 'versions.json').read_text())
        gcc, binutils = recipes['gcc'][-1]['version'], recipes['binutils'][-1]['version']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installed = root / 'installed'
            packages = []
            for arch, target in TARGETS.items():
                prefix = root / arch
                (prefix / 'bin').mkdir(parents=True)
                cc = prefix / 'bin' / f'{target}-gcc'
                cc.write_text(f'#!/bin/sh\ncase "$1" in\n-dumpmachine) echo {target} ;;\n-dumpfullversion) echo {gcc} ;;\nesac\n')
                cc.chmod(0o700)
                ld = prefix / 'bin' / f'{target}-ld'
                ld.write_text(f'#!/bin/sh\necho "GNU ld {binutils}"\n')
                ld.chmod(0o700)
                # Native ELF dependencies must be recorded; target ELF must not
                # be stripped or handed to dpkg-shlibdeps as a host executable.
                shutil.copy2('/bin/true', prefix / 'bin' / f'{target}-objcopy')
                sysroot = prefix / target / 'sysroot'
                (sysroot / 'include').mkdir(parents=True)
                (sysroot / 'include/stdio.h').write_text('/* fixture */\n')
                (sysroot / 'lib').mkdir()
                arm_elf = bytes.fromhex('7f454c4601010100000000000000000003002800')
                (sysroot / 'lib/target.so').write_bytes(arm_elf)
                work = root / 'work' / arch
                revision = 'c85f67a52679b68782c49fd967732d14bfe87841'
                for name in [f'gcc-{gcc}-src/COPYING3', f'gcc-{gcc}-src/COPYING.RUNTIME',
                             f'binutils-{binutils}-src/COPYING3', f'libcmini-{revision}/LICENSE.txt']:
                    p = work / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('License fixture\n')
                subprocess.run(['python3', str(PROJECT / 'packaging/package-deb.py'), arch,
                                str(prefix), '1.2.3~rc1', str(root / 'dist'), '--work-dir', str(root / 'work')], check=True)
                package = next((root / 'dist').glob(f'ptos-sdk-{arch.replace("_", "-")}_*.deb'))
                packages.append(package)
                depends = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Depends'], text=True)
                self.assertIn('libc6', depends)
                self.assertEqual(subprocess.check_output(['dpkg-deb', '-f', str(package), 'Architecture'], text=True).strip(),
                                 subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip())
                subprocess.run(['dpkg-deb', '-x', str(package), str(installed)], check=True)
                link = installed / 'usr/bin' / f'{target}-gcc'
                self.assertEqual(str(link.readlink()), f'/opt/ptos/{arch}/bin/{target}-gcc')
                self.assertEqual((installed / f'opt/ptos/{arch}/{target}/sysroot/lib/target.so').read_bytes(), arm_elf)
                self.assertEqual((installed / f'opt/ptos/{arch}/bin/{target}-gcc').stat().st_mode & 0o777, 0o755)
                info = json.loads((installed / f'usr/share/doc/ptos-sdk-{arch.replace("_", "-")}/build-info.json').read_text())
                self.assertEqual(info['gcc']['version'], gcc)
            self.assertEqual(len(packages), 3)
            for arch, target in TARGETS.items():
                self.assertTrue((installed / f'opt/ptos/{arch}/bin/{target}-gcc').is_file())

    def test_invalid_version(self):
        result = subprocess.run(['python3', str(PROJECT / 'packaging/package-deb.py'), 'arm',
                                 '/does-not-exist', 'invalid version', '/does-not-exist'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid Debian package version', result.stderr)

    def test_release_versions(self):
        for tag, expected in [('v1.0.0', '1.0.0'), ('1.0.0', '1.0.0'),
                              ('v1.1.0-rc1', '1.1.0~rc1')]:
            actual = subprocess.check_output(['bash', str(PROJECT / 'packaging/release-version.sh'), tag], text=True)
            self.assertEqual(actual.strip(), expected)
        subprocess.run(['dpkg', '--compare-versions', '1.1.0~rc1', 'lt', '1.1.0'], check=True)


if __name__ == '__main__':
    unittest.main()
