#!/usr/bin/env bash
set -euo pipefail
: "${APT_REPOSITORY_URL:?Missing APT_REPOSITORY_URL}"
: "${RELEASE_TAG:?Missing RELEASE_TAG}"
version=$(bash packaging/release-version.sh "$RELEASE_TAG")
key=$(mktemp)
trap 'rm -f "$key"' EXIT
curl -fsSL "$APT_REPOSITORY_URL/ptos-archive-keyring.gpg" -o "$key"
sudo install -m 644 "$key" /usr/share/keyrings/ptos-archive-keyring.gpg
printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ptos-archive-keyring.gpg] %s stable main\n' "$APT_REPOSITORY_URL" |
  sudo tee /etc/apt/sources.list.d/ptos.list
# Pages deployments and their metadata caches can take minutes to converge.
for attempt in {1..20}; do
  if sudo apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 update; then
    break
  fi
  if [[ $attempt == 20 ]]; then exit 1; fi
  sleep 15
done
packages=()
for arch in m68k arm x86_64; do
  package=ptos-sdk-${arch//_/-}
  apt-cache madison "$package" | awk -v expected="$version" '$3 == expected { found=1 } END { exit !found }'
  packages+=("$package=$version")
done
sudo apt-get install -y "${packages[@]}"
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
