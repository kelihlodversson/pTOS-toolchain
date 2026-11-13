# m68k MOVE address dependency regression

Tracked in [issue #15](https://github.com/kelihlodversson/pTOS-toolchain/issues/15).

GCC 16.2 can compile the reported volatile copy loop to:

```asm
move.l (%a0)+,(%a0,%d0.l)
```

The source increments A0 before MOVE calculates the destination address,
displacing every store by four bytes. RTL dumps show a valid auto-inc-dec
transformation followed by a memory-to-memory combination. The later
`late_combine2` pass substitutes the destination address calculation into
that MOVE after register allocation. The m68k instruction recognizer
previously accepted the resulting dependency.

`prepare.py` now adds `m68k_move_operands_p` to the backend and checks it
in the ten QI, HI, SI and SF MOVE patterns, including ColdFire variants.
It rejects memory-to-memory moves when a source PRE_DEC or POST_INC
updates a register used in the destination address. The ordinary
register-overlap helper recognizes registers by number, including indexed
destination addresses. Valid auto-inc-dec instructions remain enabled.

The fixed integer loop retains auto-increment and computes the destination
address first:

```asm
lea (%a0,%d0.l),%a1
move.l (%a0)+,(%a1)
```

## Local checks

- Built the GCC 16.2 C compiler from the SHA-256-verified official archive,
  with the repository's CrossMiNT patch and target preparation. Host
  compilation used `-O0 -g0` for the final compiler objects; target tests
  used the optimization settings below. This was a compiler-only build,
  with existing GNU m68k Linux Binutils 2.44 for freestanding test linking.
- Before the backend fix, the reported unsafe MOVE was present and the
  freestanding runtime copy check exited with status 1 under QEMU/m68k.
- With the fix, all 12 combinations passed assembly and runtime checks:
  68000/68020/68040, `-Os`/`-O2`, stack/fastcall. Each configuration used
  `-msoft-float -fomit-frame-pointer -fauto-inc-dec` and exercised byte,
  word, longword and single-precision copies in both directions: 96 copy
  checks in total. Tests verify copied data, destination guard regions
  and preservation of source contents. QEMU user emulation was 10.0.13.
- Applied the backend preparation helper successfully to pristine backend
  sources for all 17 GCC recipes, from 12.2.0 through 16.2.0. Each matched
  all ten guarded MOVE patterns. GCC 14.3's existing CrossMiNT compiler
  passed the original six integer assembly checks before the fix. The
  shared backend gap is guarded on every supported version; reproducing
  this optimizer path and rebuilding older versions remain separate checks.
- Host/download checks, version-selection tests, CI change-filter tests
  and assembly-checker tests passed.

The regression is part of SDK smoke testing. Linux build CI additionally
requires the freestanding runtime check via `qemu-m68k`; macOS runs the
assembly check. GCC 12 uses its supported stack ABI only.

For a local SDK build, use a fresh `PTOS_WORKDIR` so an existing prepared
source tree does not retain the old backend. Run:

```sh
python3 tests/m68k_auto_inc_dec.py /path/to/sdk/bin/m68k-unknown-ptos-prgelf-gcc --runner qemu-m68k
```

Full SDK/package rebuilds and pTOS kernel/MMU regression runs were not
performed in this validation. Existing published packages are unchanged.
