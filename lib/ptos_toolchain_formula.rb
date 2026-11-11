# typed: true
# frozen_string_literal: true

# Shared implementation for the three formulae in this tap.
module PtosToolchainFormula
  def self.included(formula)
    formula.class_eval do
      url "https://github.com/kelihlodversson/pTOS-toolchain/archive/bb00f4c276504cc80cc20fd2e9235621c6f9e3ba.tar.gz"
      version "16.2.0"
      sha256 "9c8f89fd97d2150337be8b80e3a53dba2dc9ab35614fc50d08661bdc9814f861"
      license all_of: ["GPL-3.0-or-later", "LGPL-2.1-or-later"]

      depends_on "bison" => :build
      depends_on "flex" => :build
      depends_on "m4" => :build
      depends_on "make" => :build
      depends_on "python@3.13" => :build
      depends_on "xz" => :build
      depends_on "gmp"
      depends_on "libmpc"
      depends_on "mpfr"

      resource "gcc" do
        url "https://ftp.gnu.org/gnu/gcc/gcc-16.2.0/gcc-16.2.0.tar.xz"
        sha256 "e6738e29597f733270731aa90600f37ffdc045079dfc27ec7e8192cc81085c3e"
      end

      resource "binutils" do
        url "https://ftp.gnu.org/gnu/binutils/binutils-2.45.tar.xz"
        sha256 "c50c0e7f9cb188980e2cc97e4537626b1672441815587f1eab69d2a1bfbef5d2"
      end

      resource "libcmini" do
        url "https://github.com/kelihlodversson/libcmini/archive/c85f67a52679b68782c49fd967732d14bfe87841.tar.gz"
        version "c85f67a52679b68782c49fd967732d14bfe87841"
        sha256 "e436e081440c5bba81ef4b2327e82346292c8185e06c0a6cad8f576cd422b38d"
      end

      resource "kconfiglib" do
        url "https://files.pythonhosted.org/packages/59/29/d557718c84ef1a8f275faa4caf8e353778121beefbe9fadfa0055ca99aae/kconfiglib-14.1.0.tar.gz"
        sha256 "bed2cc2216f538eca4255a83a4588d8823563cdd50114f86cf1a2674e602c93c"
      end
    end
  end

  def install_ptos(arch)
    work = buildpath/"work"
    downloads = work/"downloads"
    downloads.mkpath
    %w[gcc binutils].each do |name|
      source = resource(name)
      cp source.cached_download, downloads/File.basename(source.url)
    end
    resource("libcmini").stage work/arch/"libcmini-#{resource("libcmini").version}"
    resource("kconfiglib").stage do
      (buildpath/"python-modules").install Dir["*.py"]
    end

    ENV["MAKE"] = Utils::Path.formula_opt_bin("make")/"gmake"
    ENV["JOBS"] = ENV.make_jobs.to_s
    ENV["PTOS_WORKDIR"] = work
    ENV["PTOS_CACHE"] = downloads
    ENV["PYTHONPATH"] = buildpath/"python-modules"
    ENV.prepend_path "PATH", Utils::Path.formula_opt_bin("python@3.13")
    # Also work when Homebrew's superenv hides the brew executable.
    %w[gmp mpfr libmpc].each do |name|
      ENV.append "CPPFLAGS", "-I#{Utils::Path.formula_opt_include(name)}"
      ENV.append "LDFLAGS", "-L#{Utils::Path.formula_opt_lib(name)}"
    end

    system "/bin/bash", "build.sh", arch, prefix,
           "--gcc", "16.2.0", "--binutils", "2.45"
    (pkgshare/"tests").install "tests/smoke.sh"
    # GCC and Binutils install common manuals. Keep them in a formula-specific
    # directory so the SDKs can be linked side by side.
    pkgshare.install info if info.exist?
    pkgshare.install man7 if man7.exist?
  end

  def test_ptos(arch)
    system "/bin/bash", pkgshare/"tests/smoke.sh", prefix, arch
  end
end
