# Debian SDK packages

[Debian SDK packages](../.github/workflows/release-deb.yml) runs when a GitHub
release is published, including prereleases. It builds the default GCC and
Binutils recipes from that release's Git tag, together with libgcc, libcmini,
headers and startup objects. It does not rebuild every historical recipe.

## Packages and supported hosts

| Package | Target | SDK prefix |
| --- | --- | --- |
| `ptos-sdk-m68k` | `m68k-unknown-ptos-prgelf` | `/opt/ptos/m68k` |
| `ptos-sdk-arm` | `arm-unknown-ptos-elf` | `/opt/ptos/arm` |
| `ptos-sdk-x86-64` | `x86_64-unknown-ptos-elfx32` | `/opt/ptos/x86_64` |

Starting with Debian version `1.1.0`, each target has the following packages.
The examples use m68k. The other package suffixes are `arm` and `x86-64`.

| Package | Contents and dependencies |
| --- | --- |
| `ptos-binutils-m68k` | Assembler, linker, archive and inspection tools, linker scripts and Binutils support files. |
| `ptos-gcc-m68k` | C and C++ drivers and frontends, compiler support files and all libgcc multilibs. Depends on Binutils at the same Debian version. |
| `ptos-sysroot-m68k` | pTOS C headers, libcmini archives and startup objects for the target ABIs. |
| `ptos-sdk-m68k` | Metapackage that installs all three components at its exact Debian version. |
| `ptos-toolchain` | Metapackage that installs all three target SDKs at its exact Debian version. |

