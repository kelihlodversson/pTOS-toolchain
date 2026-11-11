require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  desc "GCC, Binutils and C SDK for pTOS on ARM"
  include PtosToolchainFormula

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
