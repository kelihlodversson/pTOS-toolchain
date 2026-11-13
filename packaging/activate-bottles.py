#!/usr/bin/env python3
"""Apply published bottle metadata only while the release recipes still match."""

import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote


FORMULAE = {"ptos-arm", "ptos-m68k", "ptos-x86_64"}
BLOCK = re.compile(r"^  bottle do\n.*?^  end\n", re.MULTILINE | re.DOTALL)


def ruby_string(value):
    return json.dumps(value).replace("#{", r"\#{").replace("#@", r"\#@").replace("#$", r"\#$")


def activate(repository, metadata, github_repo, tag, release_sha):
    recipes = [f"Formula/{name}.rb" for name in sorted(FORMULAE)] + ["lib/ptos_toolchain_formula.rb"]
    for path in recipes:
        released = subprocess.check_output(["git", "show", f"{release_sha}:{path}"], cwd=repository, text=True)
        current = (repository / path).read_text()
        if path.startswith("Formula/"):
            # Existing bottle blocks are output, not recipe inputs. Ignoring
            # them makes reruns and upgrades of a previous bottle block safe.
            released = re.sub(r"\n{3,}", "\n\n", BLOCK.sub("", released))
            current = re.sub(r"\n{3,}", "\n\n", BLOCK.sub("", current))
        if released != current:
            raise ValueError("Formula recipes changed since the release; rebuild bottles before activation")
    helper = (repository / "lib/ptos_toolchain_formula.rb").read_text()
    version = re.search(r'^      version "([^"]+)"$', helper, re.MULTILINE)
    if not version:
        raise ValueError("Cannot determine shared formula version")
    root = f"https://github.com/{github_repo}/releases/download/{quote(tag, safe='')}"
    updates = {}
    for path in sorted(metadata.glob("*.bottle.json")):
        entries = json.loads(path.read_text())
        if len(entries) != 1:
            raise ValueError("Expected one formula per metadata file")
        full_name, entry = next(iter(entries.items()))
        name = entry["formula"]["name"]
        if name not in FORMULAE or name in updates or full_name != f"kelihlodversson/ptos-toolchain/{name}":
            raise ValueError(f"Unexpected or duplicate formula: {full_name}")
        formula = repository / "Formula" / f"{name}.rb"
        source = formula.read_text()
        revision = re.search(r"^  revision (\d+)$", source, re.MULTILINE)
        pkg_version = version[1] + (f"_{revision[1]}" if revision and int(revision[1]) else "")
        if entry["formula"]["pkg_version"] != pkg_version:
            raise ValueError(f"Version mismatch for {name}")
        bottle = entry["bottle"]
        if bottle["root_url"] != root:
            raise ValueError("Bottle URL does not match this release")
        rebuild = bottle.get("rebuild", 0)
        if type(rebuild) is not int or rebuild < 0:
            raise ValueError("Invalid bottle rebuild")
        lines = ["  bottle do", f"    root_url {ruby_string(root)}"]
        if rebuild:
            lines.append(f"    rebuild {rebuild}")
        if not bottle["tags"]:
            raise ValueError("No bottle host platforms")
        for host, details in sorted(bottle["tags"].items()):
            if not re.fullmatch(r"[a-z][a-z0-9_]*", host) or not re.fullmatch(r"[0-9a-f]{64}", details["sha256"]):
                raise ValueError("Invalid host platform or checksum")
            cellar = details.get("cellar", bottle.get("cellar"))
            if cellar in ("any", "any_skip_relocation"):
                cellar = f":{cellar}"
            elif isinstance(cellar, str) and cellar.startswith("/"):
                cellar = ruby_string(cellar)
            else:
                raise ValueError("Missing or invalid bottle Cellar restriction")
            lines.append(f'    sha256 cellar: {cellar}, {host}: "{details["sha256"]}"')
        block = "\n".join([*lines, "  end", ""])
        if BLOCK.search(source):
            if len(BLOCK.findall(source)) != 1:
                raise ValueError("Multiple bottle blocks")
            source = BLOCK.sub(lambda _: block, source, count=1)
        else:
            anchor = (re.search(r'^  revision \d+\n', source, re.MULTILINE)
                      or re.search(r'^  homepage "[^"\n]+"\n', source, re.MULTILINE))
            if not anchor:
                raise ValueError(f"Cannot find bottle insertion point in {name}")
            source = source[:anchor.end()] + "\n" + block + source[anchor.end():]
        updates[name] = (formula, source)
    if set(updates) != FORMULAE:
        raise ValueError("Incomplete bottle metadata set")
    # Validate every formula before writing any changes.
    for formula, source in updates.values():
        formula.write_text(source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("github_repo")
    parser.add_argument("tag")
    parser.add_argument("release_sha")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    activate(args.repository, args.metadata, args.github_repo, args.tag, args.release_sha)
