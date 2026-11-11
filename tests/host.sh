#!/usr/bin/env bash
# Host setup and download failure regressions; no network or compiler build.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
mkdir -p "$scratch/bin"

cat > "$scratch/bin/old-make" <<'EOF'
#!/usr/bin/env bash
echo 'GNU Make 3.81'
EOF
chmod +x "$scratch/bin/old-make"
if MAKE="$scratch/bin/old-make" "$BASH" -c 'set -eu; source "$1/host.sh"' _ "$project" > "$scratch/log" 2>&1; then
    echo 'Accepted an unsupported Make version' >&2
    exit 1
fi
grep -q 'GNU Make 4.3 or later is required' "$scratch/log"

# Exercise the checksum fallback with sha256sum absent from PATH.
mkdir -p "$scratch/checksum-bin"
for tool in head uname shasum; do
    ln -s "$(command -v "$tool")" "$scratch/checksum-bin/$tool"
done
if command -v gmake >/dev/null 2>&1; then
    selected_make=$(command -v gmake)
else
    selected_make=$(command -v make)
fi
PATH="$scratch/checksum-bin" MAKE="$selected_make" "$BASH" -c '
    set -euo pipefail
    source "$1/host.sh"
    printf "%s  %s\n" \
        82bd5f13fcbb0bbd3664b8d75cd3a4bb5df99072736b797f7be41726a0ebbc91 \
        "$1/patches/binutils/binutils-2.45-mint-20250812.patch" | sha256_check
' _ "$project"

cat > "$scratch/bin/curl" <<'EOF'
#!/usr/bin/env bash
while [[ $# -gt 0 ]]; do
    if [[ $1 == -o ]]; then
        printf 'invalid archive\n' > "$2"
        break
    fi
    shift
done
exit "${CURL_STATUS:-0}"
EOF
chmod +x "$scratch/bin/curl"

for status in 0 22; do
    work="$scratch/work-$status"
    if PATH="$scratch/bin:$PATH" CURL_STATUS=$status PTOS_WORKDIR="$work" JOBS=1 \
        "$BASH" "$project/build.sh" arm "$scratch/prefix" binutils > "$scratch/log" 2>&1; then
        echo 'Accepted a failed download or invalid checksum' >&2
        exit 1
    fi
    [[ ! -e $work/downloads/binutils-2.45.tar.xz ]]
    [[ ! -e $work/arm/binutils-src.tmp ]]
    [[ -z $(ls -A "$work/downloads") ]]
done

# An existing corrupt cache entry must also stop before source extraction.
work="$scratch/cached"
mkdir -p "$work/downloads"
printf 'invalid archive\n' > "$work/downloads/binutils-2.45.tar.xz"
if PTOS_WORKDIR="$work" JOBS=1 "$BASH" "$project/build.sh" arm "$scratch/prefix" binutils > "$scratch/log" 2>&1; then
    echo 'Accepted a corrupt cached archive' >&2
    exit 1
fi
[[ ! -e $work/arm/binutils-src.tmp ]]
echo 'Host setup and download failure checks passed'
