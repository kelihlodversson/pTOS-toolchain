# CrossMiNT patches and local ports

The build uses the local patch paths in [versions.json](../versions.json).
Patch contents and history are tracked in Git, and patches are applied directly
from this checkout. Downloaded GNU source archives are verified against the
SHA-256 checksums in `versions.json`. SDK dependencies retain their existing
download behavior.

## Upstream archive

The `gcc/` and `binutils/` subdirectories contain unmodified copies of all
files in `patches/gcc/` and `patches/binutils/` from
[Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint)
at commit [`53ff5e25af1cd679bb60d46ab4e808d559ae5af2`](https://github.com/th-otto/crossmint/tree/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches),
retrieved on 2026-11-11. This was also the upstream `master` revision at retrieval.
Original filenames, patch contents, copyright notices and license notices are preserved.

For each archived release supported by the build, the newest patch snapshot
at that revision is selected. Multiple dated patches for one version are
alternatives, not a patch series. Patches for older releases and the separate
fastcall and segment-alignment patches are retained for reference. The build
supports GCC 12 and newer.

| Component | Archived release versions |
| --- | --- |
| gcc | 4.6.4, 7.5.0, 8.4.1, 8.5.0, 9.3.1, 9.5.0, 10.4.0, 10.5.0, 11.3.0, 11.4.0, 11.5.0, 12.2.0, 12.3.0, 12.4.0, 13.1.0, 13.2.0, 13.3.0, 13.4.0, 14.1.0, 14.2.0, 14.3.0, 15.1.0, 15.2.0 |
| binutils | 2.39, 2.40, 2.41, 2.42, 2.43, 2.44, 2.45 |

Each archived patch has the same path relative to the upstream repository.
For example, its source URL is:

```text
https://raw.githubusercontent.com/th-otto/crossmint/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches/<component>/<filename>
```

## Local ports

`prepare.py` also applies the m68k MOVE dependency fix for
[issue #15](https://github.com/kelihlodversson/pTOS-toolchain/issues/15)
to every supported GCC recipe. Integer and single-precision MOVE patterns
reject a source pre-decrement or post-increment register that also occurs
in the destination address. This prevents late combining from changing
the destination effective address while retaining valid auto-inc-dec
instructions. See the [validation report](../validation/m68k-auto-inc-dec.md).

The patches at this directory's root extend the archived patches to newer
GNU releases. Their archived source patches remain unchanged. All five ports
are selectable with `--gcc` and in the manual CI dropdown; GCC 16.2.0 remains
the default.

| Local patch | Archived CrossMiNT source patch |
| --- | --- |
| [gcc-12.5.0-mint.patch](gcc-12.5.0-mint.patch) | [gcc-12.4.0-mint-20240810.patch](gcc/gcc-12.4.0-mint-20240810.patch) |
| [gcc-13.5.0-mint.patch](gcc-13.5.0-mint.patch) | [gcc-13.4.0-mint-20250702.patch](gcc/gcc-13.4.0-mint-20250702.patch) |
| [gcc-14.4.0-mint.patch](gcc-14.4.0-mint.patch) | [gcc-14.3.0-mint-20250702.patch](gcc/gcc-14.3.0-mint-20250702.patch) |
| [gcc-15.3.0-mint.patch](gcc-15.3.0-mint.patch) | [gcc-15.2.0-mint-20250810.patch](gcc/gcc-15.2.0-mint-20250810.patch) |
| [gcc-16.2.0-mint.patch](gcc-16.2.0-mint.patch) | [gcc-15.2.0-mint-20250810.patch](gcc/gcc-15.2.0-mint-20250810.patch) |

### GCC 12–15 bugfix releases

The GCC 12.5, 13.5, 14.4 and 15.3 ports retain the full original patch
contents, including other language runtime changes, although this SDK builds
C only. GCC 12–14 required only context rebasing. GCC 15.3's
`libstdc++-v3/include/bits/chrono_io.h` needed six remaining `__out` identifiers
renamed after three hunks encountered upstream context changes. This preserves
the existing rename while retaining the upstream chrono updates.

The GCC 12 patch provides only the stack ABI; `-mfastcall` and its multilibs
require GCC 13 or newer. Smoke validation follows the available ABI variants:
GCC 12 checks the stack ABI, while GCC 13–15 must pass both stack and fastcall
checks. All four passed the volatile-long MMIO and masked-byte ROM access
reproducers at `-O2` and `-Os`, without additional backports of the GCC 16 fixes.

On pTOS `9193f7c7b`, all four m68k compiler, libgcc and SDK builds passed
smoke tests, 26 QEMU regression suites, four shutdown probes and the scalable
system-font replay. Hatari ROM results were:

| GCC | ROM | Hatari suites | Free bytes within ROM limit |
| --- | --- | --- | ---: |
| 12.5.0 | US 512 KB, STE high resolution | 29 passed, 0 failed | 109396 |
| 13.5.0 | French 192 KB, ST low resolution | 20 passed, 0 failed | 8400 |
| 14.4.0 | French 192 KB, ST low resolution | 20 passed, 0 failed | 7570 |
| 15.3.0 | French 192 KB, ST low resolution | 20 passed, 0 failed | 6334 |

The French 192 KB configuration uses stock `-Os`, LTO and fastcall settings.
GCC 12 used the stock US 512 KB configuration because the 192 KB configuration
requires fastcall. No ROM feature selection was reduced to fit the images.

Source preparation passed for m68k, ARM and x32. Full compiler and runtime
validation for these four releases covered m68k on Linux; ARM, x32 and macOS
builds were not run. See the [validation report](../validation/gcc-12-15.md)
for exact settings, results and image checksums.

### GCC 16.2

The GCC 16.2 patch ports the C compiler and runtime parts of the GCC 15.2
CrossMiNT patch to the official GCC 16.2.0 archive. It retains m68k fastcall,
MiNT ELF target registration, compiler runtime and STABS support. Other
language runtime changes are excluded because this SDK builds C only.
GCC 16's upstream libiberty PIC selection and poly-int class supersede the
corresponding GCC 15 patch hunks. The removed `diagnostic-color.cc` host
portability hunk is not carried over.

Runtime validation exposed two compiler faults, fixed in this local patch:

- The SI-mode branch bit-test pattern could replace a volatile 32-bit MMIO
  load with a byte memory `btst`. It now rejects volatile memory operands,
  preserving the full-width load required by virtio MMIO.
- The RTL lowpart helper could widen a masked byte read to a longword read
  starting three bytes earlier, causing an address error on the 68000. It now
  rejects widening a memory object or changing a volatile access's width.

The SDK smoke tests cover both reproducers at `-O2` and `-Os`, including both
calling conventions for the ROM byte-access check. No optimization-disabling
build flag was needed for the successful runtime runs.

Compiler and SDK builds, smoke tests and QEMU regressions passed for m68k,
ARM and x32, including separate m68k stack and fastcall runs. Hatari passed
20 suites on the French 192 KB ST ROM and 29 on the US 512 KB STE ROM, with
6876 and 90506 bytes free respectively. See the
[validation report](../validation/gcc-16.2.md) for compiler-fault reproducers,
exact build settings, suite counts and image checksums.
