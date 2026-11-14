require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on m68k"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 1

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "6068a3065664be22e9b17947ed3be19bf113eb625df28c68656a4491c37389e0"
  end

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
