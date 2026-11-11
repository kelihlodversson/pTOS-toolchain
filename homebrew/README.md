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
manuals and section 7 man pages move into each formula's own share directory.
The BFD dependency plugin gets a formula-specific filename; BFD discovers it
by scanning the plugin directory. These paths avoid link conflicts when
installing more than one SDK.

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

The Homebrew SDK workflow installs each formula from source on `macos-latest`
with `brew install --build-bottle`, runs its installed smoke test and checks
for missing or undeclared dynamic library dependencies. It then runs
`brew bottle --json`, uninstalls the source build and installs the local bottle.
CI verifies that Homebrew actually poured the bottle, then repeats the smoke
test and strict linkage check before uploading the archive and JSON checksum
metadata as a GitHub Actions artifact. All three targets run sequentially on
one macOS runner and share one artifact, retained for 14 days and available
from the workflow run's summary page. All three source installations coexist
before bottling; after uninstalling them, CI pours all three bottles together
and repeats every SDK test and linkage check. Both the compiler and bottle
jobs allow up to four hours for the sequential builds.
The local reinstall step sets `HOMEBREW_DEVELOPER=1` because Homebrew 7 disables
installation from file paths by default; this is limited to that CI step.
It also restores per-formula trust after uninstalling, since Homebrew 7 removes
that trust on uninstall. The embedded formula references the shared helper,
so Homebrew may warn that it cannot load it from the bottle and fall back to
the formula in the registered tap. That fallback still pours the local archive;
CI verifies this with the installed `poured_from_bottle` receipt field.

Bottles cover the host macOS version and CPU architecture of `macos-latest`;
the three formula names identify the cross-compilation targets. Homebrew
determines the bottle's Cellar compatibility without `--skip-relocation`.
The reinstall check validates pouring into the runner's normal prefix; it
does not establish compatibility with other macOS versions, Intel Macs or
custom Homebrew prefixes. The generated JSON records any Cellar restriction.

Pull requests and ordinary pushes produce CI artifacts only. The **SDK release
packages** workflow reuses the same build and test jobs when a GitHub Release
is published. It sets the bottle root URL to that release, then publishes the
three tested archives and their `.bottle.json` metadata alongside the Debian
packages. Both Debian verification and every bottle test must pass before the
shared publication job runs. `SHA256SUMS` covers the Debian packages, bottle
archives and JSON metadata. Only the publication job has `contents: write`.
Manual dispatch builds both package types as artifacts without release uploads.

Homebrew's local bottle names use `--` between the formula name and version,
but its download URLs use `-`. `packaging/prepare-bottles.py` verifies that the
metadata describes all three formulae in this tap, checks release URLs and
archive checksums, then renames archives to their metadata's download names.
Cellar restrictions and checksums from `brew bottle` are retained unchanged.

### Activate published bottles

Publication does not edit the tap automatically. After a release build succeeds,
download that release's metadata and merge the bottle blocks in a follow-up PR:

```sh
tag=v1.0.0 # Select the release to activate.
metadata=$(mktemp -d)
gh release download "$tag" --repo kelihlodversson/pTOS-toolchain \
  --pattern '*.bottle.json' --dir "$metadata"
brew bottle --merge --write --no-commit "$metadata"/*.bottle.json
```

Run this from the registered tap checkout, review the changes under `Formula/`,
and run `brew style` on the changed formulae before committing. The metadata
includes the release URL, archive checksums and detected Cellar compatibility.
Merge it only while the formula version, revision, resources and source commit
still match the release build. A later formula update needs new bottles.

Once these blocks are merged, `brew update` followed by a normal `brew install`
uses a matching bottle automatically. Other host platforms or incompatible
Cellar prefixes continue to build from source. Until the activation PR is
merged, normal installation also builds from source. Release reruns replace
assets of the same name, so do not rebuild an already activated release unless
its bottle metadata is updated together.

[Local Apple Silicon validation](../validation/homebrew-macos.md)
also verified simultaneous installation and relinking of all three SDKs.
Repeat that coexistence check when changing shared installation paths.
