# CrossMiNT patch archive

These files are unmodified copies of all files in `patches/gcc/` and
`patches/binutils/` from [Thorsten Otto's CrossMiNT](https://github.com/th-otto/crossmint)
at commit [`53ff5e25af1cd679bb60d46ab4e808d559ae5af2`](https://github.com/th-otto/crossmint/tree/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches),
retrieved on 2026-11-11. This was also the upstream `master` revision at retrieval.
Original filenames, patch contents, copyright notices and license notices are preserved.

The active build uses only:

- `gcc/gcc-14.3.0-mint-20250702.patch`
- `binutils/binutils-2.45-mint-20250812.patch`

The other patches are archived for reference and future version changes. They are
not applied by `build.sh`; the pTOS preparation code is still tied to GCC 14.3.0
and Binutils 2.45. Multiple dated patches for the same version are alternative
snapshots, not a patch series. The separate fastcall and segment-alignment
patches are retained as upstream supplied them.

| Component | Archived release versions |
| --- | --- |
| gcc | 4.6.4, 7.5.0, 8.4.1, 8.5.0, 9.3.1, 9.5.0, 10.4.0, 10.5.0, 11.3.0, 11.4.0, 11.5.0, 12.2.0, 12.3.0, 12.4.0, 13.1.0, 13.2.0, 13.3.0, 13.4.0, 14.1.0, 14.2.0, 14.3.0, 15.1.0, 15.2.0 |
| binutils | 2.39, 2.40, 2.41, 2.42, 2.43, 2.44, 2.45 |

Each local path has the same path relative to the upstream repository. For
example, the source URL of a patch is:

```text
https://raw.githubusercontent.com/th-otto/crossmint/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches/<component>/<filename>
```

`SHA256SUMS` records every archived patch. Verify the complete archive from the
repository root:

```sh
(cd patches && sha256sum -c SHA256SUMS)
```

The build checks the two active patch hashes independently before use. GNU
source tarballs and the SDK dependencies retain their existing download behavior.
