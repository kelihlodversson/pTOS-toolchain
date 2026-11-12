#!/usr/bin/env python3
"""Validate a complete bottle set and give archives their public URL filenames."""

import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote


FORMULAE = {"ptos-arm", "ptos-m68k", "ptos-x86_64"}


def safe_filename(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_+.-]+", value):
        raise ValueError(f"Unsafe bottle filename: {value!r}")
    if not value.endswith(".tar.gz") or ".bottle" not in value:
        raise ValueError(f"Not a bottle archive: {value!r}")
    return value


def prepare(directory, repository, release_tag):
    root_url = f"https://github.com/{repository}/releases/download/{quote(release_tag, safe='')}"
    seen = set()
    renames = []
    for metadata in sorted(directory.glob("*.bottle.json")):
        entries = json.loads(metadata.read_text())
        if len(entries) != 1:
            raise ValueError(f"Expected one formula in {metadata.name}")
        full_name, entry = next(iter(entries.items()))
        name = entry["formula"]["name"]
        if name not in FORMULAE or name in seen:
            raise ValueError(f"Unexpected or duplicate formula: {name}")
        if full_name != f"kelihlodversson/ptos-toolchain/{name}":
            raise ValueError(f"Unexpected tap: {full_name}")
        bottle = entry["bottle"]
        if bottle["root_url"] != root_url:
            raise ValueError(f"Wrong release URL for {name}")
        if len(bottle["tags"]) != 1:
            raise ValueError(f"Expected one host platform for {name}")
        tag, details = next(iter(bottle["tags"].items()))
        source = directory / safe_filename(details["local_filename"])
        target = directory / safe_filename(unquote(details["filename"]))
        rebuild = bottle.get("rebuild", 0)
        suffix = f".{rebuild}" if rebuild else ""
        expected = f"{name}-{entry['formula']['pkg_version']}.{tag}.bottle{suffix}.tar.gz"
        if target.name != expected:
            raise ValueError(f"Wrong download filename for {name}: {target.name}")
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Missing bottle archive: {source.name}")
        digest = hashlib.sha256()
        with source.open("rb") as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != details["sha256"]:
            raise ValueError(f"Checksum mismatch: {source.name}")
        if target != source and target.exists():
            raise ValueError(f"Bottle destination already exists: {target.name}")
        seen.add(name)
        renames.append((source, target))
    if seen != FORMULAE:
        raise ValueError(f"Incomplete bottle set: {sorted(seen)}")
    if set(directory.glob("*.bottle*.tar.gz")) != {source for source, _ in renames}:
        raise ValueError("Unexpected bottle archives")
    # Validate the entire set before changing any filenames.
    for source, target in renames:
        source.rename(target)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("Usage: prepare-bottles.py <directory> <owner/repo> <release-tag>")
    prepare(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
