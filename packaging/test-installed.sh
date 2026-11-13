#!/usr/bin/env bash
set -euo pipefail
version=${1:?Expected Debian version}
for arch in m68k arm x86_64; do
  package=ptos-sdk-${arch//_/-}
  test "$(dpkg-query -W -f='${Version}' "$package")" = "$version"
  bash "/usr/share/doc/$package/smoke.sh" /usr "$arch"
  case $arch in
    m68k) target=m68k-unknown-ptos-prgelf ;;
    arm) target=arm-unknown-ptos-elf ;;
    x86_64) target=x86_64-unknown-ptos-elfx32 ;;
  esac
  test "$("$target-gcc" -dumpmachine)" = "$target"
  test "$("$target-gcc" -print-sysroot)" = "/opt/ptos/$arch/$target/sysroot"
done
