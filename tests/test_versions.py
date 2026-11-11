#!/usr/bin/env python3
"""Offline checks for version selection and argument validation."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class Versions(unittest.TestCase):
    def test_catalogue(self):
        recipes = json.loads((PROJECT / "versions.json").read_text())
        for component, entries in recipes.items():
            versions = [entry["version"] for entry in entries]
            if component == "gcc":
                self.assertTrue(all(int(version.split(".")[0]) >= 12 for version in versions))
            self.assertEqual(versions, sorted(set(versions), key=lambda v: tuple(map(int, v.split(".")))))
            for entry in entries:
                for field in ("sha256", "patch_sha256"):
                    self.assertRegex(entry[field], r"^[a-f0-9]{64}$")
                self.assertTrue(entry["url"].startswith(f"https://ftp.gnu.org/gnu/{component}/"))
                self.assertTrue(entry["patch"].startswith("patches/"))
                local_patch = PROJECT / entry["patch"]
                if local_patch.is_file():
                    import hashlib
                    self.assertEqual(hashlib.sha256(local_patch.read_bytes()).hexdigest(), entry["patch_sha256"])
                selected = subprocess.check_output(
                    ["python3", str(PROJECT / "versions.py"), component, entry["version"]], text=True
                ).splitlines()
                self.assertEqual(selected, [entry[key] for key in ("version", "url", "sha256", "patch", "patch_sha256")])
            latest = subprocess.check_output(
                ["python3", str(PROJECT / "versions.py"), component], text=True
            ).splitlines()[0]
            self.assertEqual(latest, versions[-1])

    def test_list(self):
        output = subprocess.check_output([str(PROJECT / "build.sh"), "--list-versions"], text=True)
        self.assertIn("gcc: ", output)
        self.assertIn("binutils: ", output)

    def test_invalid_selection_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as scratch:
            prefix = Path(scratch) / "prefix"
            for options in (("--gcc", "999"), ("--binutils", "../../bad"), ("--gcc",), ("--gcc", "11.5.0")):
                result = subprocess.run(
                    [str(PROJECT / "build.sh"), "m68k", str(prefix), *options],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(prefix.exists())


if __name__ == "__main__":
    unittest.main()
