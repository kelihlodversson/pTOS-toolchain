#!/usr/bin/env bash
set -euo pipefail

arch=$1 target=$2 prefix=$3 work=$4 jobs=$5
project=$(cd -- "$(dirname -- "$0")" && pwd)
revision=c85f67a52679b68782c49fd967732d14bfe87841
source="$work/$arch/libcmini-$revision"
build="$work/$arch/libcmini-build"
sysroot="$prefix/$target/sysroot"
cc="$prefix/bin/$target-gcc"

if [[ ! -f $source/Makefile ]]; then
    staging=$(mktemp -d "$work/$arch/libcmini.XXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    git -C "$staging" init -q
    git -C "$staging" fetch --depth=1 https://github.com/kelihlodversson/libcmini.git "$revision"
    git -C "$staging" checkout -q --detach "$revision"
    mv -- "$staging" "$source"
fi

case $arch in
    m68k) config=mintelf_defconfig ;;
    arm) config=ptos_arm_defconfig ;;
    x86_64) config=ptos_x86_64_defconfig ;;
esac

make_libcmini=(make -C "$source" BUILDDIR="$build" CROSSPREFIX="$prefix/bin/$target-"
    'ARCH_CFLAGS=-fno-pie -fno-stack-protector -fno-asynchronous-unwind-tables -fno-unwind-tables')
"${make_libcmini[@]}" "$config"
"${make_libcmini[@]}" PREFIX_FOR_INCLUDE="$sysroot/include" install-include
install -m 644 "$project/sysroot/locale.h" "$sysroot/include/locale.h"
"${make_libcmini[@]}" -j "$jobs" libs startups

# libcmini only builds the user ABI on ARM and x86-64. The m68k startup
# and archives have to follow GCC's CPU/calling-convention multilib layout.
multilibs=$("$cc" -print-multi-lib)
while IFS=';' read -r variant flags; do
    if [[ $arch != m68k && -n $flags ]]; then
        continue
    fi
    library_dir="$sysroot/lib/$variant"
    install -d "$library_dir"
    install -m 644 "$build/$variant/libcmini.a" "$build/$variant/libiiomini.a" "$library_dir/"
    install -m 644 "$build/$variant/objs/crt0.o" "$library_dir/ptos-crt0.o"
    install -m 644 "$build/$variant/objs/minicrt0.o" "$library_dir/ptos-minicrt0.o"
done <<< "$multilibs"
