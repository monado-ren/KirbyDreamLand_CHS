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

    def test_layout_covers_expected_pages(self):
        pages = {record['page'] for record in self.layout['entries'].values()}
        self.assertEqual(pages, {'rom_06c000', 'rom_06c70b', 'rom_06cda8',
                                 'rom_06d490', 'rom_06db85', 'rom_0438f6',
                                 'rom_04454c', 'rom_044734'})
        self.assertEqual(len(self.layout['entries']), 11)
        self.assertEqual(len(self.layout['pages']), 8)

    def test_layout_anchors_are_recorded(self):
        for entry_id, record in self.layout['entries'].items():
            with self.subTest(entry=entry_id):
                self.assertIn(record['font'], ('12px', '8px'))
                self.assertGreaterEqual(record['anchor']['x'], 0)
                self.assertGreaterEqual(record['anchor']['y'], 0)
                self.assertEqual(record['anchor']['candidates'], 1)

    def test_base_plus_font_plus_translation_reproduces_pages(self):
        failures = []
        for page_id, page in self.layout['pages'].items():
            base_path = ROOT / page['base_png']
            self.assertTrue(base_path.is_file(), base_path)
            width, height, shades = text_layout.graphics_png.png_to_shades(base_path.read_bytes())
            rendered = list(shades)
            for entry_id, record in self.layout['entries'].items():
                if record['page'] != page_id:
                    continue
                text = self.translations[entry_id]['translation_zh_hans']
                rendered = text_layout.render_text(rendered, width,
                                                   self.fonts[record['font']], text,
                                                   record['anchor'], record['line_height'])
            expected_path = ROOT / record['page_png'] if record.get('page_png') else None
            resource = self._resource(page_id)
            if resource.get('page'):
                expected_path = ROOT / resource['page']
            else:
                self.skipTest('edit page rendering is not wired yet')
            expected = text_layout.graphics_png.png_to_shades(expected_path.read_bytes())[2]
            if list(rendered) != list(expected):
                failures.append((page_id, sum(1 for left, right in zip(rendered, expected)
                                              if left != right)))
        self.assertEqual(failures, [])

    @classmethod
    def _resource(cls, page_id):
        import common
        manifest = common.load_manifest()
        return next(item for item in manifest['resources'] if item['id'] == page_id)


if __name__ == '__main__':
    unittest.main(verbosity=2)
