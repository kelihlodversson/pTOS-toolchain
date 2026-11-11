require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  include PtosToolchainFormula

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
