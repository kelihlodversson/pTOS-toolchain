# pTOS toolchain

This C SDK builds pTOS programs and freestanding kernels. It builds native
GCC and GNU Binutils targets, together with `libgcc`, libcmini headers and
archives, and pTOS program startup objects. The default is the newest configured
GCC and Binutils release (GCC 16.2.0 and Binutils 2.45). Downloaded source
archives are verified with SHA-256.

| Target | Default output | Additional mode |
| --- | --- | --- |
| `m68k-unknown-ptos-prgelf` | Big-endian ELF32, 68000 cdecl | `-mmintelf` for MiNT PRG+ELF, `-mfastcall` for register arguments |
| `arm-unknown-ptos-elf` | Little-endian ELF32, ARMv6K ARM state, AAPCS hard-float | `-march`, `-mcpu` and `-mfpu` for pTOS's newer ARM boards |
| `x86_64-unknown-ptos-elfx32` | Little-endian ELF32, `EM_X86_64` x32 (ILP32) | `-m64` for freestanding LP64, `ld -m i386pep` for the UEFI kernel image |

The `-mmintelf` option changes the linker emulation. Object files are ELF in
both modes, and `-mfastcall` selects its own compiler runtime and libcmini
variant. GCC 12 supports the stack ABI only; `-mfastcall`
and its multilibs require GCC 13 or newer. Link together objects that agree on
the m68k calling convention.
The ordinary ELF mode also supports `-fPIC -shared` with a GOT and PLT.

## Debian/Ubuntu release packages

Publishing a GitHub release builds `amd64` host packages for all three targets:
`ptos-sdk-m68k`, `ptos-sdk-arm` and `ptos-sdk-x86-64`. Each contains GCC,
Binutils, libgcc, libcmini and startup objects. Packages are built on Ubuntu
24.04 and tested together on a fresh runner before being attached to the
release with `SHA256SUMS`. The same signed release packages are installation-tested
on Ubuntu 24.04 and 26.04 amd64; official builds remain pinned to 24.04 to preserve
the older host-library baseline. See the [host support matrix](packaging/README.md#host-support-and-runtime-compatibility).

Download the required `.deb` from a published release and install it with:

```sh
sudo apt-get install ./ptos-sdk-m68k_*_amd64.deb
```

The SDKs install under `/opt/ptos/<target-arch>` and expose their target-prefixed
commands in `/usr/bin`, so no PATH change is needed and all three can coexist.
Use the compiler prefixes shown below when building pTOS. The packages provide
the SDK; Make, Python and kconfiglib are still needed to build pTOS itself.
See [Debian packaging](packaging/README.md) for a pinned-release pTOS CI example,
release version rules and manual package builds.

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
the newest entry. GCC 12 and newer are supported. List the available versions
without downloading or building anything:

```sh
./build.sh --list-versions
./build.sh m68k "$HOME/opt/ptos-gcc14" --gcc 14.4.0 --binutils 2.45
./build.sh all "$HOME/opt/ptos-gcc15" gcc --gcc 15.3.0
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
With the source archives already cached, run
`python3 tests/prepare_versions.py /path/to/downloads` to verify archive
checksums, patch application and pTOS source preparation for every supported
release and target. This checks source preparation; it does not compile the toolchains.

### CI coverage

The Build SDK workflow runs lightweight host/download checks and offline version
tests on explicit Ubuntu 24.04 and 26.04 runners. macOS checks run inside the compiler and Homebrew
jobs when those jobs are needed. Full compiler
builds for all three targets run when SDK inputs change, including build scripts,
version recipes, patches, sysroot files and SDK smoke tests. Homebrew-only,
Debian-packaging-only and documentation changes skip these compiler builds.
Changes to the build workflow or its path classifier, and unknown paths, default
to full builds. Manual dispatch always builds the requested GCC/Binutils pair.
Ubuntu builds use explicit 24.04 and 26.04 matrices, with one parallel job per target on each host. macOS uses one job that builds
and tests all three targets sequentially, freeing each target's build tree
after its tests to limit disk usage.

Homebrew changes build and test all three formulae and bottles sequentially in
one macOS job, including simultaneous installation checks. They use
the formulae's pinned SDK sources, so they do not replace compiler tests of the
current checkout. Releases build Debian packages and Homebrew bottles through
the release workflow without an additional plain SDK build matrix.

### macOS

The repository also provides a Homebrew tap with one formula per target:

```sh
brew tap kelihlodversson/ptos-toolchain https://github.com/kelihlodversson/pTOS-toolchain.git
brew install kelihlodversson/ptos-toolchain/ptos-m68k
brew install kelihlodversson/ptos-toolchain/ptos-arm
brew install kelihlodversson/ptos-toolchain/ptos-x86_64
```

Each formula builds GCC 16.2.0, Binutils 2.45 and the libcmini SDK from
checksum-pinned sources. The release workflow also publishes tested macOS
bottles and their metadata alongside the Debian packages, then automatically
opens an activation PR with the formula bottle blocks and tests installation
from the release. Merge that PR to enable bottles; until then, installation
builds from source. The target-prefixed commands are linked into Homebrew's `bin`
directory, and the three SDKs can be installed together. Run `brew test
ptos-arm` (or the other formula name) to run the installed SDK's ABI smoke
tests. See [Homebrew maintenance](homebrew/README.md) for local development.

To build directly from this checkout instead of using a formula:

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

Runtime validation results and exact test settings are recorded in the
[GCC 12–15 report](validation/gcc-12-15.md) and
[GCC 16.2 report](validation/gcc-16.2.md), including QEMU regression tests
and Hatari ROM tests.

## Patches

The m68k fastcall and MiNT PRG+ELF support comes from
[Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint). Upstream
patches are archived in this repository at a pinned revision and applied
directly from Git.

Local additions port the MiNT patches to GCC 12.5.0, 13.5.0, 14.4.0, 15.3.0
and 16.2.0. The GCC 16.2 port also fixes volatile MMIO access width and ROM
byte-access alignment. See [patches/README.md](patches/README.md) for patch
provenance, local changes and validation details.

<a id="install-the-sdk-with-apt-ubuntu-2404-amd64"></a>

## Install the SDK with APT (Ubuntu 24.04 and 26.04, amd64)

The signed APT service at `https://apt.ptos.dev` is live. See
[APT maintenance](packaging/apt-repository.md) for operational details. GitHub Pages hosts
a bounded set of recent stable versions; GitHub Releases archive every version.

```sh
curl -fsSL https://apt.ptos.dev/ptos-archive-keyring.gpg |
  sudo tee /usr/share/keyrings/ptos-archive-keyring.gpg >/dev/null
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/ptos-archive-keyring.gpg] https://apt.ptos.dev stable main' |
  sudo tee /etc/apt/sources.list.d/ptos.list
sudo apt update
sudo apt install ptos-sdk-m68k ptos-sdk-arm ptos-sdk-x86-64
```

Install only the target you need with `sudo apt install ptos-sdk-m68k`,
`sudo apt install ptos-sdk-arm`, or `sudo apt install ptos-sdk-x86-64`.
All three packages run on an amd64 Linux host and can coexist. Their compiler
prefixes and installation directories are listed in [packaging](packaging/README.md).
