# GCC 16.2 validation — 2026-11-11

Tested on pTOS `9193f7c7b`, using GCC 16.2.0, Binutils 2.45 and libcmini
`c85f67a52679b68782c49fd967732d14bfe87841`. Host GCC was Debian 14.2.0;
QEMU was Debian 10.0.13. Tests used separate pTOS worktrees.

The initial compiler port (`cdb2dda`) was pushed before any pTOS build test.
The runtime-discovered MMIO fix (`03bc00a`) was likewise pushed before the
corrected pTOS runtime runs.

## Results

| Target/configuration | Compiler, libgcc, SDK | SDK smoke | QEMU regression suites | Shutdown checks | Scalable system-font replay |
| --- | --- | --- | --- | --- | --- |
| m68k, `virt-m68k-cli-elf` | PASS | PASS | 26 passed, 0 failed | 4 passed | PASS |
| m68k, `virt-m68k-cli-fastcall` + ELF loader | PASS | PASS | 26 passed, 0 failed | 4 passed | PASS |
| ARM, `virt-arm-cli` | PASS | PASS | 27 passed, 0 failed | 4 passed | PASS |
| x32, `pc-x86_64-desktop-tests` | PASS | PASS | 21 passed, 0 failed | 4 passed | PASS |

The suite counts are the runner's reported passed suites; architecture- and
configuration-specific SKIPs are not counted as passes. The runner labels the
four shutdown probes plus the system-font replay as “shutdown checks: 5 passed”.
The probes cover poweroff, reboot, cold boot and halt, including flushing the
file left open by the probe. The font replay runs the regression suite again.

SDK smoke covers m68k ELF/PRG+ELF, fastcall attributes and library selection,
GOT/PLT, ARM ELF32 EABI5 hard-float, x32 GCC/as/ld defaults, non-executable
stack and RELRO, and LP64 ELF/PE32+ linking. All configured m68k libgcc multilibs
and the x32 LP64 no-red-zone multilib built. These results are QEMU validation,
not hardware testing or a performance comparison against GCC 15.

## Runtime-discovered compiler fix

The original GCC 16.2 port failed to discover m68k virtio devices. QEMU reported
`virtio_mmio_read: wrong size access to register!`. This reproducer shows why:

```c
extern void use(void);
void probe(volatile unsigned long *p)
{
    if (*p & 0x01000000UL)
        use();
}
```

With `-O2 -m68020`, the original compiler generated a byte memory `btst` for the
32-bit volatile load. GCC 14.3 generated a full-width load. The SI-mode branch
bit-test pattern now rejects volatile memory operands, so GCC 16.2 preserves
the `move.l` load. The new smoke regression fails with the original compiler
and passes with the fix at both `-O2` and `-Os`. Rebuilding the kernel with that
compiler restored virtio and allowed the complete m68k runtime tests to pass.

## Build and runner settings

Toolchains were built with `build.sh` (Binutils, GCC and SDK stages) into
`/workspace/ptos-gcc16`, with the cached official archives and local patch.
The compiler build used locally unpacked MPFR/MPC headers and bison/flex/m4.
The SDK builds used the existing Python environment with kconfiglib.

pTOS build overrides:

- m68k: `CROSS_COMPILE=m68k-unknown-ptos-prgelf-`,
  `CROSSPREFIX=m68k-unknown-ptos-prgelf-`, `BUILD_TOOLCHAIN_ELF=y`,
  `LDSO_M68K_PREFIX=m68k-unknown-ptos-prgelf-`,
  `TEST_LDFLAGS=-Wl,-q,-Ttext=0,-e,_start`.
- ARM: `CROSS_COMPILE=arm-unknown-ptos-elf-`,
  `CROSSPREFIX=arm-unknown-ptos-elf-`.
- x32: `CROSS_COMPILE=x86_64-unknown-ptos-elfx32-`. The pTOS Makefile selects
  `-m64 -mno-red-zone` for the kernel and `-mx32` for programs.

Each configuration built its kernel and `test-dir`, then ran
`tools/run-regression-tests.sh MACHINE 180`. m68k fastcall additionally enabled
`CONF_WITH_ELF_LOADER=y`: its stock config omits that loader, while this SDK's
EmuCON is an ELF executable. The m68k `relocprobe2-unpacked.tos` fixture's direct
ld invocation additionally used `-m m68kmintelf` with `--oformat=elf32-m68k`, as
already described in the toolchain README. Both adaptations were confined to
the validation worktree.

QEMU used the local firmware/ROM directory. The existing environment preload
redirected vvfat temporary files from read-only `/var/tmp` to `/tmp`. x32 used
OVMF and a raw FAT disk; its local monitor socket required execution outside
the command sandbox. None of these environment adaptations changed pTOS code.
