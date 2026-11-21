"""Shared package identities, exact dependencies and the SDK split boundary."""
import re
import subprocess

TARGETS = {
    'm68k': 'm68k-unknown-ptos-prgelf',
    'arm': 'arm-unknown-ptos-elf',
    'x86_64': 'x86_64-unknown-ptos-elfx32',
}
COMPONENTS = ('binutils', 'gcc', 'sysroot')
FIRST_SPLIT_VERSION = '1.1.0'


def package_name(component, arch):
    return f'ptos-{component}-{arch.replace("_", "-")}'


SDK_PACKAGES = {package_name('sdk', arch) for arch in TARGETS}
COMPONENT_PACKAGES = {package_name(component, arch) for component in COMPONENTS for arch in TARGETS}
META_PACKAGE = 'ptos-toolchain'
MONOLITHIC_PACKAGES = SDK_PACKAGES | {META_PACKAGE}
ALL_PACKAGES = MONOLITHIC_PACKAGES | COMPONENT_PACKAGES


def validate_version(version):
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+~\-]*', version):
        raise ValueError('invalid Debian package version')
    subprocess.run(['dpkg', '--validate-version', version], check=True)


def is_split_version(version):
    return subprocess.run(['dpkg', '--compare-versions', version, 'ge', FIRST_SPLIT_VERSION]).returncode == 0


def release_layouts(version):
    if is_split_version(version):
        return (ALL_PACKAGES,)
    return SDK_PACKAGES, MONOLITHIC_PACKAGES


def exact_dependency(name, version):
    return f'{name} (= {version})'


def dependencies(version):
    return ', '.join(exact_dependency(name, version) for name in sorted(SDK_PACKAGES))


def sdk_dependencies(arch, version):
    return ', '.join(exact_dependency(package_name(component, arch), version) for component in COMPONENTS)


def sdk_takeover(arch):
    return f'{package_name("sdk", arch)} (<< {FIRST_SPLIT_VERSION})'


def control_field(path, field):
    return subprocess.check_output(['dpkg-deb', '-f', str(path), field], text=True).strip()


def relationship_list(value):
    return sorted(re.sub(r'\s+', ' ', part.strip()) for part in value.split(',')) if value else []


def validate_split_package(path, name, version):
    kind, suffix = name.removeprefix('ptos-').split('-', 1)
    arch = suffix.replace('-', '_')
    actual = relationship_list(control_field(path, 'Depends'))
    if kind == 'sdk':
        if actual != relationship_list(sdk_dependencies(arch, version)):
            raise ValueError(f'{name} must depend on its three components at the exact release version')
        return
    ptos_dependencies = [item for item in actual if re.search(r'\bptos-', item)]
    expected = [exact_dependency(package_name('binutils', arch), version)] if kind == 'gcc' else []
    if ptos_dependencies != expected or (kind == 'sysroot' and actual):
        raise ValueError(f'Unexpected component dependencies for {name}')
    for field in ('Breaks', 'Replaces'):
        if control_field(path, field) != sdk_takeover(arch):
            raise ValueError(f'{name} needs versioned {field} against its monolithic SDK')


def validate_metapackage(path, version):
    actual = relationship_list(control_field(path, 'Depends'))
    if actual != dependencies(version).split(', '):
        raise ValueError('ptos-toolchain must depend on all three SDKs at the exact release version')
