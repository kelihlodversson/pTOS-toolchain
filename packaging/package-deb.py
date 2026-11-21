#!/usr/bin/env python3
"""Split one built pTOS SDK into Debian component packages and a metapackage."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from debian_packages import (COMPONENTS, FIRST_SPLIT_VERSION, TARGETS, exact_dependency,
                             is_split_version, package_name, sdk_dependencies, sdk_takeover,
                             validate_version)

PROJECT = Path(__file__).resolve().parents[1]
SMOKE_FILES = ('smoke.sh', 'm68k_auto_inc_dec.py', 'm68k-auto-inc-dec.c', 'm68k-auto-inc-dec-runtime.c',
               'm68k_reload_const_modes.py', 'm68k-reload-const-modes.c', 'm68k-reload-const-modes-runtime.c',
               'm68k_lra_address.py', 'm68k-lra-address.c')


def output(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def native_elf(path, signature):
    """Exclude target objects, archives and cross-target ELF executables."""
    if path.is_symlink() or not path.is_file():
        return False
    with path.open('rb') as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:6] != signature[:6]:
        return False
    order = '<' if header[5] == 1 else '>'
    kind = struct.unpack(order + 'H', header[16:18])[0]
    return kind in (2, 3) and header[18:20] == signature[18:20]


def split_files(prefix, target, manifest):
    installed = {p.relative_to(prefix) for p in prefix.rglob('*') if p.is_symlink() or p.is_file()}
    binutils = {Path(line) for line in manifest.read_text().splitlines()}
    sysroot = {p for p in installed if p.is_relative_to(Path(target) / 'sysroot')}
    gcc_commands = {Path('bin') / f'{target}-{driver}' for driver in ('gcc', 'g++')}
    if not binutils <= installed or binutils & (sysroot | gcc_commands):
        raise ValueError('Binutils manifest does not match a Binutils-only installation in this SDK')
    if not all(Path('bin') / f'{target}-{tool}' in binutils for tool in ('as', 'ld')):
        raise ValueError('Binutils manifest must include the target assembler and linker')
    if not gcc_commands <= installed:
        raise ValueError('SDK must include the C and C++ drivers')
    return {'binutils': binutils, 'gcc': installed - binutils - sysroot, 'sysroot': sysroot}


def install_files(root, install_path, prefix, target, paths):
    sdk = root / install_path.relative_to('/')
    for relative in sorted(paths):
        destination = sdk / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prefix / relative, destination, follow_symlinks=False)
        if relative.parent == Path('bin'):
            if not relative.name.startswith(target + '-'):
                raise ValueError(f'unexpected command in SDK: {relative.name}')
            link = root / 'usr/bin' / relative.name
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(install_path / relative)
    return sdk


def host_dependencies(work, package, host_arch, sdk):
    signature = Path('/usr/bin/dpkg-deb').read_bytes()[:20]
    binaries = [p for p in sorted(sdk.rglob('*')) if native_elf(p, signature)]
    if not binaries:
        raise ValueError(f'{package} contains no native host executables')
    for binary in binaries:
        subprocess.run(['strip', '--strip-unneeded', str(binary)], check=True)
    (work / 'debian/control').write_text(f'Source: {package}\n\nPackage: {package}\nArchitecture: {host_arch}\n')
    fields = output('dpkg-shlibdeps', '-O', *('-e' + str(p.relative_to(work)) for p in binaries), cwd=work)
    return next((line.split('=', 1)[1] for line in fields.splitlines() if line.startswith('shlibs:Depends=')), '')


def write_package(root, destination, package, version, host_arch, description, depends, takeover, env):
    size = (sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink()) + 1023) // 1024
    control = root / 'DEBIAN'
    relationships = f'Depends: {depends}\n' if depends else ''
    if takeover:
        relationships += f'Breaks: {takeover}\nReplaces: {takeover}\n'
    (control / 'control').write_text(
        f'Package: {package}\nVersion: {version}\nArchitecture: {host_arch}\n'
        'Maintainer: Keli Hlodversson <keli@keli.dk>\n'
        f'Section: devel\nPriority: optional\nInstalled-Size: {size}\n{relationships}'
        'Homepage: https://github.com/kelihlodversson/pTOS-toolchain\n'
        f'Description: {description}\n'
    )
    for path in [root, *root.rglob('*')]:
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
    subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(root), str(destination)],
                   check=True, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arch', choices=TARGETS)
    parser.add_argument('prefix', type=Path, help='SDK built for /opt/ptos/ARCH')
    parser.add_argument('version', help='Debian package version, e.g. 1.1.0 or 1.2.0~rc1')
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('--binutils-manifest', required=True, type=Path,
                        help='relative file and symlink paths recorded after the Binutils stage')
    parser.add_argument('--work-dir', type=Path, default=Path(os.environ.get('PTOS_WORKDIR', PROJECT / '.work')))
    args = parser.parse_args()
    try:
        validate_version(args.version)
    except ValueError as error:
        parser.error(str(error))
    if not is_split_version(args.version):
        parser.error(f'split SDK packages require Debian version {FIRST_SPLIT_VERSION} or later')
    prefix = args.prefix.resolve(strict=True)
    target = TARGETS[args.arch]
    compiler = prefix / 'bin' / f'{target}-gcc'
    recipes = json.loads((PROJECT / 'versions.json').read_text())
    gcc, binutils = recipes['gcc'][-1], recipes['binutils'][-1]
    if output(str(compiler), '-dumpmachine') != target:
        parser.error('SDK compiler target does not match the requested architecture')
    if output(str(compiler), '-dumpfullversion') != gcc['version']:
        parser.error('release SDK must use the default GCC recipe')
    if not re.search(r'\b' + re.escape(binutils['version']) + r'\b', output(str(prefix / 'bin' / f'{target}-ld'), '--version')):
        parser.error('release SDK must use the default Binutils recipe')
    if not (prefix / target / 'sysroot' / 'include' / 'stdio.h').is_file():
        parser.error('SDK headers are missing; build the sdk stage first')
    try:
        files = split_files(prefix, target, args.binutils_manifest)
    except ValueError as error:
        parser.error(str(error))
    host_arch = output('dpkg', '--print-architecture')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    revision = re.search(r'^revision=([0-9a-f]+)$', (PROJECT / 'install-libcmini.sh').read_text(), re.M).group(1)
    commit = output('git', '-C', str(PROJECT), 'rev-parse', 'HEAD')
    environment = os.environ.copy()
    environment.setdefault('SOURCE_DATE_EPOCH', output('git', '-C', str(PROJECT), 'show', '-s', '--format=%ct', 'HEAD'))
    install_path = Path('/opt/ptos') / args.arch
    licenses = {
        'binutils': {'Binutils-GPL-3': args.work_dir / args.arch / f"binutils-{binutils['version']}-src/COPYING3"},
        'gcc': {
            'GCC-GPL-3': args.work_dir / args.arch / f"gcc-{gcc['version']}-src/COPYING3",
            'GCC-RUNTIME-EXCEPTION': args.work_dir / args.arch / f"gcc-{gcc['version']}-src/COPYING.RUNTIME",
        },
        'sysroot': {'libcmini-LGPL-2.1': args.work_dir / args.arch / f'libcmini-{revision}/LICENSE.txt'},
        'sdk': {},
    }
    descriptions = {
        'binutils': f"Binutils {binutils['version']} for {target}",
        'gcc': f"GCC {gcc['version']} C and C++ cross-compilers and libgcc for {target}",
        'sysroot': f'pTOS C headers, libcmini and startup objects for {target}',
        'sdk': f'Complete pTOS cross-development SDK for {target}',
    }
    with tempfile.TemporaryDirectory(prefix='ptos-deb-') as temporary:
        work = Path(temporary)
        for component in (*COMPONENTS, 'sdk'):
            package = package_name(component, args.arch)
            root = work / 'debian' / package
            (root / 'DEBIAN').mkdir(parents=True)
            docs = root / 'usr/share/doc' / package
            docs.mkdir(parents=True)
            shutil.copy2(PROJECT / 'packaging/copyright', docs / 'copyright')
            for name, source in licenses[component].items():
                shutil.copy2(source, docs / name)
            info = dict(package=package, version=args.version, host_architecture=host_arch,
                        target=target, prefix=str(install_path), toolchain_commit=commit,
                        gcc=gcc, binutils=binutils, libcmini_revision=revision,
                        toolchain_source=f'https://github.com/kelihlodversson/pTOS-toolchain/archive/{commit}.tar.gz',
                        libcmini_source=f'https://github.com/kelihlodversson/libcmini/archive/{revision}.tar.gz')
            (docs / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
            depends = ''
            takeover = ''
            if component == 'sdk':
                depends = sdk_dependencies(args.arch, args.version)
                for name in SMOKE_FILES:
                    shutil.copy2(PROJECT / 'tests' / name, docs / name)
            else:
                takeover = sdk_takeover(args.arch)
                sdk = install_files(root, install_path, prefix, target, files[component])
                if component in ('binutils', 'gcc'):
                    depends = host_dependencies(work, package, host_arch, sdk)
                if component == 'gcc':
                    binutils_dependency = exact_dependency(package_name('binutils', args.arch), args.version)
                    depends = ', '.join(filter(None, (binutils_dependency, depends)))
            destination = args.output_dir / f'{package}_{args.version}_{host_arch}.deb'
            write_package(root, destination, package, args.version, host_arch, descriptions[component],
                          depends, takeover, environment)
            print(destination)


if __name__ == '__main__':
    main()
