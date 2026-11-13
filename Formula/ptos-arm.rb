require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on ARM"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 1

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
