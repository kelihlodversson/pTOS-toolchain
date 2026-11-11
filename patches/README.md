# CrossMiNT patches and local ports

The `gcc/` and `binutils/` subdirectories contain unmodified copies of all
files in `patches/gcc/` and `patches/binutils/` from
[Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint)
at commit [`53ff5e25af1cd679bb60d46ab4e808d559ae5af2`](https://github.com/th-otto/crossmint/tree/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches),
retrieved on 2026-11-11. This was also the upstream `master` revision at retrieval.
Original filenames, patch contents, copyright notices and license notices are preserved.

`versions.json` selects the active GCC (12 and newer) and Binutils recipes,
including their exact local patch paths and source archive checksums. For each
upstream release, the newest archived snapshot is selected; multiple dated patches for one
version are alternatives, not a patch series. The remaining versions and the
separate fastcall and segment-alignment patches are retained for reference.

The local ports in this directory add the following GCC releases. Their
archived source patches remain unchanged.

| Local patch | Archived CrossMiNT source patch |
| --- | --- |
| [gcc-12.5.0-mint.patch](gcc-12.5.0-mint.patch) | [gcc-12.4.0-mint-20240810.patch](gcc/gcc-12.4.0-mint-20240810.patch) |
| [gcc-13.5.0-mint.patch](gcc-13.5.0-mint.patch) | [gcc-13.4.0-mint-20250702.patch](gcc/gcc-13.4.0-mint-20250702.patch) |
| [gcc-14.4.0-mint.patch](gcc-14.4.0-mint.patch) | [gcc-14.3.0-mint-20250702.patch](gcc/gcc-14.3.0-mint-20250702.patch) |
| [gcc-15.3.0-mint.patch](gcc-15.3.0-mint.patch) | [gcc-15.2.0-mint-20250810.patch](gcc/gcc-15.2.0-mint-20250810.patch) |

These four ports retain the full original patch contents, including language
runtime changes, although this SDK builds C only. GCC 12–14 required only
context rebasing. GCC 15.3's chrono header needed the existing `__out` rename
carried across three upstream context changes. The GCC 12 patch provides only
the stack ABI; fastcall requires GCC 13 or newer.

All four passed source preparation for m68k, ARM and x32, plus m68k compiler,
SDK, QEMU and Hatari validation on Linux. The French 192 KB ROM passed with
GCC 13–15; GCC 12 used the US 512 KB ROM. See the
[bugfix-release validation report](../validation/gcc-12-15.md) for results
and the limits of that validation.

`gcc-16.2.0-mint.patch` is the locally maintained C compiler/runtime port of the
GCC 15.2 CrossMiNT patch, with the volatile MMIO and ROM alignment fixes found
during validation. See [the validation report](../validation/gcc-16.2.md).
It is the default GCC recipe; it is not an unmodified upstream archive copy.

| Component | Archived release versions |
| --- | --- |
| gcc | 4.6.4, 7.5.0, 8.4.1, 8.5.0, 9.3.1, 9.5.0, 10.4.0, 10.5.0, 11.3.0, 11.4.0, 11.5.0, 12.2.0, 12.3.0, 12.4.0, 13.1.0, 13.2.0, 13.3.0, 13.4.0, 14.1.0, 14.2.0, 14.3.0, 15.1.0, 15.2.0 |
| binutils | 2.39, 2.40, 2.41, 2.42, 2.43, 2.44, 2.45 |

Each archived upstream patch has the same path relative to the upstream
repository. For example, the source URL of a patch is:

```text
https://raw.githubusercontent.com/th-otto/crossmint/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches/<component>/<filename>
```

Patch contents and their history are tracked in Git. The build applies the
selected local patch directly; no separate patch checksum manifest is needed.
Downloaded GNU source archives are still verified against the SHA-256 checksums
in `versions.json`. SDK dependencies retain their existing download behavior.
