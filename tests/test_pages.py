# SPDX-License-Identifier: MIT
"""Page layer: bundle PNG pages plus baseline+overlay edit pages."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import common
import graphics_png as gp
import page_edits
import page_image


class PageLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()
        cls.by_id = {entry['id']: entry for entry in cls.manifest['resources']}
        cls.tilesets = [entry for entry in cls.manifest['resources']
                        if entry['png']['mode'] == gp.TILES_MODE]
        cls.maps = [entry for entry in cls.manifest['resources']
                    if entry['png']['mode'] == gp.TILEMAP_MODE]
        cls.pages = [entry for entry in cls.manifest['resources']
                     if entry.get('page') or entry.get('edit')]
        cls.page_png = [entry for entry in cls.pages if entry.get('page')]
        cls.edits = [entry for entry in cls.pages if entry.get('edit')]
        cls.bundles = [entry for entry in cls.page_png if entry.get('page_kind') == 'bundle']
        cls.sheet_edits = [entry for entry in cls.edits if entry.get('page_kind') == 'sheet']
        cls.tilemap_edits = [entry for entry in cls.edits if entry.get('page_kind') == 'tilemap']
        cls.base_path = ROOT / 'baserom.gb'

    def graphics_page(self, entry):
        return page_edits.graphics_page_png(entry, self.by_id)

    def test_page_inventory_covers_every_page_resource(self):
        self.assertEqual(len(self.pages), 30)
        self.assertEqual(len(self.page_png), 10)
        self.assertEqual(len(self.edits), 20)
        self.assertEqual(len(self.bundles), 10)
        self.assertEqual(len(self.sheet_edits), 4)
        self.assertEqual(len(self.tilemap_edits), 16)
        self.assertEqual(len(self.maps), 16)

    def test_bundle_pages_match_their_resources(self):
        for entry in self.bundles:
            with self.subTest(page=entry['id']):
                self.assertEqual((ROOT / entry['page']).read_bytes(), self.graphics_page(entry))

    def test_edit_records_are_structural(self):
        for entry in self.edits:
            with self.subTest(page=entry['id']):
                self.assertNotIn('page', entry)
                self.assertEqual(entry['edit'], '03_Image/edits/' + entry['id'] + '.json')
                edit = page_edits.load_edit(entry)
                self.assertEqual(edit['kind'], entry['page_kind'])
                self.assertEqual(edit['id'], entry['id'])
                width, height = edit['page_size']
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                base = edit['baseline']
                self.assertGreater(base['tiles']['tiles'], 0)
                self.assertIn('bank', base['tiles'])
                if edit['kind'] == 'tilemap':
                    self.assertIn('map', base)
                    self.assertGreater(base['map']['cells'], 0)
                    self.assertIn(base['addressing'], gp.TILEMAP_ADDRESSING)
                atlas = (ROOT / edit['overlay_atlas']).read_bytes()
                cells = edit['cells']
                self.assertEqual(len(cells), len(set(cells)))
                self.assertEqual(len(cells), len(gp.png_to_tiles(atlas, 16, len(cells))) // 16)
                for index in cells:
                    self.assertGreaterEqual(index, 0)
                    self.assertLess(index, width * height)

    def test_edit_layer_matches_graphics_when_baserom_is_available(self):
        if not self.base_path.is_file():
            self.skipTest('baserom.gb not present (public CI has no ROM)')
        base = self.base_path.read_bytes()
        common.validate_input(base, self.manifest)
        page_edits.check(self.manifest, base)

    def test_edit_pages_render_to_build_pages_when_baserom_is_available(self):
        if not self.base_path.is_file():
            self.skipTest('baserom.gb not present (public CI has no ROM)')
        base = self.base_path.read_bytes()
        for entry in self.edits:
            with self.subTest(page=entry['id']):
                edit = page_edits.load_edit(entry)
                rendered = page_edits.render_png(entry, edit, base)
                self.assertEqual(rendered, self.graphics_page(entry))

    def test_page_dimensions_follow_their_layout(self):
        for entry in self.tilemap_edits:
            with self.subTest(page=entry['id']):
                edit = page_edits.load_edit(entry)
                self.assertEqual(edit['page_size'], [entry['png']['width'], entry['png']['height']])
        for entry in self.bundles:
            with self.subTest(page=entry['id']):
                bundle = entry['bundle']
                width, height = gp.decode_png((ROOT / entry['page']).read_bytes())[:2]
                self.assertEqual((width, height), (bundle['width'] * 8, bundle['height'] * 8))
        for entry in self.sheet_edits:
            with self.subTest(page=entry['id']):
                edit = page_edits.load_edit(entry)
                self.assertEqual(edit['page_size'][0], entry['png']['tiles_per_row'])

    def test_retiling_an_unchanged_tilemap_is_the_identity(self):
        for entry in self.tilemap_edits:
            tileset = self.by_id[entry['png']['tileset']]
            with self.subTest(page=entry['id']):
                pixels = self.graphics_page(entry)
                tiles, tilemap, added = page_image.retile(
                    pixels, ROOT / tileset['source'], ROOT / entry['source'],
                    tileset['png'], entry['png'])
                self.assertEqual(tiles, gp.load_resource(ROOT / tileset['source'], tileset['png']))
                self.assertEqual(tilemap, gp.load_resource(ROOT / entry['source'], entry['png']))
                self.assertEqual(added, [])

    def test_retiling_an_unchanged_bundle_is_the_identity(self):
        for entry in self.bundles:
            bundle = entry['bundle']
            map_spec = {'mode': gp.TILEMAP_MODE, 'width': bundle['width'],
                        'height': bundle['height'], 'addressing': bundle['addressing']}
            with self.subTest(page=entry['id']):
                tiles, tilemap, added = page_image.retile(
                    (ROOT / entry['page']).read_bytes(), ROOT / entry['source'],
                    ROOT / bundle['map_png'], entry['png'], map_spec, True)
                self.assertEqual(tiles, gp.load_resource(ROOT / entry['source'], entry['png']))
                self.assertEqual(tilemap, gp.load_resource(ROOT / bundle['map_png'], map_spec))
                self.assertEqual(added, [])

    def _edited_shades(self, entry, tileset):
        pixels = list(gp.png_to_shades(self.graphics_page(entry))[2])
        page_width = entry['png']['width'] * 8
        for row in range(8):
            for column in range(8):
                pixels[row * page_width + column] = 3 if (row + column) % 2 else 0
        return pixels

    def test_editing_one_cell_is_compacted_within_the_tile_budget(self):
        entry = self.by_id['rom_048462']
        tileset = self.by_id[entry['png']['tileset']]
        shades = self._edited_shades(entry, tileset)
        edited = gp.shades_to_png(entry['png']['width'] * 8,
                                  entry['png']['height'] * 8, shades)
        tiles, tilemap, added, strategy = page_image.retile_within_capacity(
            edited, ROOT / tileset['source'], ROOT / entry['source'],
            tileset['png'], entry['png'], tileset['capacity'] + 128,
            entry['capacity'] + 128, max_tiles=tileset['png']['tile_count'])
        self.assertLessEqual(len(tiles) // 16, tileset['png']['tile_count'])
        self.assertEqual(len(tilemap), entry['decoded_size'])
        rebuilt = page_image.compose(tiles, tilemap, entry['png']['width'],
                                     entry['png']['height'], entry['png']['addressing'])
        self.assertEqual(rebuilt, shades)
        self.assertIn(strategy, ('preserve', 'compact-first-use', 'compact-sorted'))

    def test_retile_preserves_addressing_mode(self):
        entry = self.by_id['rom_055050']  # 0x8800 page
        tileset = self.by_id[entry['png']['tileset']]
        tiles, tilemap, added = page_image.retile(
            self.graphics_page(entry), ROOT / tileset['source'],
            ROOT / entry['source'], tileset['png'], entry['png'])
        self.assertEqual(added, [])
        self.assertEqual(tilemap, gp.load_resource(ROOT / entry['source'], entry['png']))

    def test_sheet_edit_baseline_plus_overlay_when_baserom_is_available(self):
        if not self.base_path.is_file():
            self.skipTest('baserom.gb not present (public CI has no ROM)')
        base = self.base_path.read_bytes()
        for entry in self.sheet_edits:
            with self.subTest(page=entry['id']):
                edit = page_edits.load_edit(entry)
                self.assertEqual(page_edits.render_png(entry, edit, base),
                                 self.graphics_page(entry))

    def test_page_and_edit_path_escape_rejected(self):
        for value in ('../page.png', '03_Image/pages/../../page.png', '/' + 'tmp/page.png',
                      '03_Image/graphics/page.png'):
            with self.subTest(value=value), self.assertRaises(common.ProjectError):
                common.page_path(value)
        for value in ('../edit.json', '03_Image/edits/../../edit.json',
                      '03_Image/pages/edit.json', '/' + 'tmp/edit.json'):
            with self.subTest(value=value), self.assertRaises(common.ProjectError):
                common.edit_path(value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
