# SPDX-License-Identifier: MIT
"""Text layer: font + translation + layout regenerates the typeset pages."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import text_layout


class TextLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not text_layout.FONT_12.is_file() or not text_layout.FONT_8.is_file():
            raise unittest.SkipTest('font subsets missing; run 00_Tools/fetch_fonts.py')
        if not text_layout.LAYOUT_JSON.is_file():
            raise unittest.SkipTest('text layout missing; run 00_Tools/text_layout.py extract --write')
        cls.layout = json.loads(text_layout.LAYOUT_JSON.read_text(encoding='utf-8'))
        cls.fonts = text_layout.load_fonts()
        cls.translations = text_layout.load_translations()

    def entries(self, page):
        return {key: record for key, record in self.layout['entries'].items()
                if record['page'] == page}

    def test_layout_covers_all_typeset_pages(self):
        self.assertEqual(len(self.layout['entries']), 76)
        self.assertEqual(len(self.layout['pages']), 8)
        self.assertEqual(len({record['page'] for record in self.layout['entries'].values()}), 26)
        pages = {record['page'] for record in self.layout['entries'].values()}
        self.assertIn('rom_06c000', pages)       # stage 1
        self.assertIn('rom_055050', pages)       # normal-clear hint
        self.assertIn('rom_056110', pages)       # extra-clear hint
        self.assertIn('rom_048462', pages)       # gallery 1
        self.assertIn('rom_041000', pages)       # HUD
        self.assertIn('rom_0742b3', pages)       # gallery 3

    def test_layout_records_mode_and_anchors(self):
        for key, record in self.layout['entries'].items():
            with self.subTest(entry=key):
                self.assertIn(record['mode'], ('page', 'edit'))
                self.assertIn(record['font'], ('12px', '8px'))
                if record['mode'] == 'page':
                    self.assertIn(record['page'], self.layout['pages'])
                self.assertTrue('anchor' in record or 'positions' in record)

    def test_stage_numbers_typeset_only_chinese_part(self):
        record = self.layout['entries']['rom_06c000:stage_1_number']
        self.assertEqual(record['typeset'], '场景')
        self.assertEqual(record['anchor'], {'x': 62, 'y': 12})

    def test_gallery_entries_use_authoritative_boxes(self):
        record = self.layout['entries']['rom_048462:graphic_ending_01_01']
        self.assertEqual(record['anchor'], {'x': 14, 'y': 42})

    def test_hint_entries_carry_glyph_overrides(self):
        record = self.layout['entries']['rom_056110:graphic_ending_15_02']
        self.assertIn('1:4', record['overrides'])

    def test_base_plus_font_plus_translation_reproduces_pages(self):
        self.assertTrue(text_layout.check(self.translations, self.fonts))


if __name__ == '__main__':
    unittest.main(verbosity=2)
