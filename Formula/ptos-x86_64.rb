require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 1

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "3bc8c2b5135a8b596880f38b48ed6c8ba16e1df9c032a4a9b3de1427e7ea0982"
  end

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
