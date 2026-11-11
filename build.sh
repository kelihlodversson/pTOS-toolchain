#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <all|m68k|arm|x86_64> <install-prefix> [binutils|gcc|sdk] [--gcc VERSION] [--binutils VERSION]" >&2
    echo "       $0 --list-versions" >&2
    exit "${1:-2}"
}

project=$(cd -- "$(dirname -- "$0")" && pwd)
gcc_version=latest
binutils_version=latest
positional=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --gcc|--binutils)
            [[ $# -ge 2 && $2 != --* ]] || usage
            case $1 in
                --gcc) gcc_version=$2 ;;
                --binutils) binutils_version=$2 ;;
            esac
            shift 2 ;;
        --list-versions)
            for component in gcc binutils; do
                printf '%s: ' "$component"
                python3 "$project/versions.py" "$component" --list
            done
            exit ;;
        -h|--help) usage 0 ;;
        --*) usage ;;
        *) positional+=("$1"); shift ;;
    esac
done
set -- ${positional[@]+"${positional[@]}"}
[[ $# -ge 2 && $# -le 3 ]] || usage
case $1 in
    all) architectures=(m68k arm x86_64) ;;
    m68k|arm|x86_64) architectures=("$1") ;;
    *) usage ;;
esac
stage=${3:-all}
case $stage in all|binutils|gcc|sdk) ;; *) usage ;; esac

# Resolve versions before creating directories or starting downloads.
gcc_recipe_text=$(python3 "$project/versions.py" gcc "$gcc_version")
binutils_recipe_text=$(python3 "$project/versions.py" binutils "$binutils_version")
# macOS ships Bash 3.2, which has no mapfile/readarray builtin.
gcc_recipe=()
binutils_recipe=()
while IFS= read -r value; do gcc_recipe+=("$value"); done <<< "$gcc_recipe_text"
while IFS= read -r value; do binutils_recipe+=("$value"); done <<< "$binutils_recipe_text"
gcc_version=${gcc_recipe[0]}
binutils_version=${binutils_recipe[0]}

source "$project/host.sh"

prefix=$(mkdir -p -- "$2" && cd -- "$2" && pwd)
work=$(mkdir -p -- "${PTOS_WORKDIR:-$project/.work}" && cd -- "${PTOS_WORKDIR:-$project/.work}" && pwd)
cache=$(mkdir -p -- "${PTOS_CACHE:-$work/downloads}" && cd -- "${PTOS_CACHE:-$work/downloads}" && pwd)
jobs=${JOBS:-$(getconf _NPROCESSORS_ONLN)}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 2; }

export PATH="$prefix/bin:$PATH"

download() (
    local url=$1 hash=$2 file="$cache/${1##*/}" temporary
    if [[ ! -f $file ]]; then
        temporary=$(mktemp "$cache/.${file##*/}.XXXXXX")
        trap 'rm -f -- "$temporary"' EXIT
        curl --fail --location --silent --show-error --retry 2 "$url" -o "$temporary" || return 1
        printf '%s  %s\n' "$hash" "$temporary" | sha256_check >&2 || return 1
        mv -- "$temporary" "$file" || return 1
    fi
    printf '%s  %s\n' "$hash" "$file" | sha256_check >&2 || return 1
    printf '%s\n' "$file"
)

prepare() {
    local component=$1 arch=$2 archive=$3 mint_patch=${4:-} version=$5
    local source="$work/$arch/$component-$version-src" staging="$work/$arch/$component-$version-src.tmp"
    if [[ ! -d $source ]]; then
        rm -rf -- "$staging"
        mkdir -p -- "$staging"
        tar -xf "$archive" -C "$staging" --strip-components=1
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
    archive=$(download "${binutils_recipe[1]}" "${binutils_recipe[2]}")
    if [[ $arch == m68k ]]; then
        mint_patch="$project/${binutils_recipe[3]}"
        options+=(--enable-relro)
    elif [[ $arch == x86_64 ]]; then
        options+=(--enable-relro --enable-separate-code)
    fi
    prepare binutils "$arch" "$archive" "$mint_patch" "$binutils_version"
    mkdir -p -- "$work/$arch/binutils-$binutils_version-build"
    cd -- "$work/$arch/binutils-$binutils_version-build"
    if [[ ! -f Makefile ]]; then
        ../binutils-$binutils_version-src/configure --target="$target" --prefix="$prefix" \
            --with-sysroot="$prefix/$target/sysroot" --disable-nls --disable-werror \
            --disable-gprofng --disable-gdb --disable-sim --without-debuginfod \
            ${host_binutils_options[@]+"${host_binutils_options[@]}"} "${options[@]}"
    fi
    "$MAKE" -j "$jobs" MAKEINFO=true
    "$MAKE" MAKEINFO=true install
)

build_gcc() (
    local arch=$1 target=$2 archive mint_patch=
    local options=()
    case $arch in
        m68k)
            mint_patch="$project/${gcc_recipe[3]}"
            ;;
        arm)
            options=(--with-arch=armv6k --with-tune=arm1176jzf-s --with-mode=arm \
                     --with-fpu=vfp --with-float=hard --disable-multilib)
            ;;
        x86_64) options=(--with-abi=x32) ;;
    esac
    archive=$(download "${gcc_recipe[1]}" "${gcc_recipe[2]}")
    prepare gcc "$arch" "$archive" "$mint_patch" "$gcc_version"
    mkdir -p -- "$work/$arch/gcc-$gcc_version-binutils-$binutils_version-build" "$prefix/$target/sysroot/include"
    cd -- "$work/$arch/gcc-$gcc_version-binutils-$binutils_version-build"
    if [[ ! -f Makefile ]]; then
        ../gcc-$gcc_version-src/configure --target="$target" --prefix="$prefix" \
            --with-sysroot="$prefix/$target/sysroot" --with-native-system-header-dir=/include \
            --with-gnu-as --with-gnu-ld --without-headers --disable-bootstrap \
            --enable-languages=c --disable-nls --disable-shared --disable-threads \
            --disable-libssp --disable-libgomp --disable-libquadmath --disable-libatomic \
            ${host_gcc_options[@]+"${host_gcc_options[@]}"} ${options[@]+"${options[@]}"}
    fi
    "$MAKE" -j "$jobs" MAKEINFO=true all-gcc all-target-libgcc
    "$MAKE" MAKEINFO=true install-gcc install-target-libgcc
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
        "$project/install-libcmini.sh" "$arch" "$target" "$prefix" "$work" "$jobs" "gcc-$gcc_version-binutils-$binutils_version"
    fi
done
