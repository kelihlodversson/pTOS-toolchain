#!/usr/bin/env python3
"""Compile and assemble the pTOS#998 LRA address-boundary reproducer."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compiler")
    args = parser.parse_args()
    source = Path(__file__).with_name("m68k-lra-address.c")
    with tempfile.TemporaryDirectory() as scratch:
        for cpu in ("-m68000", "-m68010", "-m68020", "-m68040", "-m68060"):
            for opt in ("-Os", "-O2"):
                for abi in ("-mno-fastcall", "-mfastcall"):
                    for offset in (127, 128):
                        flags = [cpu, opt, abi, "-mlra", "-msoft-float",
                                 "-fomit-frame-pointer", f"-DDISPLACEMENT={offset}"]
                        subprocess.run([args.compiler, *flags, "-c", str(source),
                                        "-o", str(Path(scratch) / "address.o")], check=True)
        print("m68k LRA address boundaries: 40 compile/assemble checks passed")


if __name__ == "__main__":
    main()
