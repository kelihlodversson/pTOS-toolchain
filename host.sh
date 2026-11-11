#!/usr/bin/env bash
# Shared host setup for the toolchain and libcmini builds.

if [[ -z ${MAKE:-} ]]; then
    if command -v gmake >/dev/null 2>&1; then
        MAKE=gmake
    else
        MAKE=make
    fi
fi
export MAKE

make_version=$("$MAKE" --version | head -n 1)
if [[ ! $make_version =~ GNU\ Make\ ([0-9]+)\.([0-9]+) ]] ||
    (( BASH_REMATCH[1] < 4 || (BASH_REMATCH[1] == 4 && BASH_REMATCH[2] < 3) )); then
    echo 'GNU Make 4.3 or later is required; install it and set MAKE if needed.' >&2
    exit 1
fi

sha256_check() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c -
    else
        shasum -a 256 -c -
    fi
}

host_gcc_options=()
host_binutils_options=()
if [[ $(uname -s) == Darwin ]]; then
    # The bundled zlib treats Apple's modern TARGET_OS_MAC as classic Mac OS.
    host_binutils_options+=(--with-system-zlib)
    host_gcc_options+=(--with-system-zlib)
fi
if [[ $(uname -s) == Darwin ]] && command -v brew >/dev/null 2>&1; then
    # Homebrew's libraries are outside Apple's default compiler search path.
    for library in gmp mpfr libmpc; do
        library_prefix=$(brew --prefix "$library")
        if [[ ! -d $library_prefix/include ]]; then
            echo "Missing $library headers; run: brew install gmp mpfr libmpc" >&2
            exit 1
        fi
        case $library in
            libmpc) host_gcc_options+=(--with-mpc="$library_prefix") ;;
            *) host_gcc_options+=("--with-$library=$library_prefix") ;;
        esac
    done
fi
