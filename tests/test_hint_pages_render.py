# SPDX-License-Identifier: MIT
"""The two clear-screen hint pages must render as pictures, from their own data.

These pages are the whole point of v0.5.3 and they were the one thing with no
rendered verification: the visual-regression package shipped captures for the
gallery and HUD but none for the hint pages, so nothing compared them.

A hint page is a `tilemap` resource: the map lives in one stream and the tiles in
another, named by `png.tileset`.  Rendering the map against its own bytes -- or
against the wrong tileset -- produces noise that still looks like *an* image, so
these tests pin the wiring and the ink.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common
import hal_codec
import page_image
import render_screens

ROM = ROOT / 'KirbyDreamLand_CHS-Monado.gb'

# page resource -> (tileset resource, which clear shows it)
HINT_PAGES = {
    'rom_055050': ('rom_054000', 'normal'),   # "额外游戏 / 恭喜通关"
    'rom_056110': ('rom_055130', 'extra'),    # "配置模式 / 水平真不错呢"
}


class HintPageRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ROM.is_file():
            raise unittest.SkipTest('built ROM missing; run 00_Tools/build.py first')
        cls.rom = ROM.read_bytes()
        cls.manifest = common.load_manifest()
        cls.by_id = {e['id']: e for e in cls.manifest['resources']}

    def entry(self, page_id):
        self.assertIn(page_id, self.by_id)
        return self.by_id[page_id]

    def test_manifest_names_a_separate_tileset(self):
        for page_id, (tileset, _which) in HINT_PAGES.items():
            with self.subTest(page=page_id):
                spec = self.entry(page_id)['png']
                self.assertEqual(spec['mode'], 'tilemap-8bpp-grayscale')
                self.assertEqual(spec['tileset'], tileset,
                                 'tileset wiring changed; the page will render as noise')

    def test_tileset_and_map_fit_their_vram_windows(self):
        for page_id, (tileset, _which) in HINT_PAGES.items():
            with self.subTest(page=page_id):
                tiles = self.entry(tileset)
                # The loader writes tiles to 0x8000 and the map to 0x9800, so the
                # tileset may not spill into the map window.
                self.assertLessEqual(tiles['decoded_size'], 0x9800 - 0x8000)
                self.assertLessEqual(self.entry(page_id)['decoded_size'], 0xA000 - 0x9800)
                self.assertEqual(tiles['decoded_size'] % 16, 0)

    def test_pages_render_distinct_pictures(self):
        pictures = {}
        for page_id in HINT_PAGES:
            entry = self.entry(page_id)
            png = render_screens.resource_view(self.rom, entry, self.manifest)
            self.assertTrue(png)
            pictures[page_id] = png
        self.assertNotEqual(pictures['rom_055050'], pictures['rom_056110'],
                            'the two hint pages rendered identically')

    def test_rendered_page_has_ink_and_blank_margin(self):
        # A wrong tileset pairing yields high-frequency noise across the whole
        # frame.  Real pages have text on a mostly blank background, so measure
        # both: some ink, and a large single-shade area.
        for page_id in HINT_PAGES:
            with self.subTest(page=page_id):
                png = render_screens.resource_view(self.rom, self.entry(page_id),
                                                   self.manifest)
                shades = page_image.decode_page(png, 32, 32)
                total = len(shades)
                counts = {}
                for value in shades:
                    counts[value] = counts.get(value, 0) + 1
                dominant = max(counts.values()) / total
                ink = sum(counts.get(v, 0) for v in (0, 1, 2)) / total
                self.assertGreater(dominant, 0.45,
                                   'no large blank area; likely a tileset mismatch')
                self.assertGreater(ink, 0.02, 'page appears blank')

    def test_hint_entries_point_at_these_pages(self):
        layout = common.load_json(ROOT / '02_Text' / 'hint-layout.json') \
            if hasattr(common, 'load_json') else None
        if layout is None:
            import json
            layout = json.loads((ROOT / '02_Text' / 'hint-layout.json')
                                .read_text(encoding='utf-8'))
        pages = {entry['page'] for entry in layout['entries'].values()}
        self.assertEqual(pages, set(HINT_PAGES),
                         'hint-layout and the rendered pages disagree')


if __name__ == '__main__':
    unittest.main(verbosity=2)
