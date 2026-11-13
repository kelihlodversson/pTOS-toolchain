#!/usr/bin/env python3
"""Check issue #15 with an SDK compiler; optionally execute using qemu-m68k."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parent


def check_assembly(assembly):
    for line in assembly.splitlines():
        match = re.match(r"\s*move\.?[bwl]?\s+(.+)", line)
        if not match:
            continue
        # Split operands outside an indexed address's parentheses.
        operands = re.split(r",(?![^()]*\))", match[1].split("|")[0])
        if len(operands) != 2:
            continue
        for operand, other in (operands, operands[::-1]):
            update = re.search(r"(?:-\(%?(a[0-7]|sp)\)|\(%?(a[0-7]|sp)\)\+)", operand)
            if update:
                reg = update[1] or update[2]
                if re.search(rf"(?<![\w])%?{reg}(?![\w])", other):
                    raise AssertionError(f"auto-inc-dec register reused in MOVE: {line.strip()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compiler")
    parser.add_argument("--runner", help="qemu-m68k executable for a required runtime check")
    args = parser.parse_args()
    version = subprocess.check_output([args.compiler, "-dumpversion"], text=True)
    abis = [[], ["-mfastcall"]] if int(version.split(".")[0]) >= 13 else [[]]
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for cpu in ("-m68000", "-m68020", "-m68040"):
            for opt in ("-Os", "-O2"):
                for abi in abis:
                    flags = [cpu, opt, "-msoft-float", "-fomit-frame-pointer",
                             "-fauto-inc-dec", *abi]
                    subprocess.run([args.compiler, *flags, "-S",
                                    str(PROJECT / "m68k-auto-inc-dec.c"),
                                    "-o", str(root / "copy.s")], check=True)
                    check_assembly((root / "copy.s").read_text())
                    if args.runner:
                        # main has no arguments and returns in D0 in both ABIs.
                        subprocess.run([args.compiler, *flags, "-c",
                                        str(PROJECT / "m68k-auto-inc-dec.c"),
                                        "-o", str(root / "copy.o")], check=True)
                        subprocess.run([args.compiler, *flags, "-ffreestanding", "-c",
                                        str(PROJECT / "m68k-auto-inc-dec-runtime.c"),
                                        "-o", str(root / "runtime.o")], check=True)
                        subprocess.run([args.compiler, *flags, "-nostdlib", "-static",
                                        str(root / "copy.o"), str(root / "runtime.o"),
                                        "-Wl,-Ttext=0x10000,-e,_start", "-o", str(root / "copy")],
                                       check=True)
                        subprocess.run([args.runner, str(root / "copy")], check=True, timeout=15)
                    print(f"m68k auto-inc-dec: {' '.join(flags)} passed"
                          + (" (assembly + runtime)" if args.runner else " (assembly)"))


if __name__ == "__main__":
    main()
