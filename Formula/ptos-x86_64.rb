require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 2

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.1"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "3e6eb9e0ed7fddf75f99177fd6bfccbc00fb32567f1e8c3985d0dd1e99eba46c"
  end

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
