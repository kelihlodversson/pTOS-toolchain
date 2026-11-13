require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on m68k"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 1

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
