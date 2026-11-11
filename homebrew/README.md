# Homebrew tap development

The tap lives in this repository. `Formula/ptos-m68k.rb`, `ptos-arm.rb` and
`ptos-x86_64.rb` use the shared implementation in
`lib/ptos_toolchain_formula.rb`. No separate tap repository is needed.

The first formula release uses GCC 16.2.0 and Binutils 2.45. Its SDK source
is pinned to commit `bb00f4c276504cc80cc20fd2e9235621c6f9e3ba`, which includes
the GCC 16 MiNT port and runtime fixes. Formula changes do not implicitly
change the SDK sources. Update the source commit, its archive checksum,
resource checksums and explicit build versions together when releasing a
new SDK; use a formula revision for changes within the same GCC version.

Homebrew fetches the GCC, Binutils, libcmini and kconfiglib resources before
the build. The installer populates the normal build script's download cache
and libcmini source directory, so `build.sh` and `install-libcmini.sh` do not
need to download anything in the build sandbox. kconfiglib's Python modules
are used directly during configuration; there is no pip invocation or
runtime Python dependency.

The SDKs install into separate Cellar prefixes. Target-specific executables,
libraries and man pages retain their target names. Shared GCC/Binutils Info
manuals and section 7 man pages move into each formula's own share directory
to avoid link conflicts when installing more than one SDK.

To try an unpublished branch, commit the formula changes first, then tap the
local checkout under a development name:

```sh
brew tap kelihlodversson/ptos-dev /absolute/path/to/pTOS-toolchain
brew trust --formula kelihlodversson/ptos-dev/ptos-arm
brew info kelihlodversson/ptos-dev/ptos-arm
brew install --build-from-source kelihlodversson/ptos-dev/ptos-arm
brew test kelihlodversson/ptos-dev/ptos-arm
```

On Homebrew versions without `brew trust`, omit that command. Review and trust
the other formulae individually when testing them as well.

The local tap is a clone. Pull subsequent committed changes in its directory
with `git -C "$(brew --repository kelihlodversson/ptos-dev)" pull --ff-only`.
Do not install the development and published versions of the same target
together: their executable names are identical.

The Homebrew SDK workflow installs each formula from source on macOS, runs
its installed smoke test and checks dynamic library linkage. Before merging,
also verify that all three can be linked simultaneously. Bottle
building and publication are intentionally left for a later change; GCC's
embedded Cellar/sysroot paths need relocation testing first.
