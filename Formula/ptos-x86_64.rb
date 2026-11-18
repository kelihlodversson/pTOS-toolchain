require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  revision 3

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v1.0.3"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "eab1abe6a074d6e2dea11d5353d6eb0899f605ceb6ac70f70563750caf89a905"
  end

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
