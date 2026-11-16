# m68k reload sharing of equal constants in different modes

Tracked in [issue #18](https://github.com/kelihlodversson/pTOS-toolchain/issues/18).

GCC 16.2 (SDK 1.0.0) miscompiles libcmini's `Fseek(0, handle, 0)` binding
when the function is under register pressure. `trap_1_wlww` passes a `long`
zero and a `short` zero as two `"r"` inputs of one asm. The emitted code
clears only the low word of the register that the asm then pushes as the
longword offset:

```asm
	clr.w %d3
	move.w %d3,-(%sp)      | mode
	move.w %d7,-(%sp)      | handle
	move.l %d3,-(%sp)      | offset: upper word is stale
	move.w #66,-(%sp)
	trap #1
```

In the pTOS `pclone` regression on `virt-m68k-aspace`, `%d3` still held
`&report` from the preceding `Fread` in the loop. The seek went to
`&report & 0xffff0000`, and the suite corrupted its test file and failed.

## Root cause

Both inputs are spilled pseudos with `REG_EQUIV (const_int 0)`, so reload
creates one input reload per operand. `reload_reg_free_for_value_p` lets
reloads share a hard register when `rtx_equal_p` finds that they load the
same value. A `CONST_INT` has VOIDmode, so an SImode and an HImode reload of
zero compare equal. Both reloads therefore get `%d3`:

```
(set (reg:SI 3 %d3) (const_int 0))
(set (reg:HI 3 %d3) (const_int 0))
(parallel [(set (reg:SI 0 %d0) (asm_operands ... (reg:SI 3 %d3) ... (reg:HI 3 %d3)))])
```

rtl.texi specifies that a SET of a register in a narrower mode leaves the
rest of the register undefined, so the SImode operand is already undefined
here. The machine instructions still happen to work until later passes act on
those semantics:

- Postreload turns the HImode load into `(set (reg:HI 3) (reg:HI 3))`.
- `late_combine2` substitutes the SImode clear into that move and deletes the
  clear, leaving `clr.w`. A debug counter isolates this:
  `-fdbg-cnt=late_combine:234` passes and `:235` fails.

`-fno-late-combine-instructions` and `-mlra` both avoid the fault, but the
invalid RTL comes from reload. REG and MEM values do not hit this case,
because `rtx_equal_p` compares their modes.

## Fix

`prepare.py` adds one condition to `reload_reg_free_for_value_p` in
`gcc/reload1.cc`. Another reload's input counts as the same value only if
both reloads use the same mode. Otherwise the two reloads conflict as usual
and get separate registers. The change makes reload choose registers more
conservatively, and it never turns a previously valid allocation into an
invalid one. Only m68k builds apply it; the ARM and x86-64 compilers use LRA.

With the fix, the reproducer loads the two zeros into separate registers,
each in its own mode.

## Local checks

- Built the GCC 16.2 C compiler (`all-gcc`) from the SHA-256-verified
  official archive, with the repository's CrossMiNT patch and `prepare.py`
  m68k preparation. Host compilation used `-O0 -g0`. Tests used the SDK
  1.0.0 driver, assembler, linker and libgcc, with `-B` selecting the new
  `cc1`.
- `tests/m68k-reload-const-modes.c` reproduces the fault in all 12
  combinations: 68000/68020/68040, `-Os`/`-O2`, stack/fastcall. The
  assembly check fails on the SDK 1.0.0 compiler, and on the locally built
  compiler with the `reload1.cc` change reverted. Under QEMU, the
  freestanding runtime check fails all six `-O2` combinations with the SDK
  1.0.0 compiler. Its trampoline puts `0x5a5a5a5a` into every register
  before the call. At `-Os` the stale register happens to have a clear
  upper word, so only the assembly check detects those builds.
- With the fix, all 12 combinations pass the assembly and runtime checks
  under QEMU user emulation, and the issue #15 copy regression still passes
  all 12.
- The replaced `reload1.cc` text matches all 17 supported recipes, 12.2.0
  through 16.2.0, and no CrossMiNT patch changes that file.
- On pTOS `4079d20` (`virt-m68k-aspace_defconfig`), every object was built
  with the fixed compiler and pTOS's `-fno-late-combine-instructions`
  workaround for `pclone.o` was removed. The QEMU regression passed 29 of
  29 suites and all five shutdown checks. Of the 251 objects, only
  `pclone.o` disassembles differently from the SDK 1.0.0 build. In it, the
  `Fseek` offset now gets `clr.l` and the mode a separate `clr.w`.
- Checker unit tests, host checks, version-selection, CI change-filter,
  Debian packaging and bottle tests pass.

The regression is part of SDK smoke testing. Linux build CI also runs the
runtime check under `qemu-m68k`. To run it against an SDK:

```sh
python3 tests/m68k_reload_const_modes.py /path/to/sdk/bin/m68k-unknown-ptos-prgelf-gcc --runner qemu-m68k
```

Use a fresh `PTOS_WORKDIR` so a prepared source tree does not keep the old
`reload1.cc`. Existing published packages are unchanged.
