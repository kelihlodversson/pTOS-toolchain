"""Shared package identities and exact all-target release dependencies."""
import re
import subprocess

SDK_PACKAGES = {'ptos-sdk-m68k', 'ptos-sdk-arm', 'ptos-sdk-x86-64'}
META_PACKAGE = 'ptos-toolchain'
ALL_PACKAGES = SDK_PACKAGES | {META_PACKAGE}


def validate_version(version):
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+~\-]*', version):
        raise ValueError('invalid Debian package version')
    subprocess.run(['dpkg', '--validate-version', version], check=True)


def dependencies(version):
    return ', '.join(f'{name} (= {version})' for name in sorted(SDK_PACKAGES))


def validate_metapackage(path, version):
    actual = subprocess.check_output(['dpkg-deb', '-f', str(path), 'Depends'], text=True).strip()
    if sorted(re.sub(r'\s+', ' ', part.strip()) for part in actual.split(',')) != dependencies(version).split(', '):
        raise ValueError('ptos-toolchain must depend on all three SDKs at the exact release version')
