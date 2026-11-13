#!/usr/bin/env python3
"""Keep the host ABI audit from treating target x32/ARM/m68k ELF as native."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', PROJECT / 'packaging/audit-runtime.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class NativeRuntimeAudit(unittest.TestCase):
    def test_native_host_elf(self):
        self.assertTrue(audit.native_amd64(Path('/bin/true')))

    def test_cross_target_and_non_elf_files_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'fixture'
            for elf_class, endian, machine in [(1, 1, 62), (1, 1, 40), (1, 2, 4), (2, 1, 183)]:
                file.write_bytes(b'\x7fELF' + bytes([elf_class, endian]) + bytes(12) + machine.to_bytes(2, 'little'))
                self.assertFalse(audit.native_amd64(file))
            file.write_bytes(b'#!/bin/sh\necho sdk\n')
            self.assertFalse(audit.native_amd64(file))


if __name__ == '__main__':
    unittest.main()
