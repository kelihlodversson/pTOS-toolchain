# pTOS toolchain

This C SDK builds pTOS programs and freestanding kernels. It builds native
GCC and GNU Binutils targets, together with `libgcc`, libcmini headers and
archives, and pTOS program startup objects. The default is the newest GCC and
Binutils release in the pinned CrossMiNT patch catalogue (GCC 16.2.0 and
Binutils 2.45). Source archives and patches are verified with SHA-256.

| Target | Default output | Additional mode |
| --- | --- | --- |
| `m68k-unknown-ptos-prgelf` | Big-endian ELF32, 68000 cdecl | `-mmintelf` for MiNT PRG+ELF, `-mfastcall` for register arguments |
| `arm-unknown-ptos-elf` | Little-endian ELF32, ARMv6K ARM state, AAPCS hard-float | `-march`, `-mcpu` and `-mfpu` for pTOS's newer ARM boards |
| `x86_64-unknown-ptos-elfx32` | Little-endian ELF32, `EM_X86_64` x32 (ILP32) | `-m64` for freestanding LP64, `ld -m i386pep` for the UEFI kernel image |

The m68k port reuses the GCC fastcall implementation and the Binutils
PRG+ELF support from [Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint).
The patches are stored locally in [patches/](patches/README.md); the build
verifies their checksums and applies them without downloading patches.
That directory also archives the upstream patches for other GCC and Binutils
versions.

The `-mmintelf` option changes the linker emulation. Object files are ELF in
both modes, and `-mfastcall` selects its own compiler runtime and libcmini
variant. Link together objects that agree on the m68k calling convention.
The ordinary ELF mode also supports `-fPIC -shared` with a GOT and PLT.

## Build

The build needs Bash, GNU Make 4.3 or later, a host C/C++ compiler, the GMP,
MPFR and MPC development libraries, bison, flex, m4, Git, curl, patch, tar
with xz support, `sha256sum` or `shasum`, and Python 3 with `kconfiglib`.
Install `kconfiglib` in an active virtual environment if the host keeps its
Python environment managed.

```sh
python3 -m pip install kconfiglib
./build.sh all "$HOME/opt/ptos"
./tests/smoke.sh "$HOME/opt/ptos"
export PATH="$HOME/opt/ptos/bin:$PATH"
```

Pass `m68k`, `arm` or `x86_64` instead of `all` to build a single target.
Select GCC and Binutils independently; omitted versions (or `latest`) select
the newest entry. Each release uses its newest patch from the pinned CrossMiNT
revision, except GCC 16.2.0, which uses the local patch described below.
GCC 12 and newer are supported.
List the available versions without downloading or building anything:

```sh
./build.sh --list-versions
./build.sh m68k "$HOME/opt/ptos-gcc14" --gcc 14.3.0 --binutils 2.45
./build.sh all "$HOME/opt/ptos-gcc15" gcc --gcc 15.2.0
```

The optional third positional argument selects `binutils`, `gcc` or `sdk`;
omitting it builds all stages. Install matching Binutils before running the
`gcc` stage alone. Use separate installation prefixes to retain several SDKs.
Source and compiler build directories are separated by version. The download
cache is shared, including between versions.

`JOBS` controls Make parallelism. `PTOS_WORKDIR` selects the build directory,
and `PTOS_CACHE` selects the download cache. Use a fresh work directory when
changing the installation prefix, source recipe or host toolchain.
`versions.json` records the supported recipes; `versions.py` selects and lists
them. Run `python3 tests/test_versions.py` for the offline selection checks.
With the source archives and patches already cached, run
`python3 tests/prepare_versions.py /path/to/downloads` to verify checksums,
patch application and pTOS source preparation for every supported release and
target. This checks source preparation; it does not compile the toolchains.

### macOS

Install Apple's Command Line Tools (`xcode-select --install`) and the build
dependencies with Homebrew:

```sh
brew install make gmp mpfr libmpc python xz
python3 -m venv .work/venv
source .work/venv/bin/activate
python3 -m pip install kconfiglib
./build.sh all "$HOME/opt/ptos"
./tests/smoke.sh "$HOME/opt/ptos"
```

The build selects Homebrew's `gmake` (Apple's bundled Make is too old),
finds Homebrew's GMP/MPFR/MPC prefixes on both Apple Silicon and Intel,
uses the macOS system zlib, and supports Apple's tar and checksum tools.
Set `MAKE` to override the
GNU Make executable. The selected Make also builds libcmini.

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

On m68k, enable `CONF_WITH_ELF_LOADER` in the pTOS kernel to run plain ELF
programs. The `virt-m68k-cli-elf` configuration enables it.

