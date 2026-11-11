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

## Hatari ROM image tests

Added two clean ROM builds and complete Hatari regression runs on the same pTOS
revision, using compiler fix `f9724e1`. Hatari was the locally installed
2.6.1-devel build at pinned commit `23bc3060ebf0da348cc842e358c102ba88002b56`.

| ROM/configuration | Hatari machine/mode | Raw ROM bytes | Padded image bytes | Free within ROM limit | Regression suites |
| --- | --- | ---: | ---: | ---: | --- |
| French `atari192`, `ptos192fr.img` | ST, 4 MB, low resolution | 189732 | 196608 | 6876 | 20 passed, 0 failed |
| US `atari512`, `ptos512k.img` | STE, 4 MB, monochrome/high resolution | 433782 | 524288 | 90506 | 29 passed, 0 failed |

The 192 KB configuration uses its stock `-Os`, LTO and `-mfastcall` settings;
only the country choice was changed to French (`BUILD_COUNTRY_FR=y`). The
512 KB configuration uses its stock `-O2` and stack calling convention. Both
builds passed `mkrom`'s hard size check; the images were also checked to be
exactly 192*1024 and 512*1024 bytes. Headroom measures the unpadded `emutos.img`
against that limit, not the size of an already padded file.

Each worktree built the default ROM and `test-hd`, using the m68k compiler
prefixes above and `BUILD_TOOLCHAIN_ELF=y`. Test applications used
`TEST_LDFLAGS=-mmintelf -Wl,-e,_start`, because these ROM configurations run
MiNT PRG programs. Neither ROM's feature selection was reduced to make it fit.
The French choice was set with kconfiglib under `CONFIG_=` (pTOS uses an empty
Kconfig symbol prefix).

Runs used the existing pTOS runner, with Hatari on PATH:

```sh
# French 192 KB worktree
python3 tools/run-hatari-tests.py --tos ptos192fr.img --disk test-hd.img --mode low --timeout 600
# US 512 KB worktree
python3 tools/run-hatari-tests.py --tos ptos512k.img --disk test-hd.img --mode high --timeout 600
```

The ST legitimately skips the blitter suites. The STE run requires passing
`raster_copy` and `text_blit` results: its checks included 9600 screen-copy,
1440 clipped-copy, 384 Line-A, and 25616 text-blit cases, all without failure.

### Additional compiler fault exposed by ROM boot

Before `f9724e1`, the 512 KB image stopped with `Panic: Address Error` in
`screen_get_current_mode_desc()`, at an `and.l` from odd address `$449`.
This was distinct from the expected, recovered bus errors during hardware
probing. The 192 KB image hit the same bad access.

A masked byte used as a table index reproduced the issue without any hardware:

```c
extern unsigned char rom_mode;
extern const unsigned short mode_table[8][3];
unsigned int mode_value(void) { return mode_table[rom_mode & 7][1]; }
```

GCC 16.2's late-combine pass produced a longword read from `rom_mode-3`.
The RTL lowpart helper now rejects widening a memory object and changing the
width of a volatile access, preserving byte reads on the 68000. The new SDK
smoke check fails before the fix and passes afterwards at `-O2` and `-Os`,
with both calling conventions. No optimization-disabling build flag was used
for the successful ROM runs. Source preparation and a clean SDK rebuild also
passed after this fix.

The m68k ELF and fastcall QEMU runs were repeated after the RTL fix: both
passed all 26 suites, four shutdown probes and the scalable-system-font replay.
ARM/x32 do not apply the MiNT patch, so their compiler sources were unchanged.

Padded image SHA-256:

- `ptos192fr.img`: `0a32212e1e788e7a976f6867c2f54d16c2dd3afe409a0e90f99acf978a800f97`
- `ptos512k.img`: `ab550f937b5c91290e58af224ae504d8207f114e243a560e8c50fecece651ab9`
