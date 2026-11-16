require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on m68k"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 2

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.1"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "59d765374cb74676d134a36e325e3b35edbd71786d0b71d628ba3dc1328542e6"
  end

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
