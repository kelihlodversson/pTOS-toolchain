#!/usr/bin/env python3
"""Check issue #18 with an SDK compiler; optionally execute using qemu-m68k."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parent
INSTRUCTION = re.compile(r"\s+([a-z]+)(?:\.([bwl]))?\s+(.*)")


def written_register(line):
    """Return (register, size) for an instruction whose last operand is a
    data or address register, else None."""
    match = INSTRUCTION.match(line.split("|")[0])
    if not match or match[1] in ("cmp", "tst", "btst", "jsr", "bsr"):
        return None
    operands = re.split(r",(?![^()]*\))", match[3].strip())
    register = re.fullmatch(r"%([ad][0-7])", operands[-1].strip())
    if not register:
        return None
    return register[1], match[2] or "l"


def check_assembly(assembly):
    """Reject an asm block whose longword source register was last set by a
    byte or word instruction in the same basic block."""
    lines = assembly.splitlines()
    checked = 0
    for index, line in enumerate(lines):
        if line.strip() != "#APP":
            continue
        body = []
        for following in lines[index + 1:]:
            if following.strip() == "#NO_APP":
                break
            body.append(following)
        sources = [m[1] for m in (re.match(r"\s*move\.l\s+%([ad][0-7]),", b) for b in body) if m]
        if not sources:
            continue
        checked += 1
        for previous in reversed(lines[:index]):
            text = previous.split("|")[0]
            if not text.strip() or text.strip().startswith("#"):
                continue
            if not text[0].isspace() or re.match(r"\s+j", text):
                break  # label or branch: end of the straight-line prefix
            written = written_register(text)
            if written and written[0] == sources[0]:
                if written[1] != "l":
                    raise AssertionError(
                        f"{written[1]}-sized write feeds longword asm input: {previous.strip()}")
                break
    if not checked:
        raise AssertionError("checked asm block not found")


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
                    flags = [cpu, opt, "-msoft-float", "-fomit-frame-pointer", *abi]
                    subprocess.run([args.compiler, *flags, "-S",
                                    str(PROJECT / "m68k-reload-const-modes.c"),
                                    "-o", str(root / "modes.s")], check=True)
                    check_assembly((root / "modes.s").read_text())
                    if args.runner:
                        # Both ABIs return in D0; the runtime's assembler
                        # entry points take no arguments.
                        subprocess.run([args.compiler, *flags, "-c",
                                        str(PROJECT / "m68k-reload-const-modes.c"),
                                        "-o", str(root / "modes.o")], check=True)
                        subprocess.run([args.compiler, *flags, "-ffreestanding", "-c",
                                        str(PROJECT / "m68k-reload-const-modes-runtime.c"),
                                        "-o", str(root / "runtime.o")], check=True)
                        subprocess.run([args.compiler, *flags, "-nostdlib", "-static",
                                        str(root / "modes.o"), str(root / "runtime.o"),
                                        "-Wl,-Ttext=0x10000,-e,_start", "-o", str(root / "modes")],
                                       check=True)
                        subprocess.run([args.runner, str(root / "modes")], check=True, timeout=15)
                    print(f"m68k reload constant modes: {' '.join(flags)} passed"
                          + (" (assembly + runtime)" if args.runner else " (assembly)"))


if __name__ == "__main__":
    main()
