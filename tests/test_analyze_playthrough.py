# SPDX-License-Identifier: MIT
"""Pure matching helpers for the optional playthrough runtime audit."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import analyze_playthrough


class PlaythroughMatchTests(unittest.TestCase):
    def test_map_ratio_exact_and_mismatch(self):
        expected = [value & 0xFF for value in range(32 * 18)]
        captured = bytearray(32 * 32)
        captured[:32 * 18] = bytes(expected)
        self.assertEqual(analyze_playthrough.map_ratio(bytes(captured), expected, 32, 18), 1.0)
        captured[0] = 255
        self.assertLess(analyze_playthrough.map_ratio(bytes(captured), expected, 32, 18), 1.0)

    def test_title_row_shift_finds_vertical_offset(self):
        expected = [1] * (32 * 18)
        captured = bytearray(32 * 32)
        captured[16 * 32:16 * 32 + 32 * 18] = bytes(expected)
        ratio, shift = analyze_playthrough.title_row_shift(bytes(captured), expected, 32, 18)
        self.assertEqual(ratio, 1.0)
        self.assertEqual(shift, 16)


if __name__ == '__main__':
    unittest.main(verbosity=2)
