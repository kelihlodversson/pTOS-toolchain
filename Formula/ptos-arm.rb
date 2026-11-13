require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on ARM"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v0.2.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "15ba233799a2bb8f378c818447cc8aeb790567912b9da6e362c4ca6d80278c83"
  end

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
