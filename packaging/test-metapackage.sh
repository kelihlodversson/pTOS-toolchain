#!/usr/bin/env bash
# Fresh-runner installation requesting only the new metapackage.
set -euo pipefail
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"
if [[ $# == 0 ]]; then
  : "${GH_TOKEN:?Missing GH_TOKEN for public release download}"
  gh release download "${RELEASE_TAG:-v0.1.0}" --repo "${GH_REPO:-kelihlodversson/pTOS-toolchain}" \
    --pattern '*.deb' --pattern SHA256SUMS --dir "$work/assets"
  source=$work/assets
else
  source=$1
fi
for package in ptos-sdk-m68k ptos-sdk-arm ptos-sdk-x86-64; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    echo 'Metapackage test requires a clean runner without installed SDKs' >&2
    exit 1
  fi
done
python3 packaging/make-test-repository.py "$source" "$work/repository"
version=$(dpkg-deb -f "$work/repository"/pool/main/ptos-toolchain_*.deb Version)
chmod -R a+rX "$work/repository"
sudo install -m 644 "$work/repository/ptos-archive-keyring.gpg" /usr/share/keyrings/ptos-ci-fixture.gpg
printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ptos-ci-fixture.gpg] file:%s stable main\n' "$work/repository" |
  sudo tee /etc/apt/sources.list.d/ptos-ci-fixture.list
sudo apt-get -o APT::Update::Error-Mode=any update
sudo apt-get install -y "ptos-toolchain=$version"
test "$(dpkg-query -W -f='${Version}' ptos-toolchain)" = "$version"
for package in ptos-sdk-m68k ptos-sdk-arm ptos-sdk-x86-64; do
  apt-mark showauto | grep -Fx "$package"
done
bash packaging/test-installed.sh "$version"
