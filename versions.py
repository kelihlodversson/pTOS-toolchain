#!/usr/bin/env python3
"""Select a checksum-pinned CrossMiNT source recipe."""

import argparse
import json
from pathlib import Path


def main():
    recipes = json.loads(Path(__file__).with_name("versions.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=recipes)
    parser.add_argument("version", nargs="?", default="latest")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    entries = recipes[args.component]
    if args.list:
        print(" ".join(entry["version"] for entry in entries))
        return
    selected = entries[-1]["version"] if args.version == "latest" else args.version
    entry = next((entry for entry in entries if entry["version"] == selected), None)
    if entry is None:
        parser.error(f"unsupported {args.component} version: {args.version}")
    for key in ("version", "url", "sha256", "patch", "patch_sha256"):
        print(entry[key])


if __name__ == "__main__":
    main()
