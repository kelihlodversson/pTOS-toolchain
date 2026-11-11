#!/usr/bin/env python3
"""Check release filenames, checksums and completeness using Homebrew JSON fixtures."""

import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest


prepare = runpy.run_path(str(Path(__file__).resolve().parents[1] / "packaging/prepare-bottles.py"))["prepare"]
REPO = "kelihlodversson/pTOS-toolchain"
TAG = "v1.0.0"


class BottleReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for name in ("ptos-arm", "ptos-m68k", "ptos-x86_64"):
            local = f"{name}--16.2.0.arm64_tahoe.bottle.tar.gz"
            archive = self.directory / local
            archive.write_bytes(f"fixture for {name}".encode())
            data = {
                f"kelihlodversson/ptos-toolchain/{name}": {
                    "formula": {"name": name, "pkg_version": "16.2.0"},
                    "bottle": {
                        "root_url": f"https://github.com/{REPO}/releases/download/{TAG}",
                        "cellar": "/opt/homebrew/Cellar",
                        "rebuild": 0,
                        "tags": {"arm64_tahoe": {
                            "local_filename": local,
                            "filename": local.replace("--", "-"),
                            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                        }},
                    },
                },
            }
            (self.directory / f"{name}.bottle.json").write_text(json.dumps(data))

    def change_metadata(self, change):
        path = self.directory / "ptos-arm.bottle.json"
        data = json.loads(path.read_text())
        change(next(iter(data.values()))["bottle"])
        path.write_text(json.dumps(data))

    def test_release_names_and_checksums(self):
        prepare(self.directory, REPO, TAG)
        archives = list(self.directory.glob("*.tar.gz"))
        self.assertEqual(len(archives), 3)
        self.assertTrue(all("--" not in path.name for path in archives))
        for path in self.directory.glob("*.json"):
            bottle = next(iter(json.loads(path.read_text()).values()))["bottle"]
            entry = bottle["tags"]["arm64_tahoe"]
            self.assertEqual(hashlib.sha256((self.directory / entry["filename"]).read_bytes()).hexdigest(), entry["sha256"])

    def test_rejects_corrupt_archive_before_renaming(self):
        (self.directory / "ptos-x86_64--16.2.0.arm64_tahoe.bottle.tar.gz").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            prepare(self.directory, REPO, TAG)
        self.assertEqual(len(list(self.directory.glob("*--*.tar.gz"))), 3)

    def test_rejects_wrong_release(self):
        with self.assertRaisesRegex(ValueError, "Wrong release URL"):
            prepare(self.directory, REPO, "v2.0.0")

    def test_rejects_missing_target(self):
        (self.directory / "ptos-arm.bottle.json").unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete bottle set"):
            prepare(self.directory, REPO, TAG)

    def test_rejects_unsafe_download_filename(self):
        self.change_metadata(lambda bottle: bottle["tags"]["arm64_tahoe"].update(filename="..%2Fescape.bottle.tar.gz"))
        with self.assertRaisesRegex(ValueError, "Unsafe bottle filename"):
            prepare(self.directory, REPO, TAG)

    def test_rejects_wrong_download_filename(self):
        self.change_metadata(lambda bottle: bottle["tags"]["arm64_tahoe"].update(filename="wrong-16.2.0.arm64_tahoe.bottle.tar.gz"))
        with self.assertRaisesRegex(ValueError, "Wrong download filename"):
            prepare(self.directory, REPO, TAG)


if __name__ == "__main__":
    unittest.main()
