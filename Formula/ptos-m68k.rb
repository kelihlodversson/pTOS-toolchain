require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on m68k"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v0.2.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "b896b5f49ac0170528b10b6843c7f0b25c79ad15c4cc9fef727e24f4480463d0"
  end

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
