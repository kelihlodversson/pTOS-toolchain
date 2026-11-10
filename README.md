# pTOS toolchain

This C SDK builds pTOS programs and freestanding kernels. It builds native
GCC and GNU Binutils targets, together with `libgcc`, libcmini headers and
archives, and pTOS program startup objects. GCC 14.3.0 and Binutils 2.45 are
pinned to the versions used by pTOS's m68k build.

| Target | Default output | Additional mode |
| --- | --- | --- |
| `m68k-unknown-ptos-prgelf` | Big-endian ELF32, 68000 cdecl | `-mmintelf` for MiNT PRG+ELF, `-mfastcall` for register arguments |
| `arm-unknown-ptos-elf` | Little-endian ELF32, ARMv6K ARM state, AAPCS hard-float | `-march`, `-mcpu` and `-mfpu` for pTOS's newer ARM boards |
| `x86_64-unknown-ptos-elfx32` | Little-endian ELF32, `EM_X86_64` x32 (ILP32) | `-m64` for freestanding LP64, `ld -m i386pep` for the UEFI kernel image |

The m68k port takes GCC's fastcall implementation and Binutils' PRG+ELF
support from [Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint).
The `-mmintelf` option changes the linker emulation. Object files are ELF in
both modes, and `-mfastcall` selects its own compiler runtime and libcmini
variant. Link together objects that agree on the m68k calling convention.
The ordinary ELF mode also supports `-fPIC -shared` with a GOT and PLT.

## Build

The build needs Bash, GNU Make 4.3 or later, a host C/C++ compiler, the GMP,
MPFR and MPC development libraries, bison, flex, m4, Git, curl, patch, GNU tar,
xz, `sha256sum`, and Python 3 with `kconfiglib`. Install `kconfiglib` in an
active virtual environment if the host keeps its Python environment managed.

```sh
python3 -m pip install kconfiglib
./build.sh all "$HOME/opt/ptos"
./tests/smoke.sh "$HOME/opt/ptos"
export PATH="$HOME/opt/ptos/bin:$PATH"
```

Pass `m68k`, `arm` or `x86_64` instead of `all` to build a single target.
`JOBS` controls Make parallelism. `PTOS_WORKDIR` selects the build directory,
and `PTOS_CACHE` selects the download cache. Use a fresh work directory when
changing the installation prefix, source recipe or host toolchain.

## Build a C application

```c
#include <stdio.h>

int main(void)
{
    puts("Hello from pTOS");
    return 0;
}
```

```sh
m68k-unknown-ptos-prgelf-gcc hello.c -o hello-m68k.elf
m68k-unknown-ptos-prgelf-gcc -mmintelf hello.c -o hello.tos
arm-unknown-ptos-elf-gcc hello.c -o hello-arm.elf
x86_64-unknown-ptos-elfx32-gcc hello.c -o hello-x32.elf
```

The driver supplies the target's libcmini and startup object for regular
links. Native m68k and ARM executables keep relocations for pTOS's static
ELF loader. The ARM driver uses word relocations so absolute addresses stay
rebasable. x32 uses 4 KiB pages at the standard user image base. Keep the
relocation records on binaries that need rebasing. For your own startup and
linker script, use `-ffreestanding -nostdlib` and specify the layout directly.

Shared libraries and dynamic executables use the corresponding pTOS
runtime linker and entry ABI. See [pTOS's ELF shared libraries document](https://github.com/kelihlodversson/pTOS/blob/master/doc/elf-shared.txt)
for the interpreter paths, loader flags and runtime conventions.

## Build the pTOS kernel

Run these commands from a pTOS checkout with its submodules initialised.
Use separate checkouts or `make distclean` between configurations.

```sh
make virt-m68k-fastcall_defconfig
make CROSS_COMPILE=m68k-unknown-ptos-prgelf-

make virt-arm_defconfig
make CROSS_COMPILE=arm-unknown-ptos-elf- CROSSPREFIX=arm-unknown-ptos-elf-

make pc-x86_64_defconfig
make CROSS_COMPILE=x86_64-unknown-ptos-elfx32-
```

With the current pTOS Makefile, pass `LDSO_M68K_PREFIX=m68k-unknown-ptos-prgelf-`
to select this toolchain for m68k shared libraries as well. For m68k EmuCON
or a test program that should be plain ELF, pass `M68K_ELF=y` to select the
ELF CLI link, or use `TEST_LDFLAGS='-Wl,-q,-Ttext=0,-e,_start'` for the test
harness. For a PRG compatibility build, add `-mmintelf` to the program's
link flags instead.

The x86-64 Makefile already selects `-m64 -mno-red-zone` for the kernel and
the `i386pep` linker emulation for its boot image. The driver selects a
dedicated no-red-zone LP64 `libgcc` for that build. Applications use x32.
