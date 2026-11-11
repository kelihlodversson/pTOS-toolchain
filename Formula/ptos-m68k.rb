require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  desc "GCC, Binutils and C SDK for pTOS on m68k"
  include PtosToolchainFormula

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
