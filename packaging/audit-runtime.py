#!/usr/bin/env python3
"""Report native SDK ABI requirements without inspecting cross-target ELF as host code."""
import re
from pathlib import Path
import subprocess

from debian_packages import TARGETS, is_split_version, package_name


def native_amd64(path):
    with path.open('rb') as stream:
        header = stream.read(20)
    # ELF64, little endian, EM_X86_64; target x32 objects are ELF32.
    return len(header) == 20 and header[:6] == b'\x7fELF\x02\x01' and header[18:20] == b'\x3e\x00'


def main():
    requirements = {'GLIBC': set(), 'GLIBCXX': set(), 'CXXABI': set()}
    for arch, target in TARGETS.items():
        package = package_name('sdk', arch)
        version = subprocess.check_output(['dpkg-query', '-W', '-f', '${Version}', package], text=True)
        native_packages = [package_name(component, arch) for component in ('binutils', 'gcc')] if is_split_version(version) else [package]
        print(subprocess.check_output(['dpkg-query', '-W', '-f',
                                       '${Package} ${Version} ${Architecture}\nDepends: ${Depends}\n',
                                       *native_packages], text=True), flush=True)
        count = 0
        prefix = Path('/opt/ptos') / arch
        for path in prefix.rglob('*'):
            if (path.is_relative_to(prefix / target / 'sysroot') or path.is_symlink()
                    or not path.is_file() or not native_amd64(path)):
                continue
            output = subprocess.check_output(['readelf', '--version-info', str(path)], text=True)
            # Only undefined version requirements, not symbol versions exported
            # by an SDK's own host library, determine compatibility.
            needs = output.split('Version needs section', 1)
            if len(needs) == 2:
                for family, version in re.findall(r'Name: (GLIBCXX|GLIBC|CXXABI)_([0-9.]+)', needs[1]):
                    requirements[family].add(tuple(map(int, version.split('.'))))
            count += 1
        if not count:
            raise ValueError(f'No native host ELF files found in {package}')
        print(f'{package}: inspected {count} native amd64 ELF files', flush=True)
    for family, versions in requirements.items():
        if versions:
            print(f'Maximum required {family}: {".".join(map(str, max(versions)))}', flush=True)
    # Official SDKs are built on Ubuntu 24.04 (glibc 2.39). A newer
    # build host must not silently raise the published minimum glibc ABI.
    if requirements['GLIBC'] and max(requirements['GLIBC']) > (2, 39):
        raise ValueError('Published SDK requires glibc newer than Ubuntu 24.04 (2.39)')
    for package in ['libc6', 'libstdc++6']:
        print(subprocess.check_output(['dpkg-query', '-W', '-f', '${Package} ${Version}\n', package], text=True), flush=True)


if __name__ == '__main__':
    main()
