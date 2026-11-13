#!/usr/bin/env python3
"""Register the pTOS targets in the pinned GCC and Binutils releases."""

import argparse
import re
from pathlib import Path


def replace(root, path, original, replacement):
    file = root / path
    source = file.read_text()
    if source.count(original) != 1:
        raise ValueError(f"{file}: expected one occurrence of {original!r}")
    file.write_text(source.replace(original, replacement))


def add_target_names(root):
    # Keep these four-part names intact. The last component is the pTOS ABI.
    marker = "# Split fields of configuration type\n"
    replace(root, "config.sub", marker, """case $1 in
    m68k-*-ptos-prgelf | arm-*-ptos-elf | x86_64-*-ptos-elfx32)
        echo "$1"
        exit ;;
esac

""" + marker)


def prepare_binutils(root, arch):
    if arch == "m68k":
        # The CrossMiNT patch references its a.out BFD backend from the
        # common relocation code, even in an ELF-only linker.
        replace(root, "bfd/config.bfd", "  m68*-*-mintelf*)\n", """\
  m68k-*-ptos-prgelf)
    targ_defvec=m68k_elf32_vec
    targ_selvecs="m68k_elf32_atariprg_vec m68k_aout_mintprg_vec"
    ;;
  m68*-*-mintelf*)
""")
        # Use the host libc ABI. CrossMiNT's Linux binary distribution pins
        # glibc symbol versions that are unsuitable for newer host headers.
        (root / "include/libcwrap.h").write_text("/* Use host libc symbol versions. */\n")
        replace(root, "gas/configure.tgt", "  m68k-*-elf*)", "  m68k-*-ptos-prgelf | m68k-*-elf*)")
        replace(root, "ld/configure.tgt", "m68*-*-mintelf*)", """\
m68k-*-ptos-prgelf)\ttarg_emul=m68kelf
\t\t\ttarg_extra_emuls=m68kmintelf
\t\t\t;;
m68*-*-mintelf*)""")
        # Use ordinary ELF GAS. The patched tc-m68k.c handles the ABI flags
        # and ELF relocations; the Atari program header is a linker choice.
        replace(root, "ld/emulparams/m68kelf.sh", "TEXT_START_ADDR=0x80000000\n", """\
TEXT_START_ADDR=0x80000000
case $target in
  m68k-*-ptos-prgelf) TEXT_START_ADDR=0x400000 ;;
esac
""")
    elif arch == "arm":
        replace(root, "bfd/config.bfd", "  arm-*-elf | arm*-*-freebsd*",
                "  arm-*-ptos-elf | arm-*-elf | arm*-*-freebsd*")
        replace(root, "gas/configure.tgt", "  arm-*-eabi* | arm-*-rtems*",
                "  arm-*-ptos-elf | arm-*-eabi* | arm-*-rtems*")
        replace(root, "ld/configure.tgt", "arm-*-elf | arm*-*-eabi*",
                "arm-*-ptos-elf | arm-*-elf | arm*-*-eabi*")
    else:
        replace(root, "bfd/config.bfd", "  x86_64-*-elf* | x86_64-*-rtems*", """\
  x86_64-*-ptos-elfx32)
    targ_defvec=x86_64_elf32_vec
    targ_selvecs="x86_64_elf64_vec x86_64_pe_vec x86_64_pei_vec"
    want64=true
    ;;
  x86_64-*-elf* | x86_64-*-rtems*""")
        replace(root, "gas/configure.tgt", "  i386-*-elf*)\t", """\
  i386-*-ptos-elfx32)\t\t\tfmt=elf arch=x86_64:32 ;;
  i386-*-elf*)\t""")
        replace(root, "ld/configure.tgt", "x86_64-*-elf* | x86_64-*-rtems*", """\
x86_64-*-ptos-elfx32)\ttarg_emul=elf32_x86_64
\t\t\ttarg_extra_emuls="elf_x86_64 i386pep"
\t\t\ttarg_extra_ofiles="$targ_extra_ofiles deffilep.o pdb.o pep-dll-x86_64.o pe-dll.o"
\t\t\t;;
x86_64-*-elf* | x86_64-*-rtems*""")


