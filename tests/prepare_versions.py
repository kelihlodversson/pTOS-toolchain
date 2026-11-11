#!/usr/bin/env python3
"""Check every source recipe without compiling (requires a populated download cache)."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
PREPARE_FILES = {
    "config.sub", "bfd/config.bfd", "gas/configure.tgt", "ld/configure.tgt",
    "ld/emulparams/m68kelf.sh", "gcc/config.gcc", "libgcc/config.host",
}
TARGETS = {
    "m68k": "m68k-unknown-ptos-prgelf",
    "arm": "arm-unknown-ptos-elf",
    "x86_64": "x86_64-unknown-ptos-elfx32",
}


def check(cache, component, recipe):
    archive = cache / recipe["url"].rsplit("/", 1)[-1]
    patch = PROJECT / recipe["patch"]
    if not patch.is_file():
        patch = cache / recipe["patch"].rsplit("/", 1)[-1]
    for path, checksum in ((archive, recipe["sha256"]), (patch, recipe["patch_sha256"])):
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == checksum, path
    # Only extract files read by prepare.py or changed by the CrossMiNT patch.
    patch_text = patch.read_text()
    needed = PREPARE_FILES | set(re.findall(r"^--- a/(.*)$", patch_text, re.M))
    needed |= set(re.findall(r"^rename from (.*)$", patch_text, re.M))
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch) / "base"
        base.mkdir()
        with tarfile.open(archive) as source:
            for member in source:
                relative = member.name.partition("/")[2]
                if relative in needed and member.isfile():
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(source.extractfile(member).read())
        for arch, target in TARGETS.items():
            root = Path(scratch) / arch
            shutil.copytree(base, root)
            if arch == "m68k":
                with patch.open() as stream:
                    subprocess.run(["patch", "-d", str(root), "-p1", "--batch", "--forward", "--silent"],
                                   stdin=stream, check=True)
            for directory in ("include", "gcc/config/m68k", "gcc/config/i386"):
                (root / directory).mkdir(parents=True, exist_ok=True)
            subprocess.run(["python3", str(PROJECT / "prepare.py"), component, arch, str(root)], check=True)
            canonical = subprocess.check_output(["sh", str(root / "config.sub"), target], text=True).strip()
            assert canonical == target, (recipe["version"], arch, canonical)
    print(f"{component} {recipe['version']}: source preparation passed", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    recipes = json.loads((PROJECT / "versions.json").read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(check, args.cache, component, recipe)
                   for component, entries in recipes.items() for recipe in entries]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
