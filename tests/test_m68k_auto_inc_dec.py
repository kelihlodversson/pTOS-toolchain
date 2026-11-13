#!/usr/bin/env python3
"""Ensure the assembly regression detects the operand dependency in #15."""

import unittest

from m68k_auto_inc_dec import check_assembly


class AssemblyCheck(unittest.TestCase):
    def test_rejects_shared_updated_register(self):
        for instruction in (
            "move.l (%a0)+,(%a0,%d0.l)",
            "move.w (%a1)+,8(%a1)",
            "move.b -(%a2),(%a3,%a2.l)",
            "move.l (%a3,%a2.l),-(%a2)",
        ):
            with self.subTest(instruction=instruction), self.assertRaises(AssertionError):
                check_assembly("\t" + instruction)

    def test_accepts_independent_addresses_and_explicit_increment(self):
        check_assembly("""
        move.l (%a0)+,(%a1,%d0.l)
        move.l (%a0),(%a1,%a0.l)
        addq.l #4,%a0
        move.w -(%a2),(%a3)
        move.b (%a2),-(%a3)
        """)


if __name__ == "__main__":
    unittest.main()