def fix_m68k_move_dependencies(root):
    # RTL evaluates the SET source before its destination.  MOVE evaluates
    # the destination address after updating a source address register.
    replace(root, "gcc/config/m68k/m68k-protos.h",
            "extern const char *output_move_simode (rtx *);",
            "extern bool m68k_move_operands_p (rtx, rtx);\n"
            "extern const char *output_move_simode (rtx *);")
    marker = "\nconst char *\noutput_move_simode (rtx *operands)\n"
    replace(root, "gcc/config/m68k/m68k.cc", marker, """
/* Reject a memory MOVE whose source updates a register used to address
   the destination.  Combining such operands changes the destination EA.  */
bool
m68k_move_operands_p (rtx dest, rtx src)
{
  if (MEM_P (dest) && MEM_P (src))
    {
      rtx addr = XEXP (src, 0);
      if ((GET_CODE (addr) == POST_INC || GET_CODE (addr) == PRE_DEC)
          && reg_overlap_mentioned_p (XEXP (addr, 0), XEXP (dest, 0)))
        return false;
    }
  return true;
}
""" + marker)
    md = root / "gcc/config/m68k/m68k.md"
    chunks = re.split(r"(?=^\(define_)", md.read_text(), flags=re.M)
    count = 0
    for index, chunk in enumerate(chunks):
        if (chunk.startswith("(define_insn ") and re.search(
                r'\[\(set \(match_operand:(SI|HI|QI|SF) 0 "nonimmediate_operand"[^)]*\)'
                r'\s*\(match_operand:\1 1 "(?:general_src_operand|general_operand)"',
                chunk, re.S)):
            chunks[index], replacements = re.subn(
                r'\n  "([^"\n]*)"\n',
                r'\n  "\1 && m68k_move_operands_p (operands[0], operands[1])"\n',
                chunk, count=1)
            if replacements != 1:
                raise ValueError("missing m68k MOVE condition")
            count += 1
    if count != 10:
        raise ValueError(f"expected ten m68k MOVE patterns, found {count}")
    md.write_text("".join(chunks))