Shared libraries and dynamic executables use the corresponding pTOS
runtime linker and entry ABI. The interpreter paths and loader flags are
documented in [ELF shared libraries](https://github.com/kelihlodversson/pTOS/blob/master/doc/elf-shared.txt).

## Build the pTOS kernel

Run these commands from a pTOS checkout with its submodules initialised.
Use separate checkouts or `make distclean` between configurations.

```sh
make virt-m68k-cli-elf_defconfig
make CROSS_COMPILE=m68k-unknown-ptos-prgelf- CROSSPREFIX=m68k-unknown-ptos-prgelf- BUILD_TOOLCHAIN_ELF=y

make virt-arm_defconfig
make CROSS_COMPILE=arm-unknown-ptos-elf- CROSSPREFIX=arm-unknown-ptos-elf-

make pc-x86_64_defconfig
make CROSS_COMPILE=x86_64-unknown-ptos-elfx32-
```

With the current pTOS Makefile, pass `LDSO_M68K_PREFIX=m68k-unknown-ptos-prgelf-`
to select this toolchain for m68k shared libraries as well. Select the ELF
EmuCON link with `BUILD_TOOLCHAIN_ELF=y` and the ELF test-harness link with
`TEST_LDFLAGS='-Wl,-q,-Ttext=0,-e,_start'`. The `relocprobe2-unpacked.tos`
fixture in the current pTOS test suite uses the MiNT linker script layout.
Add `-m m68kmintelf` to its direct `ld` invocation and keep its explicit
`--oformat=elf32-m68k`. For a PRG compatibility application, add `-mmintelf`
to the GCC link flags.

The x86-64 Makefile already selects `-m64 -mno-red-zone` for the kernel and
the `i386pep` linker emulation for its boot image. The driver selects a
dedicated no-red-zone LP64 `libgcc` for that build. Applications use x32.

## Verification

Run `bash tests/host.sh` to check host setup and rejection of failed or
corrupt downloads without building a compiler. GitHub Actions builds all
three SDKs on Linux and macOS and runs the smoke tests for each target.
For a manual run, open **Actions → Build SDK → Run workflow** and choose the
GCC and Binutils versions independently from the dropdowns. `latest` selects
the newest supported recipe. Push and pull-request builds use `latest` for
both components. All six OS/architecture combinations use the selected pair;
unsupported versions are rejected before dependency installation. Keep the
workflow's dropdown options in sync when adding recipes to `versions.json`.

The SDK smoke tests cover the three application ABIs, m68k PRG+ELF,
fastcall library selection and GOT/PLT relocations, and x86-64 LP64 and
EFI linking. The x32 shared-library test also checks stack permissions and
GNU RELRO against pTOS's runtime loader requirements.

Kernel builds were exercised on pTOS commit `e83242935290`, with
`virt-m68k-fastcall`, `virt-m68k-cli-elf`, `virt-m68k-aspace`,
`virt-arm-cli`, and `pc-x86_64-desktop-tests`. The ARM suite passed 27 tests
and the x32 suite passed 22, with five shutdown checks each. SDK hello
programs ran in QEMU on ARM, x32 and m68k. The m68k runs exercised plain ELF
and fastcall PRG+ELF. The `virt-m68k-aspace` regression run stopped before the
EmuCON prompt.

## GCC 16.2 MiNT port

`patches/gcc-16.2.0-mint.patch` adapts the C compiler and runtime parts of
CrossMiNT's `gcc-15.2.0-mint-20250810.patch` at revision
`53ff5e25af1cd679bb60d46ab4e808d559ae5af2` to the official GCC 16.2.0 archive.
It retains m68k fastcall, MiNT ELF target registration, compiler runtime and
STABS support. Changes for the other language runtimes are excluded: this SDK
builds C only. GCC 16's upstream libiberty PIC selection and poly-int class
already supersede the corresponding GCC 15 patch hunks. The removed
`diagnostic-color.cc` host portability hunk is not carried over.

Local patches are verified against the checksum in `versions.json`, just like
remote patches. Full compiler and SDK builds, smoke tests and QEMU regression runs have now
passed for m68k, ARM and x32, including a separate m68k fastcall run. Hatari
ROM validation also covers a 192 KB French ST image and a 512 KB STE image. See the
[validation report](validation/gcc-16.2.md) for results, the runtime-discovered
MMIO and ROM alignment fixes, and exact test settings. Source preparation alone does not establish
ABI or runtime correctness.

Validation on 2026-11-11, after pushing the initial port as `cdb2dda`:

- GCC 16.2.0 source patching and pTOS target registration passed for m68k,
  ARM and x32; the offline version-selection tests passed.
- Binutils 2.45, the m68k GCC C compiler, all configured `libgcc` multilibs,
  and the libcmini SDK built successfully with the default build recipe.
- `./tests/smoke.sh /workspace/ptos-gcc16 m68k` passed ELF, PRG+ELF,
  fastcall ABI/library selection and GOT/PLT shared-library checks.
- On pTOS `9193f7c7b`, clean `virt-m68k-cli-elf` and `virt-m68k-fastcall`
  builds passed with `CROSS_COMPILE=m68k-unknown-ptos-prgelf-`,
  `CROSSPREFIX=m68k-unknown-ptos-prgelf-`, `BUILD_TOOLCHAIN_ELF=y` and
  `LDSO_M68K_PREFIX=m68k-unknown-ptos-prgelf-`. The resulting reported RAM
  usage was 625568 and 714580 bytes respectively. These are build results,
  not performance measurements or boot tests.

The first m68k QEMU run exposed a volatile-access regression: a 32-bit read
used as a conditional bit test became a byte-wide memory `btst`, which virtio
MMIO rejects. The GCC 16 patch now excludes volatile memory from the SI-mode
branch bit-test pattern that narrows its operand to QImode. The SDK smoke test
checks the reproducer at `-O2` and `-Os`. GCC 14.3 preserved the full-width load.
