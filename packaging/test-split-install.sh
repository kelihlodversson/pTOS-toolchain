#!/usr/bin/env bash
# Run on a clean, disposable Ubuntu runner with the release artifacts.
set -euo pipefail
mode=${1:?Expected components, single or all}
assets=$(realpath "${2:?Expected release artifact directory}")
version=$(dpkg-deb -f "$assets"/ptos-toolchain_*.deb Version)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"

if [[ $mode == components ]]; then
  python3 packaging/publish-apt.py --verify-assets "$assets" "$version"
  cd "$work"
  printf '.text\n.byte 0\n' > input.s
  printf 'int entry(void) { return 42; }\n' > input.c
  cat > input.cc <<'EOF'
template<class T> T remainder(T n, T d) { return n % d; }
static volatile unsigned long long value = 23, divisor = 4;
extern "C" int entry() { return remainder(value, divisor); }
EOF
  for arch in m68k arm x86_64; do
    suffix=${arch//_/-}
    case $arch in
      m68k) target=m68k-unknown-ptos-prgelf ;;
      arm) target=arm-unknown-ptos-elf ;;
      x86_64) target=x86_64-unknown-ptos-elfx32 ;;
    esac
    binutils=$assets/ptos-binutils-${suffix}_${version}_amd64.deb
    gcc=$assets/ptos-gcc-${suffix}_${version}_amd64.deb
    sudo apt-get install -y "$binutils"
    test ! -e "/usr/bin/$target-gcc"
    "$target-as" input.s -o input.o
    "$target-ld" -r input.o -o combined.o
    "$target-ar" rcs libcombined.a combined.o
    test "$("$target-ar" t libcombined.a)" = combined.o
    "$target-objdump" -f combined.o

    sudo apt-get install -y "$binutils" "$gcc"
    test ! -d "/opt/ptos/$arch/$target/sysroot"
    "$target-gcc" -ffreestanding -c input.c -o c.o
    "$target-g++" -std=c++17 -ffreestanding -fno-exceptions -fno-rtti -c input.cc -o cxx.o
    "$target-gcc" -nostdlib -Wl,-e,entry cxx.o -lgcc -o bare.elf
    sudo apt-get purge -y "ptos-gcc-$suffix" "ptos-binutils-$suffix"
  done
  cd -
  # The documented four-file install works with only Ubuntu's APT sources.
  sudo apt-get install -y "$assets"/ptos-{sdk,binutils,gcc,sysroot}-m68k_"${version}"_amd64.deb
  bash packaging/test-installed.sh "$version" m68k
  sudo apt-get purge -y ptos-{sdk,binutils,gcc,sysroot}-m68k
  sudo apt-get install -y "$assets"/*.deb
  test "$(dpkg-query -W -f='${Version}' ptos-toolchain)" = "$version"
  bash packaging/test-installed.sh "$version"
  exit
fi

case $mode in
  single) package=ptos-sdk-m68k; selection=m68k; suffixes=(m68k) ;;
  all) package=ptos-toolchain; selection=all; suffixes=(m68k arm x86-64) ;;
  *) exit 2 ;;
esac

# Pin the published baseline. Its bytes and checksums remain those from v1.0.3.
old_version=1.0.3
gh release download "v$old_version" --repo kelihlodversson/pTOS-toolchain \
  --pattern '*.deb' --pattern SHA256SUMS --dir "$work/historical"
repository=$work/repository
python3 packaging/make-test-repository.py "$assets" "$repository" --historical "$work/historical"
chmod -R a+rX "$repository"
sudo install -m 644 "$repository/ptos-archive-keyring.gpg" /usr/share/keyrings/ptos-ci-fixture.gpg
printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ptos-ci-fixture.gpg] file:%s stable main\n' "$repository" |
  sudo tee /etc/apt/sources.list.d/ptos-ci-fixture.list
sudo apt-get -o APT::Update::Error-Mode=any update

sudo apt-get install -y "$package=$version"
test "$(dpkg-query -W -f='${Version}' "$package")" = "$version"
bash packaging/test-installed.sh "$version" "$selection"
installed=("$package")
historical=("$package=$old_version")
for suffix in "${suffixes[@]}"; do
  if [[ $mode == all ]]; then
    grep -Fx "ptos-sdk-$suffix" < <(apt-mark showauto)
    installed+=("ptos-sdk-$suffix")
    historical+=("ptos-sdk-$suffix=$old_version")
  fi
  for component in binutils gcc sysroot; do
    grep -Fx "ptos-$component-$suffix" < <(apt-mark showauto)
    installed+=("ptos-$component-$suffix")
  done
done
if [[ $mode == single ]]; then
  test ! -d /opt/ptos/arm
  test ! -d /opt/ptos/x86_64
fi
sudo apt-get purge -y "${installed[@]}"

# Pin the old SDKs too because the same repository already offers the split candidates.
sudo apt-get install -y "${historical[@]}"
test "$(dpkg-query -W -f='${Version}' "$package")" = "$old_version"
bash packaging/test-installed.sh "$old_version" "$selection"
sudo apt-get install -y "$package=$version"
test "$(dpkg-query -W -f='${Version}' "$package")" = "$version"
bash packaging/test-installed.sh "$version" "$selection"
