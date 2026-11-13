require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v0.2.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "bbda5a4e4a3f2c6ab8ec6d6942a850b83259c3f1a599be60e35d00bdbbf7c0fd"
  end

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
