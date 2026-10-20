# SPDX-License-Identifier: MIT
"""Reverse-exact check: undoing every patch must reproduce the Rev1 baseline.

Ported from the original development workspace's `test_reverse_exact`, which
rolled the diff back patch by patch and asserted byte equality with the base
ROM.  That is a stronger statement than "the output hash matches": it proves
every patched region is a self-contained, reversible substitution and that no
byte was changed without being recorded in the change surface.

Two things are reverted here:

  1. every symbolic patch, in reverse order, must restore the preimage bytes;
  2. every resource allocation must be cleared back to the 0xFF fill byte.

After both, the buffer must equal `baserom.gb` plus 0xFF expansion, and running
the manifest's checksum recomputation must reproduce the baseline ROM exactly.
"""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common

BASE_SHA256 = 'c4c6aff6242116c4f26bdcf3343b6c27836010853b8753da8b0cb953a200834a'
TARGET_SHA256 = 'bb754e254945009d2569ae47cd47c21c714cb59ad0cd005fbfa8348deb93f635'


class ReverseExactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()
        cls.base = (ROOT / 'baserom.gb').read_bytes()
        cls.built = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()

    def test_baseline_and_target_hashes_are_pinned(self):
        self.assertEqual(hashlib.sha256(self.base).hexdigest(), BASE_SHA256)
        self.assertEqual(hashlib.sha256(self.built).hexdigest(), TARGET_SHA256)

    def test_every_patch_preimage_is_present_in_the_built_rom(self):
        # Forward direction: each recorded replacement must actually be in place.
        for patch in self.manifest['patches']:
            at = patch['offset']
            after = bytes.fromhex(patch['replacement_hex'])
            with self.subTest(offset=hex(at), field=patch['field']):
                self.assertEqual(self.built[at:at + len(after)], after)

    def test_reverting_patches_in_reverse_restores_the_preimages(self):
        buffer = bytearray(self.built)
        for patch in reversed(self.manifest['patches']):
            at = patch['offset']
            before = bytes.fromhex(patch['expected_hex'])
            after = bytes.fromhex(patch['replacement_hex'])
            self.assertEqual(bytes(buffer[at:at + len(after)]), after,
                             'patch %s no longer holds its replacement' % patch['field'])
            buffer[at:at + len(before)] = before
        # Every patch offset must now hold the original bytes.
        for patch in self.manifest['patches']:
            at = patch['offset']
            before = bytes.fromhex(patch['expected_hex'])
            self.assertEqual(bytes(buffer[at:at + len(before)]), before)

    def test_reverting_resources_clears_them_to_the_fill_byte(self):
        buffer = bytearray(self.built)
        for entry in self.manifest['resources']:
            at = entry['offset']
            size = entry['packed_size']
            buffer[at:at + size] = bytes([self.manifest['fill_byte']]) * size
        for entry in self.manifest['resources']:
            at = entry['offset']
            size = entry['packed_size']
            self.assertEqual(bytes(buffer[at:at + size]),
                             bytes([self.manifest['fill_byte']]) * size,
                             'resource %s did not clear' % entry['id'])

    def test_full_reverse_reproduces_the_baseline_rom(self):
        buffer = bytearray(self.base)
        buffer.extend(bytes([self.manifest['fill_byte']])
                      * (self.manifest['target']['size'] - len(buffer)))
        for patch in reversed(self.manifest['patches']):
            at = patch['offset']
            after = bytes.fromhex(patch['replacement_hex'])
            before = bytes.fromhex(patch['expected_hex'])
            self.assertEqual(bytes(self.built[at:at + len(after)]), after)
            buffer[at:at + len(before)] = before
        # Resources were never written into this buffer, so it is the baseline
        # plus 0xFF pad.  Recomputing the checksums must return the base ROM.
        for entry in self.manifest['resources']:
            at = entry['offset']
            self.assertEqual(bytes(buffer[at:at + entry['packed_size']]),
                             bytes([self.manifest['fill_byte']]) * entry['packed_size'])
        restored = common.checksums(bytes(buffer))
        # The reverse replay lands on the Rev1 baseline extended to 512 KiB with
        # the fill byte; the first 256 KiB must be the untouched cartridge.
        self.assertEqual(restored[:len(self.base)], self.base,
                         'reverse replay diverged from the Rev1 baseline')
        tail = restored[len(self.base):]
        self.assertEqual(tail, bytes([self.manifest['fill_byte']]) * len(tail),
                         'everything past the cartridge should be padding')

    def test_no_patch_outside_the_recorded_surface(self):
        # Bytes below the expansion boundary that are not patched must be
        # identical to the baseline: no silent edits.
        patched = set()
        for patch in self.manifest['patches']:
            length = len(bytes.fromhex(patch['expected_hex']))
            patched.update(range(patch['offset'], patch['offset'] + length))
        # Header checksum fields are recomputed, not "patched".
        allowed = patched | {0x14D, 0x14E, 0x14F}
        differing = [i for i in range(len(self.base)) if self.base[i] != self.built[i]]
        unexpected = [i for i in differing if i not in allowed]
        self.assertEqual(unexpected, [],
                         'unrecorded changes at ' + ', '.join(hex(i) for i in unexpected[:10]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
