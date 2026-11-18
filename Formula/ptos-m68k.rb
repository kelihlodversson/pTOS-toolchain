require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on m68k"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 3

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.3"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "f0466cc872c444bb02bcecfcc14a6f0fb6d89fa2a0c82075b3302a36e8b32c17"
  end

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
