require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on ARM"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 1

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "2f84d01af5fdb059b012af4f0d7c9d572386ef94a3050310dcbeccc6af38407f"
  end

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
