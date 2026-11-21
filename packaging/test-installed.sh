#!/usr/bin/env bash
set -euo pipefail
version=${1:?Expected Debian version}
selection=${2:-all}
for arch in m68k arm x86_64; do
  [[ $selection == all || $selection == "$arch" ]] || continue
  suffix=${arch//_/-}
  package=ptos-sdk-$suffix
  test "$(dpkg-query -W -f='${Version}' "$package")" = "$version"
  bash "/usr/share/doc/$package/smoke.sh" /usr "$arch"
  case $arch in
    m68k) target=m68k-unknown-ptos-prgelf ;;
    arm) target=arm-unknown-ptos-elf ;;
    x86_64) target=x86_64-unknown-ptos-elfx32 ;;
  esac
  prefix=/opt/ptos/$arch
  test "$("$target-gcc" -dumpmachine)" = "$target"
  test "$("$target-gcc" -print-sysroot)" = "$prefix/$target/sysroot"
  if [[ $(dpkg-query -W -f='${Depends}' "$package") == *"ptos-binutils-$suffix"* ]]; then
    for component in binutils gcc sysroot; do
      test "$(dpkg-query -W -f='${Version}' "ptos-$component-$suffix")" = "$version"
    done
    test "$(dpkg-query -S "/usr/bin/$target-ld")" = "ptos-binutils-$suffix: /usr/bin/$target-ld"
    test "$(dpkg-query -S "$prefix/$target/bin/as")" = "ptos-binutils-$suffix: $prefix/$target/bin/as"
    test "$(dpkg-query -S "/usr/bin/$target-g++")" = "ptos-gcc-$suffix: /usr/bin/$target-g++"
    frontend=$(realpath "$("$target-g++" -print-prog-name=cc1plus)")
    test "$(dpkg-query -S "$frontend")" = "ptos-gcc-$suffix: $frontend"
    libgcc=$(realpath "$("$target-gcc" -print-libgcc-file-name)")
    test "$(dpkg-query -S "$libgcc")" = "ptos-gcc-$suffix: $libgcc"
    for file in include/stdio.h lib/libcmini.a lib/ptos-crt0.o; do
      path=$prefix/$target/sysroot/$file
      test "$(dpkg-query -S "$path")" = "ptos-sysroot-$suffix: $path"
    done
  fi
done