With the [signed APT source](../README.md#ubuntu-2404-and-2604-amd64) configured, use
`sudo apt install ptos-toolchain` for all SDKs or `sudo apt install ptos-sdk-m68k`
for one. Use `sudo apt install ptos-binutils-m68k` for standalone binary tools
or `sudo apt install ptos-gcc-m68k` for freestanding C and C++ with your own
startup and libraries. GCC includes libgcc. The pTOS C sysroot is a separate
package.

The packages run on Linux `amd64` hosts. That is the Debian package
architecture even for the m68k and ARM cross compilers. Builds use
`ubuntu-24.04`; the same binaries are installation-tested on Ubuntu 24.04
and 26.04. Other Ubuntu/Debian versions are not validated and can have
incompatible system library versions.
Runtime dependencies and minimum versions are generated separately for the
Binutils and GCC packages by `dpkg-shlibdeps` from their native host binaries.
The target sysroot has no host-library dependencies.

Each SDK has its own prefix, manuals and support files. Only target-prefixed
command symlinks go into `/usr/bin`, allowing all three packages to coexist.
The SDK package names stay the same across releases. To upgrade an installed
v1.0.3 SDK after the split release is available, run `sudo apt update` and
`sudo apt install ptos-sdk-m68k`, or `sudo apt install ptos-toolchain` for all
targets. The component packages declare `Breaks` and `Replaces` against their
old SDK package for versions below `1.1.0`. This fixed boundary allows dpkg to
transfer ownership of existing toolchain files during the upgrade.

The package version comes from the release tag, independently of GCC's version.
A leading `v` is removed and the first prerelease `-` becomes `~`, so `v1.0.0`
produces `1.0.0` and `v1.1.0-rc1` produces `1.1.0~rc1`. Use numeric version
tags compatible with this convention. Filenames follow
`<package>_<version>_amd64.deb`. Use version `1.1.0` or greater for split
packages, including trial builds.

## Host support and runtime compatibility

| Host (amd64) | Source SDK build CI | Packaging fixtures | Signed published APT installation | Official release build host |
| --- | --- | --- | --- | --- |
| Ubuntu 24.04 | All three targets | Yes | All three SDKs together | Yes |
| Ubuntu 26.04 | All three targets | Yes | The same 24.04-built packages | No |

Source builds run the existing SDK smoke/ABI tests for m68k, ARM and x86_64/x32.
The host and build lanes use explicit runner labels rather than `ubuntu-latest`,
which is migrating between Ubuntu versions. Both hosts use Python virtual
environments for kconfiglib; development dependencies retain the same Ubuntu
package names. The mirror fallback setup is shared across both host versions.

`test-apt.yml` installs the same published release with `signed-by` on fresh
Ubuntu 24.04 and 26.04 runners, verifies exact versions, target prefixes, sysroot
paths and installed smoke tests. It runs on relevant PRs without production
credentials, can be dispatched manually for a tag, and is reused after Pages
publication. PR/push public compatibility checks are pinned to `v1.0.3`. Update that
baseline deliberately before it leaves the public Pages retention window.

Official packages must continue to build on **Ubuntu 24.04**, even when 26.04
source builds pass. Compiling on a newer host can raise glibc/library requirements.
For v0.1.0, all three .deb control records declare:

```text
libc6 (>= 2.38), libgmp10 (>= 2:6.3.0+dfsg), libmpc3 (>= 1.1.0),
libmpfr6 (>= 4.2.0), libzstd1 (>= 1.5.5)
```

These are the recorded package requirements, not a claim of support for every
host satisfying them. `packaging/audit-runtime.py` inspects all installed native
ELF64 amd64 objects with readelf, reports their highest required GLIBC, GLIBCXX
and CXXABI versions, and rejects requirements newer than glibc 2.39 (Ubuntu 24.04).
It excludes target ELF, including x32's ELF32/EM_X86_64, from host analysis.
Dependency and symbol reports are saved as `runtime-ubuntu-24.04` and
`runtime-ubuntu-26.04` workflow artifacts. Actual installation and smoke tests
remain the compatibility check for the full dependency set. The release packager
continues to generate dependencies with dpkg-shlibdeps; no library requirements
or package contents are relaxed to make a newer host pass.

To rerun public compatibility checks after the workflow reaches main:

```sh
gh workflow run test-apt.yml --repo kelihlodversson/pTOS-toolchain \
  --ref main -f release_tag=v1.0.3
```

## Use in pTOS CI

Pin a published toolchain release instead of following `latest`. The following
GitHub Actions step installs the m68k SDK directly from release assets without
configuring the pTOS APT source. Set `TOOLCHAIN_RELEASE` to the desired published
tag. The workflow attaches assets after the installation checks finish.

```yaml
- name: Install the pTOS m68k SDK
  env:
    GH_TOKEN: ${{ github.token }}
    TOOLCHAIN_RELEASE: v1.1.0
  shell: bash
  run: |
    packages="$RUNNER_TEMP/ptos-sdk"
    gh release download "$TOOLCHAIN_RELEASE" \
      --repo kelihlodversson/pTOS-toolchain \
      --pattern 'ptos-*-m68k_*_amd64.deb' --pattern SHA256SUMS \
      --dir "$packages"
    (cd "$packages" && sha256sum --ignore-missing --check SHA256SUMS)
    sudo apt-get update
    sudo apt-get install -y "$packages"/*.deb
```

Use the suffix `arm` or `x86-64` in the pattern for another target. For a split
release, the m68k pattern selects these four files. Pass them in a single APT
invocation:

```sh
sudo apt-get install ./ptos-sdk-m68k_1.1.0_amd64.deb \
  ./ptos-binutils-m68k_1.1.0_amd64.deb ./ptos-gcc-m68k_1.1.0_amd64.deb \
  ./ptos-sysroot-m68k_1.1.0_amd64.deb
```

For all targets, download `*.deb` from one tag into an empty directory and
pass all 13 files together, including `ptos-toolchain`. For GCC without the
sysroot, pass its `ptos-gcc-*` and `ptos-binutils-*` files together. For
Binutils on its own, pass its one file. APT fetches the host-library dependencies
from the normal Ubuntu sources. Keep installing pTOS's other build tools and
Python/kconfiglib as usual. With v1.0.3 and earlier, the per-target pattern
selects its monolithic SDK `.deb`.

For m68k, pTOS builds use:

```sh
make virt-m68k-cli-elf_defconfig
make CROSS_COMPILE=m68k-unknown-ptos-prgelf- \
  CROSSPREFIX=m68k-unknown-ptos-prgelf- BUILD_TOOLCHAIN_ELF=y \
  LDSO_M68K_PREFIX=m68k-unknown-ptos-prgelf-
```

The corresponding ARM and PC compiler prefixes are in the
[main README](../README.md). The existing pTOS `setup-toolchain` action uses
different compiler names; adopting these assets there requires selecting the
pTOS compiler prefixes as well as replacing its downloads. This change adds
the producer workflow and installation instructions in the toolchain repository.

## Build, verification and publication

The workflow builds each SDK once at its final `/opt/ptos/<arch>` prefix. It
records file ownership after the Binutils stage, then builds GCC and the libcmini
sysroot in the same prefix and runs the SDK smoke tests. `package-deb.py` uses
the Binutils manifest and the sysroot location to assign files and their
`/usr/bin` links to components. It strips native host ELF executables and
shared objects, preserves the target libraries, and adds licenses and build
provenance. It normalizes permissions and root ownership without needing root.

Fresh Ubuntu 24.04 and 26.04 runners verify the standalone components and
direct `.deb` installation. The signed test repository includes both the new
packages and the original v1.0.3 assets. Install lanes request only one
`ptos-sdk-*` or only `ptos-toolchain` on a clean system, then exercise upgrading
from v1.0.3. They check aligned versions, package ownership, and full C, C++ and
ABI smoke tests after both installation and upgrade. Publication uploads the
13 Debian packages after these tests pass. The
workflow also builds macOS Homebrew bottles through the reusable Homebrew
workflow. The publication job waits for bottle pouring, smoke tests and strict
linkage checks as well as Debian verification, and uploads both package types
with one combined `SHA256SUMS`. Bottle JSON metadata is included for activation
in the tap; see [Homebrew maintenance](../homebrew/README.md). Reruns replace
assets of the same name.

Each installed package includes `/usr/share/doc/<package>/build-info.json`
with the toolchain commit, target, GCC/Binutils recipes, archive checksums and
source URLs, plus the pinned libcmini revision. Component packages carry their
license texts and the target SDK metapackages carry the smoke tests. Source archives come from the recorded GNU
URLs and libcmini commit; local patches and build scripts are in the recorded
toolchain commit's archive.

For a trial build, use **Actions → SDK release packages → Run workflow** and
enter a Debian package version such as `1.1.0` or `1.2.0~rc1`. This builds and
verifies the Debian packages and macOS bottles and keeps them as workflow
artifacts. Download the Debian artifacts and pass the desired package set
together to `sudo apt-get install` as shown above.

For local assembly after a default SDK build on a Debian/Ubuntu host:

```sh
# Start with an empty directory at the final installation prefix.
prefix=/opt/ptos/m68k
./build.sh m68k "$prefix" binutils
(cd "$prefix" && find . \( -type f -o -type l \) -printf '%P\n' | LC_ALL=C sort) \
  > binutils-m68k.manifest
./build.sh m68k "$prefix" gcc
./build.sh m68k "$prefix" sdk
python3 packaging/package-deb.py m68k "$prefix" 1.1.0 dist \
  --binutils-manifest binutils-m68k.manifest
```

The script needs `dpkg-dev`, native `binutils`, Python 3, the installed SDK and
the source work directory containing its license texts. `PTOS_WORKDIR` or
`--work-dir` selects that directory; it defaults to `.work`. It requires the
SDK's GCC and Binutils versions to match the repository's default recipes.

`python3 tests/test_deb.py` checks actual package assembly, generated host
library dependencies, permissions, target ELF preservation, metadata and
coexistence with small SDK fixtures. Pull requests changing packaging run this
check; full release builds run on publication or manual dispatch.

[Local package validation](../validation/debian-packages.md) also assembled
packages from all three existing GCC 16.2 SDKs and passed their full smoke tests
after extraction and removal of the original test prefixes.

## Signed APT publication through GitHub Pages

After the existing release publication succeeds, official releases also call
[Publish APT repository](../.github/workflows/publish-apt.yml). This reuses the
verified GitHub Release assets and does not compile SDKs. See
[APT repository operations](apt-repository.md) for infrastructure bootstrap,
signing secrets, retention, manual publication, recovery and key rotation.

## All-target metapackage

`ptos-toolchain` is a dependency-only `amd64` package. Its Debian version is the
release tag's normalized version, and it requires each `ptos-sdk-*` package at
exactly that version. It contains only a README and copyright information; the
SDK payload lives in the component packages. Build the all-target metapackage
without compiling anything:

```sh
python3 packaging/package-toolchain.py 1.1.0 dist
```

The APT publisher accepts either historical layout below version 1.1.0
(three monolithic SDK packages, with or without `ptos-toolchain`). For versions
starting at 1.1.0, it requires all thirteen packages. It verifies the checksums,
identities, exact-version dependencies and versioned file takeover rules.
Mixed historical and split releases use the existing retention and grace
policy. Historical assets and their checksums remain intact. Split packaging
applies to Debian/APT. The Homebrew workflow continues to publish SDK bottles.
