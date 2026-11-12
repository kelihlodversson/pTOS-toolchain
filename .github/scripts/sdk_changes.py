#!/usr/bin/env python3
"""Skip compiler builds only when every changed path is known to be unrelated."""

import argparse
from fnmatch import fnmatchcase
import os
import subprocess


NON_SDK_PATHS = (
    "*.md",
    "Formula/*",
    "lib/ptos_toolchain_formula.rb",
    "homebrew/*",
    "packaging/*",
    "validation/*",
    ".github/workflows/homebrew.yml",
    ".github/workflows/release-deb.yml",
    "tests/test_bottles.py",
    "tests/test_bottle_activation.py",
    "tests/test_deb.py",
)


def needs_sdk_build(paths):
    # Unknown files deliberately trigger builds, including changes to this
    # classifier and build.yml. A new build input must not silently lose CI.
    return any(not any(fnmatchcase(path, pattern) for pattern in NON_SDK_PATHS) for path in paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    if args.event == "workflow_dispatch" or not args.base or set(args.base) == {"0"}:
        build = True
    else:
        # A PR uses its merge base; a push must cover every commit in the push.
        refs = [f"{args.base}...{args.head}"] if args.event == "pull_request" else [args.base, args.head]
        diff = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", "-z", *refs, "--"])
        build = needs_sdk_build(os.fsdecode(path) for path in diff.split(b"\0") if path)
    print(f"build={str(build).lower()}")


if __name__ == "__main__":
    main()
