# SPDX-License-Identifier: MIT
"""Human-readable page layer: preview sync and reversible retile tests."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import common
import graphics_png as gp
import page_image


class PageLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()
        cls.by_id = {entry['id']: entry for entry in cls.manifest['resources']}
        cls.maps = [entry for entry in cls.manifest['resources']
                    if entry['png']['mode'] == gp.TILEMAP_MODE]
        cls.pages = [entry for entry in cls.manifest['resources'] if entry.get('page')]
        cls.bundles = [entry for entry in cls.pages if entry.get('page_kind') == 'bundle']
        cls.sheets = [entry for entry in cls.pages if entry.get('page_kind') == 'sheet']

    def resources(self, entry):
        tileset = self.by_id[entry['png']['tileset']]
        return tileset, entry

    def test_page_inventory_covers_every_tileset(self):
        self.assertEqual(len(self.pages), 48)
        self.assertEqual(len(self.maps), 23)
        self.assertEqual(len(self.bundles), 21)
        self.assertEqual(len(self.sheets), 4)

    def test_tracked_pages_match_their_resources(self):
        by_id = self.by_id
        for entry in self.pages:
            with self.subTest(page=entry['id']):
                tiles_png = entry['source'] if entry.get('page_kind') != 'tilemap' \
                    else by_id[entry['png']['tileset']]['source']
                tiles_spec = entry['png'] if entry.get('page_kind') != 'tilemap' \
                    else by_id[entry['png']['tileset']]['png']
                tiles = gp.load_resource(ROOT / tiles_png, tiles_spec)
                if entry.get('page_kind') == 'sheet':
                    payload = gp.tiles_to_png(tiles, tiles_spec['tiles_per_row'])
                else:
                    bundle = entry.get('bundle')
                    map_spec = (entry['png'] if entry.get('page_kind') == 'tilemap'
                                else {'mode': gp.TILEMAP_MODE,
                                      'width': bundle['width'], 'height': bundle['height'],
                                      'addressing': bundle['addressing']})
                    map_png = entry['source'] if entry.get('page_kind') == 'tilemap' \
                        else bundle['map_png']
                    tilemap = gp.load_resource(ROOT / map_png, map_spec)
                    payload = page_image.page_png(
                        tiles, tilemap, map_spec['width'], map_spec['height'],
                        map_spec['addressing'], entry.get('page_kind') == 'bundle')
                self.assertEqual(payload, (ROOT / entry['page']).read_bytes())

    def test_page_dimensions_follow_their_layout(self):
        for entry in self.maps:
            with self.subTest(page=entry['id']):
                width, height = gp.decode_png((ROOT / entry['page']).read_bytes())[:2]
                self.assertEqual((width, height),
                                 (entry['png']['width'] * 8, entry['png']['height'] * 8))
        for entry in self.bundles:
            with self.subTest(page=entry['id']):
                bundle = entry['bundle']
                width, height = gp.decode_png((ROOT / entry['page']).read_bytes())[:2]
                self.assertEqual((width, height), (bundle['width'] * 8, bundle['height'] * 8))
        for entry in self.sheets:
            with self.subTest(page=entry['id']):
                width, height = gp.decode_png((ROOT / entry['page']).read_bytes())[:2]
                self.assertEqual(height % 8, 0)
                self.assertEqual(width, entry['png']['tiles_per_row'] * 8)

    def test_retiling_an_unchanged_page_is_the_identity(self):
        for entry in self.maps:
            tileset, _ = self.resources(entry)
            with self.subTest(page=entry['id']):
                pixels = (ROOT / entry['page']).read_bytes()
                tiles, tilemap, added = page_image.retile(
                    pixels, ROOT / tileset['source'], ROOT / entry['source'],
                    tileset['png'], entry['png'])
                self.assertEqual(tiles, gp.load_resource(ROOT / tileset['source'], tileset['png']))
                self.assertEqual(tilemap, gp.load_resource(ROOT / entry['source'], entry['png']))
                self.assertEqual(added, [])

    def _edited_page(self, entry, tileset):
        pixels = page_image.decode_page((ROOT / entry['page']).read_bytes(),
                                        entry['png']['width'], entry['png']['height'])
        page_width = entry['png']['width'] * 8
        # A checkerboard cell is extremely unlikely to exist in the tileset.
        for row in range(8):
            for column in range(8):
                pixels[row * page_width + column] = 3 if (row + column) % 2 else 0
        return pixels

    def test_editing_one_cell_is_compacted_within_the_tile_budget(self):
        # The tile slot count is fixed (it is what the game loader copies), so a
        # new 8x8 block must be paid for by compacting unused tiles.
        entry = self.by_id['rom_048462']
        tileset, _ = self.resources(entry)
        shades = self._edited_page(entry, tileset)
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

    def test_editing_a_0x8800_page_with_existing_tiles(self):
        # 0x8800 pages have no free addressable tile, but edits that reuse an
        # existing tile must still work and recompose exactly.
        entry = self.by_id['rom_055050']
        tileset, _ = self.resources(entry)
        shades = page_image.decode_page((ROOT / entry['page']).read_bytes(), 32, 32)
        page_width = 256
        blocks = {}
        for cell_y in range(32):
            for cell_x in range(32):
                blocks[(cell_x, cell_y)] = page_image._block_from_page(
                    shades, page_width, cell_x, cell_y)
        non_blank = [cell for cell, block in blocks.items() if any(block)]
        self.assertGreater(len(non_blank), 2)
        source_cell, target_cell = non_blank[0], None
        for candidate in non_blank[1:]:
            if blocks[candidate] != blocks[source_cell]:
                target_cell = candidate
                break
        self.assertIsNotNone(target_cell)
        source = blocks[source_cell]
        for row in range(8):
            low, high = source[row * 2], source[row * 2 + 1]
            for column in range(8):
                bit = 7 - column
                shades[(target_cell[1] * 8 + row) * page_width
                       + target_cell[0] * 8 + column] = (
                           ((high >> bit) & 1) << 1) | ((low >> bit) & 1)
        edited = gp.shades_to_png(256, 256, shades)
        tiles, tilemap, added = page_image.retile(
            edited, ROOT / tileset['source'], ROOT / entry['source'],
            tileset['png'], entry['png'])
        self.assertEqual(added, [])
        self.assertEqual(len(tiles), len(gp.load_resource(ROOT / tileset['source'], tileset['png'])))
        rebuilt = page_image.compose(tiles, tilemap, 32, 32, entry['png']['addressing'])
        self.assertEqual(rebuilt, shades)

    def test_new_tile_on_0x8800_page_is_rejected(self):
        entry = self.by_id['rom_055050']
        tileset, _ = self.resources(entry)
        shades = self._edited_page(entry, tileset)
        edited = gp.shades_to_png(256, 256, shades)
        with self.assertRaisesRegex(common.ProjectError, 'spare tile slot|0x8800'):
            page_image.retile(edited, ROOT / tileset['source'], ROOT / entry['source'],
                              tileset['png'], entry['png'])

    def test_retile_preserves_addressing_mode(self):
        entry = self.by_id['rom_055050']  # 0x8800 page
        tileset, _ = self.resources(entry)
        tiles, tilemap, added = page_image.retile(
            (ROOT / entry['page']).read_bytes(), ROOT / tileset['source'],
            ROOT / entry['source'], tileset['png'], entry['png'])
        self.assertEqual(added, [])
        self.assertEqual(tilemap, gp.load_resource(ROOT / entry['source'], entry['png']))

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

    def test_sheet_pages_are_the_tile_atlas(self):
        for entry in self.sheets:
            with self.subTest(page=entry['id']):
                tiles = gp.png_to_tiles((ROOT / entry['page']).read_bytes(),
                                        entry['png']['tiles_per_row'],
                                        entry['png']['tile_count'])
                self.assertEqual(tiles, gp.load_resource(ROOT / entry['source'], entry['png']))

    def test_bundle_placeholders_are_read_only(self):
        entry = self.by_id['rom_06cda8']  # stage 3: map uses original-ROM art tiles
        bundle = entry['bundle']
        map_spec = {'mode': gp.TILEMAP_MODE, 'width': bundle['width'],
                    'height': bundle['height'], 'addressing': bundle['addressing']}
        tiles = gp.load_resource(ROOT / entry['source'], entry['png'])
        tilemap = gp.load_resource(ROOT / bundle['map_png'], map_spec)
        tile_count = entry['png']['tile_count']
        unresolved = [index for index, value in enumerate(tilemap) if value >= tile_count]
        self.assertTrue(unresolved, 'expected external tiles in this bundle')
        shades = page_image.decode_page((ROOT / entry['page']).read_bytes(),
                                        bundle['width'], bundle['height'])
        page_width = bundle['width'] * 8
        cell = unresolved[0]
        cell_x, cell_y = cell % bundle['width'], cell // bundle['width']
        base = (cell_y * 8 + 2) * page_width + cell_x * 8
        shades[base] = 0  # repaint an inked pixel of the placeholder
        edited = gp.shades_to_png(page_width, bundle['height'] * 8, shades)
        with self.assertRaisesRegex(common.ProjectError, 'original ROM tiles'):
            page_image.retile(edited, ROOT / entry['source'], ROOT / bundle['map_png'],
                              entry['png'], map_spec, True)

    def test_page_path_escape_rejected(self):
        for value in ('../page.png', 'source/pages/../../page.png', '/' + 'tmp/page.png',
                      'source/graphics/page.png'):
            with self.subTest(value=value), self.assertRaises(common.ProjectError):
                common.page_path(value)


if __name__ == '__main__':
    unittest.main()
