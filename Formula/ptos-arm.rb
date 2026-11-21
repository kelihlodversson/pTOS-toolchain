require_relative "../lib/ptos_toolchain_formula"

class PtosArm < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on ARM"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 3

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.3"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "c34546869496757ea8078dc862ab27b6a74503d4e468895b058c095d9b61a26b"
  end

  def install
    install_ptos "arm"
  end

  test do
    test_ptos "arm"
  end
end
