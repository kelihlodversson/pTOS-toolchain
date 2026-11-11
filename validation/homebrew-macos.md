# Local Homebrew SDK validation

Validated on 2026-11-11 using the `feat/homebrew-tap` branch and a local
`kelihlodversson/ptos-dev` tap cloned from that checkout.

## Host and sources

- Apple Silicon (`arm64`), macOS 26.5.1.
- Homebrew 7.0.11, Xcode 26.6 and Command Line Tools 26.6.
- GCC 16.2.0, Binutils 2.45 and libcmini
  `c85f67a52679b68782c49fd967732d14bfe87841`.
- SDK recipe snapshot: `bb00f4c276504cc80cc20fd2e9235621c6f9e3ba`.
- Native libraries: GMP 6.3.0, MPFR 4.2.2, MPC 1.4.1, ISL 0.28 and
  zstd 1.5.7. Build configuration uses Python 3.13.18.

The original local CLT 15.3 installation prevented Homebrew source builds.
After user approval, macOS Software Update installed only the offered CLT
26.6 update. Homebrew's dependency update also upgraded Python 3.13; the
previous generic Python command names were restored using its `libexec/bin`
entry points after the versioned formula stopped linking them globally.

## Installation and tests

All three SDKs were built from source through Homebrew, installed into their
own Cellar prefixes and linked into `/opt/homebrew/bin`. ARM was additionally
reinstalled to exercise the plugin filename fix.

```sh
brew tap kelihlodversson/ptos-dev /path/to/pTOS-toolchain
brew install --build-from-source kelihlodversson/ptos-dev/ptos-arm
brew install --build-from-source kelihlodversson/ptos-dev/ptos-m68k
brew install --build-from-source kelihlodversson/ptos-dev/ptos-x86_64
```

| Formula | Installed GCC | Installed ABI smoke test |
| --- | --- | --- |
| `ptos-arm` | 16.2.0 | Passed: ELF32 EABI5 hard-float |
| `ptos-m68k` | 16.2.0 | Passed: ELF, PRG+ELF, fastcall and GOT/PLT shared libraries |
| `ptos-x86_64` | 16.2.0 | Passed: x32 GCC/as/ld defaults, LP64 ELF and PE32+ EFI |

All installed SDKs passed the following checks with the final formula
declarations and test hook:

```sh
for arch in arm m68k x86_64; do
  brew test --verbose "kelihlodversson/ptos-dev/ptos-$arch"
  brew linkage --test --strict "kelihlodversson/ptos-dev/ptos-$arch"
  brew audit --strict "kelihlodversson/ptos-dev/ptos-$arch"
done
```

Homebrew style checks passed for the three formula files and their shared
Ruby implementation. All three globally linked GCC drivers report 16.2.0.

## Simultaneous installation

After all packages were installed, each was unlinked, then all three were
linked again without overwriting any files. All three installed smoke tests
and linkage checks passed again afterward.

The shared BFD plugin directory contains three distinct links:

```text
ptos-arm-libdep.so
ptos-m68k-libdep.so
ptos-x86_64-libdep.so
```

## Issues found and fixed

1. Binutils installs a common `libdep.so` filename. Namespace it by formula,
   preserving BFD's directory-based plugin discovery. Common Info manuals
   and section 7 man pages also remain in formula-specific directories.
2. Versioned Python places `python3` in `libexec/bin`, not `bin`. Put that
   directory on the build PATH. The x86-64 source build exercised this
   refinement of the shared setup; the ARM and m68k source builds preceded it.
3. `brew test` injects native macOS headers through `CPATH`. The m68k test
   failed with `Unsupported architecture` inside the macOS SDK, while the
   installed compiler passed outside that environment. Clear native include,
   library and SDK environment overrides only in the cross-test hook. Both
   m68k and ARM then passed through Homebrew, followed by x86-64.
4. Native compiler binaries had automatically linked ISL and zstd, and some
   Binutils binaries linked Flex's library. Declare those runtime dependencies
   and use strict linkage checking in CI. The final declarations were checked
   against the actual installed Mach-O dependencies without recompiling the
   unchanged binaries for this metadata correction.

These results cover local Apple Silicon source installations and static ABI
smoke checks. They do not cover bottles, bottle relocation, Intel hosts or
Linuxbrew, and do not replace pTOS runtime tests in QEMU or on hardware.
