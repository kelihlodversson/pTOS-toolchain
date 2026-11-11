#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

[[ $# == 1 || $# == 2 ]] || { echo "Usage: $0 <install-prefix> [all|m68k|arm|x86_64]" >&2; exit 2; }
bin=$(cd -- "$1/bin" && pwd)
arch=${2:-all}
case $arch in all|m68k|arm|x86_64) ;; *) exit 2 ;; esac

scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
cd -- "$scratch"

cat > hello.c <<'EOF'
#include <stdint.h>
#include <stdio.h>

#ifndef __ptos__
#error The driver did not select pTOS
#endif
_Static_assert(sizeof(void *) == 4 && sizeof(long) == 4, "ILP32 user ABI");
static volatile uint64_t value = 23;
static volatile uint64_t divisor = 4;

int main(void)
{
    puts("Hello from pTOS");
    return value / divisor == 5 ? 0 : 1;
}
EOF

check_elf() {
    local file=$1 class=$2 machine=$3 header
    header=$("$target-readelf" -h "$file")
    grep -Eq "Class: +$class" <<< "$header"
    grep -Eq "Machine: +$machine" <<< "$header"
}

check_prgelf() {
    "$target-objdump" -f "$1" | grep -q 'file format elf32-atariprg'
}

check_target() {
    [[ $("$target-gcc" -dumpmachine) == "${target##*/}" ]]
    "$target-gcc" hello.c -o hello.elf
    check_elf hello.elf ELF32 "$1"
    "$target-readelf" -h hello.elf | grep -q 'EXEC (Executable file)'
}

if [[ $arch == all || $arch == m68k ]]; then
    target="$bin/m68k-unknown-ptos-prgelf"

    # A memory BTST reads one byte on m68k. A volatile 32-bit MMIO read
    # must retain its width even when only one bit is used by a branch.
    cat > mmio.c <<'EOF'
extern void use(void);
void probe(volatile unsigned long *p) { if (*p & 0x01000000UL) use(); }
EOF
    for optimization in -O2 -Os; do
        "$target-gcc" "$optimization" -m68020 -S mmio.c -o mmio.s
        if grep -Eq 'btst.*\(' mmio.s; then
            echo 'm68k: volatile long MMIO read narrowed to a byte BTST' >&2
            exit 1
        fi
    done
    check_target 'MC68000'
    "$target-gcc" -mmintelf hello.c -o hello.tos
    check_prgelf hello.tos
    "$target-gcc" -mfastcall -c hello.c -o fastcall.o
    "$target-readelf" -A fastcall.o | grep -Eq 'fastcall|5 \(0x5\)'
    "$target-gcc" -mfastcall fastcall.o -o fastcall.elf
    check_elf fastcall.elf ELF32 'MC68000'
    [[ $("$target-gcc" -mfastcall -print-libgcc-file-name) != $("$target-gcc" -print-libgcc-file-name) ]]

    cat > pic.c <<'EOF'
extern volatile int number;
extern int use_number(int);
int exported(void) { return use_number(number); }
EOF
    "$target-gcc" -m68020 -fPIC -nostdlib -shared pic.c -o libpic.so
    relocations=$("$target-readelf" -r libpic.so)
    grep -q R_68K_GLOB_DAT <<< "$relocations"
    grep -q R_68K_JMP_SLOT <<< "$relocations"
    echo 'm68k: ELF, PRG+ELF, fastcall, and GOT/PLT shared library passed'
fi

if [[ $arch == all || $arch == arm ]]; then
    target="$bin/arm-unknown-ptos-elf"
    check_target ARM
    "$target-readelf" -h hello.elf | grep -q 'Version5 EABI, hard-float ABI'
    echo 'ARM: ELF32 EABI5 hard-float passed'
fi

if [[ $arch == all || $arch == x86_64 ]]; then
    target="$bin/x86_64-unknown-ptos-elfx32"
    check_target 'Advanced Micro Devices X86-64'
    cat > start.s <<'EOF'
.text
.globl _start
_start:
    xor %eax, %eax
    ret
EOF
    "$target-as" -o start.o start.s
    "$target-ld" -o bare.elf start.o
    check_elf bare.elf ELF32 'Advanced Micro Devices X86-64'
    "$target-gcc" -nostdlib -shared start.o -o loader.so
    headers=$("$target-readelf" -lW loader.so)
    grep -q GNU_RELRO <<< "$headers"
    if grep -Eq 'GNU_STACK.*RWE' <<< "$headers"; then
        echo 'The pTOS loader requires a non-executable stack' >&2
        exit 1
    fi

    printf '%s\n' '_Static_assert(sizeof(void *) == 8 && sizeof(long) == 8, "LP64 kernel ABI");' \
        'void _start(void) {}' > kernel.c
    "$target-gcc" -m64 -mno-red-zone -ffreestanding -nostdlib kernel.c -o kernel.elf
    check_elf kernel.elf ELF64 'Advanced Micro Devices X86-64'
    [[ $("$target-gcc" -m64 -mno-red-zone -print-libgcc-file-name) == */64/no-red-zone/libgcc.a ]]
    "$target-gcc" -m64 -mno-red-zone -ffreestanding -fno-ident -c kernel.c -o kernel.o
    "$target-ld" -m i386pep -pie --subsystem 10 -e _start kernel.o -o kernel.efi
    "$target-objdump" -f kernel.efi | grep -q 'file format pei-x86-64'
    echo 'x86-64: x32 GCC/as/ld defaults, LP64 ELF and PE32+ passed'
fi
