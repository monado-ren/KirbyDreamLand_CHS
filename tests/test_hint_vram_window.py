# SPDX-License-Identifier: MIT
"""The clear-screen hint tilesets must fit the VRAM window their loader uses.

These pages have no ``loader.vram_base`` patch, so they are copied to the
addresses the original code already contains.  Disassembly of that routine:

    ld hl,$4000 / ld de,$8000 / ld c,$15 / call $20C1    ; tileset -> 0x8000
    ld hl,$4000 / ld de,$9800 / ld c,$10 / call $20C1    ; map     -> 0x9800

VRAM ends at 0x9FFF and the map occupies 0x9800..0x9BFF, so the tileset only has
0x8000..0x97FF = 6144 bytes.  Growing the 12px tilesets past that silently
overwrote the map on hardware, which is exactly what happened once: an 8192-byte
tileset still packed and passed every other gate.  These tests pin the bound.
"""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common

TILESET_LOW = 0x8000
MAP_LOW = 0x9800
VRAM_END = 0xA000
TILESET_WINDOW = MAP_LOW - TILESET_LOW          # 6144 bytes
MAP_WINDOW = VRAM_END - MAP_LOW                 # 2048 bytes, map uses 1024

# page resource -> its tileset resource
# A normal clear shows the page that explains how to reach Extra Game
# (`rom_055050`, "额外游戏 / 恭喜通关"), so that page is the *normal* clear hint.
# An extra clear shows the configuration instructions (`rom_056110`,
# "配置模式 / 水平真不错呢").  The mapping is easy to invert by accident, so it is
# spelled out here and checked against the page text below.
HINT_PAGES = {
    'rom_055050': 'rom_054000',   # normal clear -> how to reach Extra Game
    'rom_056110': 'rom_055130',   # extra clear  -> how to reach Configuration
}


class HintVramWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'KirbyDreamLand_CHS-Monado.gb').is_file():
            raise unittest.SkipTest('built ROM missing; run 00_Tools/build.py first')
        cls.manifest = common.load_manifest()
        cls.by_id = {entry['id']: entry for entry in cls.manifest['resources']}

    def test_hint_loaders_use_the_built_in_addresses(self):
        # If a vram_base patch ever appears for these pages the window assertion
        # below would need revisiting, so fail loudly instead of silently drifting.
        spec = json.loads((ROOT / '06_ProgramFix' / 'change_surface.json')
                          .read_text(encoding='utf-8'))
        patched = set()
        for site in spec['sites']:
            for patch in site.get('patches', []):
                if patch['kind'] == 'loader.vram_base' and site.get('resource'):
                    patched.add(site['resource'])
        for tileset in HINT_PAGES.values():
            self.assertNotIn(tileset, patched,
                             tileset + ' gained a vram_base patch; '
                             're-check the 6144-byte window assumption')

    def test_tilesets_fit_the_6144_byte_window(self):
        for tileset in HINT_PAGES.values():
            entry = self.by_id[tileset]
            with self.subTest(tileset=tileset):
                self.assertLessEqual(entry['decoded_size'], TILESET_WINDOW,
                                     '%s decodes to %d bytes but only %d fit '
                                     'between 0x8000 and 0x97FF'
                                     % (tileset, entry['decoded_size'],
                                        TILESET_WINDOW))

    def test_maps_fit_the_map_window(self):
        for page in HINT_PAGES:
            entry = self.by_id[page]
            with self.subTest(page=page):
                self.assertLessEqual(entry['decoded_size'], MAP_WINDOW)

    def test_tileset_capacity_matches_the_window(self):
        # capacity is the packed budget; the decoded size is what the loader copies
        for tileset in HINT_PAGES.values():
            entry = self.by_id[tileset]
            with self.subTest(tileset=tileset):
                self.assertLessEqual(entry['capacity'], TILESET_WINDOW)

    def test_map_codes_stay_inside_the_384_tile_window(self):
        # 384 tiles is the most that fit; a map code above that would index past
        # the loaded tileset once the copy is done.
        import hal_codec
        rom = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()
        limit = TILESET_WINDOW // 16
        for page in HINT_PAGES:
            entry = self.by_id[page]
            raw, _ = hal_codec.decode(rom[entry['offset']:])
            with self.subTest(page=page):
                self.assertLess(max(raw), 256,
                                'map code %d cannot be expressed in one byte'
                                % max(raw))


if __name__ == '__main__':
    unittest.main(verbosity=2)
