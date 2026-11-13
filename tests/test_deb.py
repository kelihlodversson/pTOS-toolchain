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
                docs = installed / f'usr/share/doc/ptos-sdk-{arch.replace("_", "-")}'
                for name in ('m68k_auto_inc_dec.py', 'm68k-auto-inc-dec.c', 'm68k-auto-inc-dec-runtime.c'):
                    self.assertEqual((docs / name).read_bytes(), (PROJECT / 'tests' / name).read_bytes())
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


class AllTargetMetapackage(unittest.TestCase):
    def build(self, root, version='0.2.0'):
        subprocess.run(['python3', str(PROJECT / 'packaging/package-toolchain.py'), version, str(root)], check=True,
                       stdout=subprocess.DEVNULL)
        return root / f'ptos-toolchain_{version}_amd64.deb'

    def test_control_payload_reproducibility_and_coexistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.build(root / 'one')
            other = self.build(root / 'two')
            self.assertEqual(package.read_bytes(), other.read_bytes())
            fields = subprocess.check_output(['dpkg-deb', '-f', str(package)], text=True)
            for text in ['Package: ptos-toolchain', 'Version: 0.2.0', 'Architecture: amd64', 'Section: devel']:
                self.assertIn(text, fields)
            depends = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Depends'], text=True).strip()
            self.assertEqual(depends, 'ptos-sdk-arm (= 0.2.0), ptos-sdk-m68k (= 0.2.0), ptos-sdk-x86-64 (= 0.2.0)')
            installed = root / 'installed'
            subprocess.run(['dpkg-deb', '-x', str(package), str(installed)], check=True)
            files = [p for p in installed.rglob('*') if p.is_file()]
            self.assertEqual({p.name for p in files}, {'README', 'copyright'})
            self.assertTrue(all(p.is_relative_to(installed / 'usr/share/doc/ptos-toolchain') for p in files))
            self.assertLess(sum(p.stat().st_size for p in files), 8192)
            self.assertFalse((installed / 'usr/bin').exists())
            self.assertFalse((installed / 'opt').exists())
            # Extracting the tiny package must not overwrite any SDK files.
            (installed / 'opt/ptos/m68k').mkdir(parents=True)
            sentinel = installed / 'opt/ptos/m68k/compiler'
            sentinel.write_text('SDK remains intact')
            subprocess.run(['dpkg-deb', '-x', str(package), str(installed)], check=True)
            self.assertEqual(sentinel.read_text(), 'SDK remains intact')

    def test_invalid_version(self):
        result = subprocess.run(['python3', str(PROJECT / 'packaging/package-toolchain.py'),
                                 'invalid version', '/tmp/unused-ptos-meta'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid Debian package version', result.stderr)

    def test_four_asset_validation_and_historical_three_asset_compatibility(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('publisher', PROJECT / 'packaging/publish-apt.py')
        publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = []
            for name in sorted(publisher.PACKAGES):
                stage = root / name
                (stage / 'DEBIAN').mkdir(parents=True)
                (stage / 'DEBIAN').chmod(0o755)
                (stage / 'DEBIAN/control').write_text(f'Package: {name}\nVersion: 0.2.0\nArchitecture: amd64\nMaintainer: Test <test@example.org>\nDescription: fixture\n')
                package = root / f'{name}_0.2.0_amd64.deb'
                subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(package)], check=True, stdout=subprocess.DEVNULL)
                files.append(package)
            def checksums():
                (root / 'SHA256SUMS').write_text(''.join(f'{publisher.digest(p)}  {p.name}\n' for p in files))
            checksums()
            self.assertEqual(len(publisher.verify_assets(root, '0.2.0')), 3)
            files.append(self.build(root))
            checksums()
            self.assertEqual(len(publisher.verify_assets(root, '0.2.0')), 4)
            repository = root / 'repo'
            publisher.merge(repository / 'pool/main', files)
            publisher.build_indexes(repository)
            publisher.validate_index_references(repository)
            index = (repository / publisher.BINARY / 'Packages').read_text()
            self.assertEqual(index.count('Package: '), 4)
            self.assertIn('Filename: pool/main/ptos-toolchain_0.2.0_amd64.deb', index)
            self.assertIn('ptos-sdk-arm (= 0.2.0)', index)
            files[-1].write_bytes(b'bad checksum')
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                publisher.verify_assets(root, '0.2.0')

    def test_metapackage_rejects_relaxed_dependency_versions(self):
        import sys
        sys.path.insert(0, str(PROJECT / 'packaging'))
        from debian_packages import validate_metapackage
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.build(root)
            extracted = root / 'stage'
            subprocess.run(['dpkg-deb', '-R', str(package), str(extracted)], check=True)
            control = extracted / 'DEBIAN/control'
            control.write_text(control.read_text().replace('(= 0.2.0)', '(>= 0.2.0)'))
            subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(extracted), str(package)], check=True, stdout=subprocess.DEVNULL)
            with self.assertRaisesRegex(ValueError, 'exact release version'):
                validate_metapackage(package, '0.2.0')


if __name__ == '__main__':
    unittest.main()
