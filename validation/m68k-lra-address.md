# m68k LRA address displacement — pTOS#998

## Cause and fix

GCC 16.2.0 with `-mlra` crashes compiling
`thread_startup_prepare_outputs` from pTOS PR #998 (`c298949a9`), at `-Os`,
`-m68000`, `-mfastcall`, `-msoft-float`, and `-fomit-frame-pointer`.
The reload allocator compiles the same preprocessed translation unit.

The failing RTL is a LEA of `sp + d6 + 128`. LRA's `decompose_lea_address`
uses `VOIDmode`, and `m68k_decompose_address` used its size (zero) for
`reach`. Consequently `IN_RANGE (offset, -128, 128 - reach)` accepted 128.
The later QImode check in postreload rejects the same address and ICEs.
This also explains the standalone reproducer's failure in the assembler
printer, which checks an inline asm address with QImode.

The GCC 16.2 patch sets `reach` to one for `VOIDmode`, as it already does
for `BLKmode`. The displacement must itself fit even when no memory is
accessed. LRA can then repair the invalid address. The same correction also
applies to the signed-word base displacement limit. Memory-mode checks and
the allocator selection are unchanged.

## Reproduction

The installed SDK's GCC 16.2.0 fails on `tests/m68k-lra-address.c` with:

```sh
m68k-unknown-ptos-prgelf-gcc -m68000 -mlra -Os \
    -c tests/m68k-lra-address.c -o address.o
```

It reports an ICE in `print_operand_address`. The original pTOS translation
unit reports `insn does not satisfy its constraints` in postreload for
`*lea` with displacement 128.

Run the boundary regression using a rebuilt compiler:

```sh
python3 tests/m68k_lra_address.py /path/to/m68k-unknown-ptos-prgelf-gcc
```

The test compiles and assembles both 127 and 128 with `-mlra`, five CPU
variants (68000, 68010, 68020, 68040, 68060), `-Os`/`-O2`, and stack/fastcall
ABIs. It is included in the GCC 16 smoke tests.

## Validation results (2026-11-17)

- Applied the complete updated patch to the checksum-verified official
  GCC 16.2.0 archive; the patched backend matches the tested source.
- Built a C-only m68k pTOS cross compiler with the updated backend
  (`--disable-multilib`, host compilation at `-O0`; no runtime rebuild).
- Standalone regression: all 40 compile/assemble checks passed.
- Original preprocessed `thread_startup.c` from PR #998: all 20 combinations
  of the five CPUs, two optimization levels and two ABIs compiled and
  assembled with `-mlra`, `-msoft-float`, `-fomit-frame-pointer`,
  `-fno-common`, `-fno-tree-loop-distribute-patterns` and
  `-fno-builtin-strlen`.
- Existing `m68k_auto_inc_dec.py` and `m68k_reload_const_modes.py` assembly
  regressions passed with the rebuilt compiler.
- Python discovery: 45 tests passed; five packaging tests could not run
  because `apt-ftparchive` is missing from the environment. All five m68k
  checker unit tests passed separately.
- Shell syntax and `git diff --check` passed.

No complete SDK, ROM build or emulator suite was run. This change fixes
GCC 16.2's compiler crash; it does not establish that all LRA-generated
pTOS code passes runtime tests or enable LRA by default.

## macOS patch application follow-up

The macOS m68k builder rejected the LRA hunk before compiling GCC. The
hunk had trailing context but no leading context. Apple's `patch_match`
implementation treats that asymmetry as a beginning-of-file change and
rejects a match elsewhere, unlike GNU patch. Restore three leading context
lines around the existing change; the patched compiler source is unchanged.

Source preparation with the complete patch passed again for m68k, ARM and
x86-64 using the verified GCC 16.2.0 archive and GNU patch, and all 40 LRA
compile/assemble checks passed. Native macOS patch application is checked
by the PR's macOS build.
