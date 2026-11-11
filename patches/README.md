# CrossMiNT patch archive

These files are unmodified copies of all files in `patches/gcc/` and
`patches/binutils/` from [Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint)
at commit [`53ff5e25af1cd679bb60d46ab4e808d559ae5af2`](https://github.com/th-otto/crossmint/tree/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches),
retrieved on 2026-11-11. This was also the upstream `master` revision at retrieval.
Original filenames, patch contents, copyright notices and license notices are preserved.

`versions.json` selects the active GCC (12 and newer) and Binutils recipes,
including their exact local patch paths and hashes. For each upstream release,
the newest archived snapshot is selected; multiple dated patches for one
version are alternatives, not a patch series. The remaining versions and the
separate fastcall and segment-alignment patches are retained for reference.

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

`SHA256SUMS` records every patch, including the local GCC 16.2 port. Verify the
complete archive from the repository root:

```sh
(cd patches && sha256sum -c SHA256SUMS)
```

The build checks the selected patch hashes independently against `versions.json`
before use. GNU source tarballs and the SDK dependencies retain their existing download behavior.
