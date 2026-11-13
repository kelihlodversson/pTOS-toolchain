require_relative "../lib/ptos_toolchain_formula"

class PtosM68k < Formula
  include PtosToolchainFormula

  desc "GCC, Binutils and C SDK for pTOS on m68k"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"

  bottle do
    root_url "https://github.com/kelihlodversson/pTOS-toolchain/releases/download/v0.1.0"
    sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe: "d4b148722750a849ae64ae92f354273ef66834874d387a509e56aa44f121747f"
  end

  def install
    install_ptos "m68k"
  end

  test do
    test_ptos "m68k"
  end
end
