# Homebrew bottle trust regression

Validated locally on Apple Silicon with Homebrew 7 on 2026-11-11.

A temporary tap contained a minimal formula using `require_relative` to load
an install helper from `lib/`, matching the SDK formula structure. The fixture
installed one shell executable and had no SDK build or dependency changes.

1. Trust the fixture formula, install with `--build-bottle`, and run
   `brew bottle --json`.
2. Uninstall it, then try to install its absolute bottle path with
   `HOMEBREW_DEVELOPER=1` and `--force-bottle`.
3. Confirm the same failure as CI: the embedded formula cannot resolve its
   shared helper from the uninstalled keg, and fallback to the tap is refused
   because uninstall removed the formula's trust entry.
4. Run `brew trust --formula` for the fixture again, then repeat installation.
   Homebrew warns about the embedded helper, falls back to the trusted tap
   formula and successfully pours the local bottle.
5. Confirm `brew info --json=v2` reports `poured_from_bottle: true`; run the
   fixture's `brew test` and `brew linkage --test --strict`. All pass.

The fixture was uninstalled, its tap removed and developer mode restored to
off afterward. Existing pTOS installations were not changed. This verifies
the Homebrew lifecycle fix; actual SDK bottle smoke tests remain in CI.
