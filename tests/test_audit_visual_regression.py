# SPDX-License-Identifier: MIT
"""Pure matching helpers for the external BGB visual-regression audit."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import audit_visual_regression as avr


class VisualRegressionMatchTests(unittest.TestCase):
    def test_bundle_map_and_tile_match(self):
        tiles = bytes(range(16)) * 4
        model = {
            'kind': 'bundle',
            'map': [1, 2, 3, 4],
            'width': 2,
            'height': 2,
            'tiles': tiles,
            'destinations': [0x9000],
        }
        vram = bytearray(0x2000)
        vram[0x1000:0x1000 + len(tiles)] = tiles
        vram[0x1800:0x1802] = bytes([1, 2])
        vram[0x1820:0x1822] = bytes([3, 4])
        ratio, source = avr.map_match(bytes(vram[0x1800:0x1C00]), bytes(vram), model, 'page')
        self.assertEqual(ratio, 1.0)
        self.assertEqual(source, 'bgmap')
        tile_ratio, offset = avr.tile_match(bytes(vram), model, 'page')
        self.assertEqual(tile_ratio, 1.0)
        self.assertEqual(offset, 0x9000)

    def test_sheet_tile_match(self):
        tiles = bytes(range(32))
        vram = bytearray(0x2000)
        vram[0x1234:0x1234 + len(tiles)] = tiles
        model = {'kind': 'sheet', 'tiles': tiles}
        ratio, offset = avr.tile_match(bytes(vram), model, 'sheet')
        self.assertEqual(ratio, 1.0)
        self.assertEqual(offset, 0x9234)


if __name__ == '__main__':
    unittest.main(verbosity=2)
