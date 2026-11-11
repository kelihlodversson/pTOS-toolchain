#!/usr/bin/env python3
"""Package one built pTOS SDK for the current Debian/Ubuntu host architecture."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
TARGETS = {
    'm68k': 'm68k-unknown-ptos-prgelf',
    'arm': 'arm-unknown-ptos-elf',
    'x86_64': 'x86_64-unknown-ptos-elfx32',
}


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arch', choices=TARGETS)
    parser.add_argument('prefix', type=Path, help='SDK built for /opt/ptos/ARCH')
    parser.add_argument('version', help='Debian package version, e.g. 1.0.0 or 1.1.0~rc1')
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('--work-dir', type=Path, default=Path(os.environ.get('PTOS_WORKDIR', PROJECT / '.work')))
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+~\-]*', args.version):
        parser.error('invalid Debian package version')
    subprocess.run(['dpkg', '--validate-version', args.version], check=True)
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
    package = 'ptos-sdk-' + args.arch.replace('_', '-')
    host_arch = output('dpkg', '--print-architecture')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir.resolve() / f'{package}_{args.version}_{host_arch}.deb'
    revision = re.search(r'^revision=([0-9a-f]+)$', (PROJECT / 'install-libcmini.sh').read_text(), re.M).group(1)
    commit = output('git', '-C', str(PROJECT), 'rev-parse', 'HEAD')
    environment = os.environ.copy()
    environment.setdefault('SOURCE_DATE_EPOCH', output('git', '-C', str(PROJECT), 'show', '-s', '--format=%ct', 'HEAD'))
    signature = Path('/usr/bin/dpkg-deb').read_bytes()[:20]

    with tempfile.TemporaryDirectory(prefix='ptos-deb-') as temporary:
        work = Path(temporary)
        root = work / 'debian' / package
        install_path = Path('/opt/ptos') / args.arch
        sdk = root / install_path.relative_to('/')
        shutil.copytree(prefix, sdk, symlinks=True)
        binaries = [p for p in sdk.rglob('*') if native_elf(p, signature)]
        if not binaries:
            parser.error('SDK contains no native host executables')
        for binary in binaries:
            subprocess.run(['strip', '--strip-unneeded', str(binary)], check=True)
        links = root / 'usr/bin'
        links.mkdir(parents=True)
        for binary in sorted((sdk / 'bin').iterdir()):
            if not binary.name.startswith(target + '-'):
                parser.error(f'unexpected command in SDK: {binary.name}')
            (links / binary.name).symlink_to(install_path / 'bin' / binary.name)

        docs = root / 'usr/share/doc' / package
        docs.mkdir(parents=True)
        shutil.copy2(PROJECT / 'packaging/copyright', docs / 'copyright')
        shutil.copy2(PROJECT / 'tests/smoke.sh', docs / 'smoke.sh')
        licenses = {
            'GCC-GPL-3': args.work_dir / args.arch / f"gcc-{gcc['version']}-src/COPYING3",
            'GCC-RUNTIME-EXCEPTION': args.work_dir / args.arch / f"gcc-{gcc['version']}-src/COPYING.RUNTIME",
            'Binutils-GPL-3': args.work_dir / args.arch / f"binutils-{binutils['version']}-src/COPYING3",
            'libcmini-LGPL-2.1': args.work_dir / args.arch / f'libcmini-{revision}/LICENSE.txt',
        }
        for name, source in licenses.items():
            shutil.copy2(source, docs / name)
        info = dict(package=package, version=args.version, host_architecture=host_arch,
                    target=target, prefix=str(install_path), toolchain_commit=commit,
                    gcc=gcc, binutils=binutils,
                    libcmini_revision=revision,
                    toolchain_source=f'https://github.com/kelihlodversson/pTOS-toolchain/archive/{commit}.tar.gz',
                    libcmini_source=f'https://github.com/kelihlodversson/libcmini/archive/{revision}.tar.gz')
        (docs / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')

        # Resolve native shared-library requirements, excluding all target libraries.
        control = root / 'DEBIAN'
        control.mkdir()
        (work / 'debian/control').write_text(f'Source: {package}\n\nPackage: {package}\nArchitecture: {host_arch}\n')
        dependencies = output('dpkg-shlibdeps', '-O', *('-e' + str(p.relative_to(work)) for p in binaries), cwd=work)
        depends = next(line.split('=', 1)[1] for line in dependencies.splitlines() if line.startswith('shlibs:Depends='))
        size = (sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink()) + 1023) // 1024
        (control / 'control').write_text(
            f'Package: {package}\nVersion: {args.version}\nArchitecture: {host_arch}\n'
            'Maintainer: Keli Hlodversson <keli@keli.dk>\n'
            'Section: devel\nPriority: optional\n'
            f'Installed-Size: {size}\nDepends: {depends}\n'
            'Homepage: https://github.com/kelihlodversson/pTOS-toolchain\n'
            f'Description: GCC, Binutils and C SDK for pTOS ({args.arch})\n'
            f" GCC {gcc['version']}, Binutils {binutils['version']}, libgcc, libcmini\n"
            f' and startup objects for {target}.\n'
        )
        # Normalize permissions after adding metadata too, regardless of umask.
        for path in [root, *root.rglob('*')]:
            if not path.is_symlink():
                mode = path.stat().st_mode
                path.chmod(0o755 if path.is_dir() or mode & 0o111 else 0o644)
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(root), str(destination)],
                       check=True, env=environment)
    print(destination)


if __name__ == '__main__':
    main()
