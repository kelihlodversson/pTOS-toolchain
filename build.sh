#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <all|m68k|arm|x86_64> <install-prefix> [binutils|gcc|sdk]" >&2
    exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage
case $1 in
    all) architectures=(m68k arm x86_64) ;;
    m68k|arm|x86_64) architectures=("$1") ;;
    *) usage ;;
esac
stage=${3:-all}
case $stage in all|binutils|gcc|sdk) ;; *) usage ;; esac

project=$(cd -- "$(dirname -- "$0")" && pwd)
prefix=$(mkdir -p -- "$2" && cd -- "$2" && pwd)
work=$(mkdir -p -- "${PTOS_WORKDIR:-$project/.work}" && cd -- "${PTOS_WORKDIR:-$project/.work}" && pwd)
cache=$(mkdir -p -- "${PTOS_CACHE:-$work/downloads}" && cd -- "${PTOS_CACHE:-$work/downloads}" && pwd)
jobs=${JOBS:-$(getconf _NPROCESSORS_ONLN)}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 2; }

export PATH="$prefix/bin:$PATH"

gcc_version=14.3.0
binutils_version=2.45
crossmint=https://raw.githubusercontent.com/th-otto/crossmint/53ff5e25af1cd679bb60d46ab4e808d559ae5af2/patches

download() (
    local url=$1 hash=$2 file="$cache/${1##*/}" temporary
    if [[ ! -f $file ]]; then
        temporary=$(mktemp "$cache/.${file##*/}.XXXXXX")
        trap 'rm -f -- "$temporary"' EXIT
        curl --fail --location --silent --show-error --retry 2 "$url" -o "$temporary"
        printf '%s  %s\n' "$hash" "$temporary" | sha256sum -c - >&2
        mv -- "$temporary" "$file"
    fi
    printf '%s  %s\n' "$hash" "$file" | sha256sum -c - >&2
    printf '%s\n' "$file"
)

prepare() {
    local component=$1 arch=$2 archive=$3 mint_patch=${4:-}
    local source="$work/$arch/$component-src" staging="$work/$arch/$component-src.tmp"
    if [[ ! -d $source ]]; then
        rm -rf -- "$staging"
        mkdir -p -- "$staging"
        tar --extract --file="$archive" --directory="$staging" --strip-components=1
        if [[ -n $mint_patch ]]; then
            patch --directory="$staging" -p1 --batch --forward --silent < "$mint_patch"
        fi
        python3 "$project/prepare.py" "$component" "$arch" "$staging"
        mv -- "$staging" "$source"
    fi
}

build_binutils() (
    local arch=$1 target=$2 archive mint_patch=
    local options=(--disable-default-execstack)
    archive=$(download "https://ftp.gnu.org/gnu/binutils/binutils-$binutils_version.tar.xz" \
        c50c0e7f9cb188980e2cc97e4537626b1672441815587f1eab69d2a1bfbef5d2)
    if [[ $arch == m68k ]]; then
        mint_patch=$(download "$crossmint/binutils/binutils-2.45-mint-20250812.patch" \
            82bd5f13fcbb0bbd3664b8d75cd3a4bb5df99072736b797f7be41726a0ebbc91)
        options+=(--enable-relro)
    elif [[ $arch == x86_64 ]]; then
        options+=(--enable-relro --enable-separate-code)
    fi
    prepare binutils "$arch" "$archive" "$mint_patch"
    mkdir -p -- "$work/$arch/binutils-build"
    cd -- "$work/$arch/binutils-build"
    if [[ ! -f Makefile ]]; then
        ../binutils-src/configure --target="$target" --prefix="$prefix" \
            --with-sysroot="$prefix/$target/sysroot" --disable-nls --disable-werror \
            --disable-gprofng --disable-gdb --disable-sim --without-debuginfod "${options[@]}"
    fi
    make -j "$jobs" MAKEINFO=true
    make MAKEINFO=true install
)

build_gcc() (
    local arch=$1 target=$2 archive mint_patch=
    local options=()
    case $arch in
        m68k)
            mint_patch=$(download "$crossmint/gcc/gcc-14.3.0-mint-20250702.patch" \
                3dd3c201985fe09a81c59bdf50a7079bec53545f302f152f7c65ad182db4b2a0)
            ;;
        arm)
            options=(--with-arch=armv6k --with-tune=arm1176jzf-s --with-mode=arm \
                     --with-fpu=vfp --with-float=hard --disable-multilib)
            ;;
        x86_64) options=(--with-abi=x32) ;;
    esac
    archive=$(download "https://ftp.gnu.org/gnu/gcc/gcc-$gcc_version/gcc-$gcc_version.tar.xz" \
        e0dc77297625631ac8e50fa92fffefe899a4eb702592da5c32ef04e2293aca3a)
    prepare gcc "$arch" "$archive" "$mint_patch"
    mkdir -p -- "$work/$arch/gcc-build" "$prefix/$target/sysroot/include"
    cd -- "$work/$arch/gcc-build"
    if [[ ! -f Makefile ]]; then
        ../gcc-src/configure --target="$target" --prefix="$prefix" \
            --with-sysroot="$prefix/$target/sysroot" --with-native-system-header-dir=/include \
            --with-gnu-as --with-gnu-ld --without-headers --disable-bootstrap \
            --enable-languages=c --disable-nls --disable-shared --disable-threads \
            --disable-libssp --disable-libgomp --disable-libquadmath --disable-libatomic \
            "${options[@]}"
    fi
    make -j "$jobs" MAKEINFO=true all-gcc all-target-libgcc
    make MAKEINFO=true install-gcc install-target-libgcc
)

for arch in "${architectures[@]}"; do
    case $arch in
        m68k) target=m68k-unknown-ptos-prgelf ;;
        arm) target=arm-unknown-ptos-elf ;;
        x86_64) target=x86_64-unknown-ptos-elfx32 ;;
    esac
    mkdir -p -- "$work/$arch"
    if [[ $stage == all || $stage == binutils ]]; then
        build_binutils "$arch" "$target"
    fi
    if [[ $stage == all || $stage == gcc ]]; then
        build_gcc "$arch" "$target"
    fi
    if [[ $stage == all || $stage == sdk ]]; then
        "$project/install-libcmini.sh" "$arch" "$target" "$prefix" "$work" "$jobs"
    fi
done
