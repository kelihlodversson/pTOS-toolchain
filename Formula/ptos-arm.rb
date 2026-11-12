require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on ARM"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v0.1.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "85e184814777e2a32fd783ed541fa08c1e32ece8703748531f3fb045cea7f5fb"
  end

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
