#!/usr/bin/env python3
"""Exercise release activation against real Git recipe snapshots."""

import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest


activate = runpy.run_path(str(Path(__file__).resolve().parents[1] / "packaging/activate-bottles.py"))["activate"]
REPO = "kelihlodversson/pTOS-toolchain"


class BottleActivationTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "Formula").mkdir()
        (self.root / "lib").mkdir()
        self.metadata = self.root / "metadata"
        self.metadata.mkdir()
        (self.root / "lib/ptos_toolchain_formula.rb").write_text('      version "16.2.0"\n')
        for name in ("ptos-arm", "ptos-m68k", "ptos-x86_64"):
            (self.root / f"Formula/{name}.rb").write_text('class Fixture < Formula\n  homepage "https://example.org"\n\n  def install\n  end\nend\n')
            entry = {f"kelihlodversson/ptos-toolchain/{name}": {
                "formula": {"name": name, "pkg_version": "16.2.0"},
                "bottle": {"root_url": f"https://github.com/{REPO}/releases/download/v1.0.0",
                           "cellar": "/opt/homebrew/Cellar", "rebuild": 0,
                           "tags": {"arm64_tahoe": {"sha256": "a" * 64}}},
            }}
            (self.metadata / f"{name}.bottle.json").write_text(json.dumps(entry))
        self.git("init", "-q")
        self.git("-c", "user.name=Test", "-c", "user.email=test@local", "add", "Formula", "lib")
        self.git("-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-qm", "Release recipes")
        self.sha = self.git("rev-parse", "HEAD")

    def run_activation(self):
        activate(self.root, self.metadata, REPO, "v1.0.0", self.sha)

    def change_metadata(self, change):
        path = self.metadata / "ptos-arm.bottle.json"
        data = json.loads(path.read_text())
        change(next(iter(data.values())))
        path.write_text(json.dumps(data))

    def test_inserts_blocks_and_reruns_without_duplicates(self):
        self.run_activation()
        first = (self.root / "Formula/ptos-arm.rb").read_text()
        self.assertIn('sha256 cellar: "/opt/homebrew/Cellar", arm64_tahoe:', first)
        self.run_activation()
        self.assertEqual(first, (self.root / "Formula/ptos-arm.rb").read_text())
        self.assertEqual(first.count("bottle do"), 1)

    def test_replaces_old_bottle_and_preserves_relocation_metadata(self):
        self.run_activation()
        self.change_metadata(lambda entry: entry["bottle"].update(rebuild=2, cellar="any_skip_relocation"))
        self.run_activation()
        source = (self.root / "Formula/ptos-arm.rb").read_text()
        self.assertIn("rebuild 2", source)
        self.assertIn("cellar: :any_skip_relocation", source)
        self.assertEqual(source.count("bottle do"), 1)

    def test_rejects_changed_recipe(self):
        (self.root / "lib/ptos_toolchain_formula.rb").write_text('      version "17.0.0"\n')
        with self.assertRaisesRegex(ValueError, "recipes changed"):
            self.run_activation()

    def test_rejects_wrong_release_without_writing_formulae(self):
        self.change_metadata(lambda entry: entry["bottle"].update(root_url="https://wrong.example"))
        with self.assertRaisesRegex(ValueError, "URL"):
            self.run_activation()
        self.assertNotIn("bottle do", (self.root / "Formula/ptos-arm.rb").read_text())

    def test_rejects_version_mismatch(self):
        self.change_metadata(lambda entry: entry["formula"].update(pkg_version="15.3.0"))
        with self.assertRaisesRegex(ValueError, "Version mismatch"):
            self.run_activation()

    def test_rejects_incomplete_set_without_partial_writes(self):
        (self.metadata / "ptos-x86_64.bottle.json").unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.run_activation()
        self.assertNotIn("bottle do", (self.root / "Formula/ptos-arm.rb").read_text())


if __name__ == "__main__":
    unittest.main()
