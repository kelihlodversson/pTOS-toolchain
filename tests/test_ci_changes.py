#!/usr/bin/env python3
"""Protect compiler CI coverage while filtering packaging-only changes."""

from pathlib import Path
import runpy
import unittest


needs_sdk_build = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / ".github/scripts/sdk_changes.py")
)["needs_sdk_build"]


class SdkChangesTests(unittest.TestCase):
    def test_homebrew_only_changes_skip_compiler_builds(self):
        self.assertFalse(needs_sdk_build([
            "Formula/ptos-arm.rb", "lib/ptos_toolchain_formula.rb",
            ".github/workflows/homebrew.yml", "homebrew/README.md",
            "packaging/prepare-bottles.py", "tests/test_bottles.py",
        ]))

    def test_debian_only_changes_skip_compiler_builds(self):
        self.assertFalse(needs_sdk_build([
            ".github/workflows/release-deb.yml", "packaging/package-deb.py",
            "packaging/copyright", "tests/test_deb.py",
        ]))

    def test_each_toolchain_input_still_builds(self):
        for path in (
            "build.sh", "host.sh", "versions.py", "versions.json", "prepare.py",
            "install-libcmini.sh", "sysroot/locale.h",
            "patches/gcc-16.2.0-mint.patch", "patches/binutils/fix.patch",
            "tests/smoke.sh", ".github/workflows/build.yml",
            ".github/scripts/sdk_changes.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(needs_sdk_build([path]))

    def test_mixed_changes_still_build(self):
        self.assertTrue(needs_sdk_build(["Formula/ptos-arm.rb", "build.sh"]))

    def test_new_inputs_default_to_building(self):
        self.assertTrue(needs_sdk_build(["new-build-input.txt"]))

    def test_documentation_and_empty_changes_skip_builds(self):
        self.assertFalse(needs_sdk_build(["README.md", "validation/new-result.md"]))
        self.assertFalse(needs_sdk_build([]))


if __name__ == "__main__":
    unittest.main()
