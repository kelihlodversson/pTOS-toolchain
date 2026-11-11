# Debian package validation — 2026-11-11

Tested on Debian 13 `amd64` using the existing GCC 16.2.0 / Binutils 2.45
SDKs from the compiler validation. Each target was copied into its own prefix,
packaged, extracted into a shared installation root, and its original test
prefix removed before running the full SDK smoke test.

| Package | Archive bytes | SDK smoke after extraction |
| --- | ---: | --- |
| `ptos-sdk-m68k` | 37048560 | PASS: ELF, PRG+ELF, stack/fastcall, MMIO/ROM reproducers and GOT/PLT |
| `ptos-sdk-arm` | 41593092 | PASS: ELF32 EABI5 hard-float |
| `ptos-sdk-x86-64` | 46084012 | PASS: x32 GCC/as/ld defaults, ELF permissions, LP64 ELF and PE32+ |

All packages used version `0.0.0~validation` and host architecture `amd64`.
Each relocated compiler's `-print-sysroot` resolved inside its extracted SDK.
The generated dependencies were `libc6 (>= 2.38)`, `libgmp10 (>= 2:6.3.0+dfsg)`
and `libzstd1 (>= 1.5.5)` for these existing builds. Release packages will
resolve dependencies from their actual Ubuntu 24.04 builds instead.

`tests/test_deb.py` passed real archive assembly with small fixtures for all
three targets. It checked dependency generation, host architecture metadata,
command links, executable permissions, target ELF preservation, build-info
metadata and coexistence. Invalid package version rejection also passed.
Release tag conversion and Debian prerelease version ordering passed.
The existing version-selection and host/download-failure tests passed, as did
workflow YAML parsing, shell syntax, documentation links and whitespace checks.

This local validation used extracted packages rather than a system-wide apt
installation. The release workflow adds a separate Ubuntu 24.04 runner that
installs all three packages with apt and runs the installed smoke tests through
`/usr/bin` before publication. No GitHub release was created or published during
local validation, and the full release workflow has not yet run.
