require_relative "../lib/ptos_toolchain_formula"

class PtosX8664 < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on x86-64 x32"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v0.1.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "b17bce9dbf66adb19c29bc9c5a78683547de803d10deb091af56247e94154082"
  end

  def install
    install_ptos "x86_64"
  end

  test do
    test_ptos "x86_64"
  end
end
