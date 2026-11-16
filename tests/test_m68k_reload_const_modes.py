#!/usr/bin/env python3
"""Ensure the assembly regression detects the partial constant load in #18."""

import unittest

from m68k_reload_const_modes import check_assembly


def block(prefix):
    return prefix + """
#APP
| 19 "m68k-reload-const-modes.c" 1
	move.l %d6,%d5
	add.w %d6,%d5
	add.l #0x10000,%d5
| 0 "" 2
#NO_APP
"""


class AssemblyCheck(unittest.TestCase):
    def test_rejects_narrow_write_of_longword_input(self):
        for prefix in (".L3:\n\tclr.w %d6",
                       ".L3:\n\tmove.w #0,%d6\n\tmove.l %d1,%d2",
                       ".L3:\n\tclr.b %d6"):
            with self.subTest(prefix=prefix), self.assertRaises(AssertionError):
                check_assembly(block(prefix))

    def test_accepts_longword_write_and_block_boundaries(self):
        for prefix in (".L3:\n\tclr.l %d6",
                       ".L3:\n\tmoveq #0,%d6\n\tclr.w %d4",
                       ".L3:\n\tclr.w %d6\n\tclr.l %d6",
                       "\tclr.w %d6\n.L3:",
                       "\tclr.w %d6\n\tjne .L4"):
            with self.subTest(prefix=prefix):
                check_assembly(block(prefix))

    def test_requires_the_checked_asm(self):
        with self.assertRaises(AssertionError):
            check_assembly("\tclr.l %d0\n\trts\n")


if __name__ == "__main__":
    unittest.main()