def prepare_gcc(root, arch):
    if arch == "m68k":
        fix_m68k_move_dependencies(root)
        # Retain CrossMiNT's C ABI, including fastcall and the CPU multilibs.
        replace(root, "gcc/config.gcc", "m68k-*-mintelf*)\n", """\
m68k-*-ptos-prgelf)
    default_m68k_cpu=68000
    default_cf_cpu=5475
    tm_file="${tm_file} dbxelf.h elfos.h m68k/mint.h m68k/mint-stdint.h"
    tm_defines="${tm_defines} MOTOROLA=1"
    tmake_file="m68k/t-floatlib m68k/t-mint"
    extra_options="${extra_options} m68k/ptos.opt"
    gcc_cv_initfini_array=yes
    ;;
m68k-*-mintelf*)
""")
        replace(root, "libgcc/config.host", "m68k-*-elf* | fido-*-elf)",
                "m68k-*-ptos-prgelf | m68k-*-elf* | fido-*-elf)")
        # Keep ELF's normal GOT/PLT code generation available. The MiNT
        # target's compile-time restriction is specific to its PRG output.
        options = root / "gcc/config/m68k/ptos.opt"
        options.write_text("""
mmintelf
Target RejectNegative
Link a MiNT PRG+ELF executable.

""")
        options.with_suffix(".opt.urls").touch()
        target_header = r"""
#undef TARGET_OS_CPP_BUILTINS
#define TARGET_OS_CPP_BUILTINS() \
  do { builtin_define ("__ptos__"); GCC_HAVE_INITFINI_ARRAY_SUPPORT } while (0)

#undef SUBTARGET_OVERRIDE_OPTIONS
#define SUBTARGET_OVERRIDE_OPTIONS do { } while (0)

/* The MiNT ELF target uses the stack and floating-point ABI selected by
   the CPU flags. pTOS kernels pass -msoft-float explicitly. */
#define PTOS_RELOCATABLE_LINK "%{!mmintelf:-q -Ttext=0} "
#undef LINK_SPEC
#define LINK_SPEC PTOS_LINK_MODE PTOS_APPLICATION_LINK \
  "%{mmintelf:%{shared|pie|static-pie:%e-mmintelf requires a static executable} " \
  "-m m68kmintelf}"
"""
    elif arch == "arm":
        marker = " # Avoid special cases that are not obsolete\n"
        replace(root, "gcc/config.gcc", marker, marker + "   arm-*-ptos-elf) ;;\n")
        for path, pattern, secondary in (
            ("gcc/config.gcc", "arm*-*-eabi* | arm*-*-symbianelf* | arm*-*-rtems* | arm*-*-fuchsia*)",
             "\tarm*-*-eabi*)\n\t  tm_file=\"$tm_file newlib-stdint.h\""),
            ("libgcc/config.host", "arm*-*-eabi* | arm*-*-symbianelf* | arm*-*-rtems*)",
             "\tarm*-*-eabi* | arm*-*-rtems*)"),
        ):
            replace(root, path, pattern, "arm-*-ptos-elf | " + pattern)
            replace(root, path, secondary, "\tarm-*-ptos-elf | " + secondary.lstrip())
        target_header = r"""
#define PTOS_RELOCATABLE_LINK "-q -Ttext=0 "
#undef LINK_SPEC
#define LINK_SPEC BPABI_LINK_SPEC " " PTOS_APPLICATION_LINK

/* The static ELF loader can rebase absolute words, not split MOVW/MOVT. */
#undef CC1_SPEC
#define CC1_SPEC "%{!mno-word-relocations:-mword-relocations}"
"""
    else:
        replace(root, "gcc/config.gcc", "x86_64-*-elf*)\n", """\
x86_64-*-ptos-elfx32)
    tm_file="${tm_file} i386/unix.h i386/att.h elfos.h newlib-stdint.h i386/i386elf.h i386/x86-64.h"
    tmake_file="${tmake_file} i386/t-ptos"
    ;;
x86_64-*-elf*)
""")
        replace(root, "libgcc/config.host", "x86_64-*-elf* | x86_64-*-rtems*)",
                "x86_64-*-ptos-elfx32 | x86_64-*-elf* | x86_64-*-rtems*)")
        (root / "gcc/config/i386/t-ptos").write_text("""\
MULTILIB_OPTIONS = m64/mx32 mno-red-zone
MULTILIB_DIRNAMES = 64 x32 no-red-zone
MULTILIB_REQUIRED = m64 m64/mno-red-zone
""")
        target_header = r"""
#undef MULTILIB_DEFAULTS
#define MULTILIB_DEFAULTS { "mx32" }
#undef SUBTARGET_DRIVER_SELF_SPECS
#define SUBTARGET_DRIVER_SELF_SPECS \
  "%{m16|m32:%eUse -mx32 for pTOS applications or -m64 for the kernel}"

#define PTOS_RELOCATABLE_LINK "%{!m64:-q -z max-page-size=4096 -z noseparate-code} "
#undef LINK_SPEC
#define LINK_SPEC PTOS_LINK_MODE PTOS_APPLICATION_LINK "%{m64:-m elf_x86_64}"

/* The SDK provides the ILP32 user ABI. LP64 is for freestanding kernels. */
#undef STARTFILE_SPEC
#define STARTFILE_SPEC "%{!shared:%{m64:%eUse -nostdlib for the LP64 kernel;:ptos-crt0.o%s}}"
#undef LIB_SPEC
#define LIB_SPEC "%{!m64:-lcmini}"
"""

    common_config = """\
case ${target} in
*-*-ptos-*)
    tm_file="${tm_file} ptos.h"
    gas=yes
    gnu_ld=yes
    use_gcc_stdint=provide
    # Build libgcc before installing the pTOS C library in the sysroot.
    inhibit_libc=true
    ;;
esac

"""
    marker = "case ${target} in\ni[34567]86-*-linux* | x86_64-*-linux*)\n"
    replace(root, "gcc/config.gcc", marker, common_config + marker)
    (root / "gcc/config/ptos.h").write_text(r"""
/* GCC driver settings for the pTOS C SDK. */
#undef TARGET_OS_CPP_BUILTINS
#define TARGET_OS_CPP_BUILTINS() builtin_define ("__ptos__")

/* When a caller supplies its own link or startup, leave its layout alone. */
#define PTOS_APPLICATION_LINK \
  "%{!nostdlib:%{!nostartfiles:%{!shared:%{!r:%{!pie:%{!static-pie:" \
  "%{!T*:-static " PTOS_RELOCATABLE_LINK "} %{!e*:-e _start}}}}}}} "
#define PTOS_LINK_MODE "%{static:-static} %{shared:-shared} %{rdynamic:-export-dynamic} "

#undef STARTFILE_PREFIX_SPEC
#define STARTFILE_PREFIX_SPEC "/lib/"
#undef STARTFILE_SPEC
#define STARTFILE_SPEC "%{!shared:ptos-crt0.o%s}"
#undef ENDFILE_SPEC
#define ENDFILE_SPEC ""
#undef LIB_SPEC
#define LIB_SPEC "-lcmini"
""".lstrip() + target_header)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("component", choices=("binutils", "gcc"))
    parser.add_argument("arch", choices=("m68k", "arm", "x86_64"))
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    add_target_names(args.source)
    if args.component == "binutils":
        prepare_binutils(args.source, args.arch)
    else:
        prepare_gcc(args.source, args.arch)


if __name__ == "__main__":
    main()
