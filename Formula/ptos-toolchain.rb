class PtosToolchain < Formula
  desc "All-target cross-development SDK selection for pTOS"
  homepage "https://github.com/kelihlodversson/pTOS-toolchain"
  url "https://github.com/kelihlodversson/pTOS-toolchain/archive/bb00f4c276504cc80cc20fd2e9235621c6f9e3ba.tar.gz"
  version "0.1.0"
  sha256 "9c8f89fd97d2150337be8b80e3a53dba2dc9ab35614fc50d08661bdc9814f861"
  license all_of: ["GPL-3.0-or-later", "LGPL-2.1-or-later"]

  depends_on "kelihlodversson/ptos-toolchain/ptos-arm"
  depends_on "kelihlodversson/ptos-toolchain/ptos-m68k"
  depends_on "kelihlodversson/ptos-toolchain/ptos-x86_64"

  def install
    # Versioned provenance only; compilers are provided by runtime dependencies.
    pkgshare.install "versions.json" => "source-recipes.json"
  end

  test do
    %w[CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH SDKROOT].each do |key|
      ENV.delete key
    end
    {
      "ptos-m68k" => ["m68k", "m68k-unknown-ptos-prgelf"],
      "ptos-arm" => ["arm", "arm-unknown-ptos-elf"],
      "ptos-x86_64" => ["x86_64", "x86_64-unknown-ptos-elfx32"],
    }.each do |name, (arch, target)|
      sdk = Formula["kelihlodversson/ptos-toolchain/#{name}"]
      assert_equal target, shell_output("#{sdk.opt_bin}/#{target}-gcc -dumpmachine").strip
      system "/bin/bash", sdk.pkgshare/"tests/smoke.sh", sdk.opt_prefix, arch
    end
  end
end
