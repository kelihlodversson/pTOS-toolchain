require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
