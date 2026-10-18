# SPDX-License-Identifier: MIT
"""Guards for the dead-load removal (v0.5.2).

The localization merges several original loads of a screen into one HAL bundle
but leaves the original per-part loads in the code.  This release NOPs out the
six calls whose VRAM destination the merged bundle rewrites completely.  These
tests pin the two properties that make that safe.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import audit_dead_loads
import common

TARGET_SHA256 = '959835314b684dded38752a6df9fc349d38a4d70fa83633d971c84972a5755dd'

# Every neutralised call, and the merged bundle that must cover it.
DEAD_CALLS = {
    0x18030: (2, 0x7906, 0x8800),    # title:  title_tiles_1 -> covered by bundle
    0x1803B: (2, 0x796A, 0x9000),    # title:  title_tiles_2
    0x18046: (2, 0x77E9, 0x8E00),    # title:  intro_font
    0x1A3A9: (2, 0x4855, 0x9670),    # config: normal_hud
    0x1A3B4: (6, 0x7B04, 0x8800),    # config: configuration_tiles
    0x1A3BF: (3, 0x41C0, 0x8E00),    # config: full_font
}


class DeadLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / 'baserom.gb').read_bytes()
        cls.built = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()

    def test_every_neutralised_call_is_a_nopped_decompress(self):
        for offset in DEAD_CALLS:
            with self.subTest(offset=hex(offset)):
                self.assertEqual(self.base[offset:offset + 3], b'\xcd\xc1\x20')
                self.assertEqual(self.built[offset:offset + 3], b'\x00\x00\x00')

    def test_every_neutralised_call_is_proven_dead(self):
        import hashlib
        self.assertEqual(hashlib.sha256(self.built).hexdigest(), TARGET_SHA256)
        rows = audit_dead_loads.collect(self.base)
        self.assertEqual(len(rows), 6)
        for row in rows:
            with self.subTest(call=hex(row['call_at'])):
                self.assertIsNotNone(row['shadowed_by'],
                                     'no covering load for ' + hex(row['call_at']))
                shadow = row['shadowed_by']
                self.assertLessEqual(shadow['dest'], row['dest'])
                self.assertGreaterEqual(shadow['dest'] + shadow['size'],
                                        row['dest'] + row['decoded'])

    def test_saved_bytes_are_pinned(self):
        stats = audit_dead_loads.summarize(audit_dead_loads.collect(self.base))
        self.assertEqual(stats['calls'], 6)
        self.assertEqual(stats['proven_dead'], 6)
        self.assertEqual(stats['unproven'], 0)
        self.assertEqual(stats['saved_bytes'], 6032)
        self.assertEqual(stats['patched_bytes'], 18)

    def test_dead_load_doc_is_current(self):
        path = ROOT / 'docs' / 'DEAD_LOADS.md'
        self.assertTrue(path.is_file())
        expected = audit_dead_loads.render_markdown(audit_dead_loads.collect(self.base))
        self.assertEqual(path.read_text(encoding='utf-8'), expected)

    def test_removing_the_nops_restores_the_previous_release(self):
        # The change is exactly 20 bytes versus v0.5.1: 18 call bytes + the two
        # global-checksum bytes.  Reverting must reproduce the old ROM hash.
        restored = bytearray(self.built)
        for offset in DEAD_CALLS:
            restored[offset:offset + 3] = b'\xcd\xc1\x20'
        restored = common.checksums(bytes(restored))
        import hashlib
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
                         'f96fe0ecac53cc586eac19b53fe1b50cef3fd1751261ae273c2356b2c6c62795')


if __name__ == '__main__':
    unittest.main(verbosity=2)
