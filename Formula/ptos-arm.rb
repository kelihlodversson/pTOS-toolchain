require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on ARM"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 2

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.1"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "6549e4d840f03dee99b9a2e858df2981d9dc520c21096bdf1f23b72e54e11f83"
  end

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
