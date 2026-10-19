# SPDX-License-Identifier: MIT
"""Static page budget audit: inventory, capacity and map-code warnings."""
from pathlib import Path
import copy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import common
import audit_pages


class PageBudgetAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()
        cls.spec = json.loads((ROOT / '06_ProgramFix/change_surface.json').read_text())
        cls.result = audit_pages.audit(cls.manifest, cls.spec)

    def test_inventory_matches_page_layer(self):
        self.assertEqual(len(self.result['pages']), 30)
        self.assertEqual(self.result['active_pages'], 30)
        self.assertEqual(self.result['legacy_pages'], 0)
        self.assertEqual(len(self.result['bundles']), 10)
        self.assertEqual(len(self.result['edits']), 20)
        self.assertEqual(self.result['active'], 46)
        self.assertEqual(self.result['hard_errors'], [])

    def test_every_active_page_has_budget_and_capacity(self):
        for page in self.result['pages']:
            with self.subTest(page=page['id']):
                self.assertIn(page['kind'], ('bundle', 'edit'))
                self.assertGreater(page['decoded'], 0)
                self.assertGreaterEqual(page['capacity'], page['packed'])
                if page['active'] and page['kind'] == 'bundle':
                    self.assertIsNotNone(page['tile_count'])
                    self.assertIsNotNone(page['map_codes'])
                if page['active']:
                    self.assertIn('destinations', page)

    def test_title_bundle_uses_loader_specific_layout(self):
        title = next(p for p in self.result['pages'] if p['id'] == 'rom_070000')
        self.assertEqual(title['tile_count'], 292)
        self.assertGreater(title['tile_count'], audit_pages.BG_TILE_SLOTS)
        self.assertEqual(title['destinations'], [0x8800])
        self.assertTrue(any('rom_070000' in warning for warning in self.result['warnings']))

    def test_capacity_overflow_is_a_hard_error(self):
        broken = copy.deepcopy(self.manifest)
        broken['resources'][0]['capacity'] = 0
        result = audit_pages.audit(broken, self.spec)
        self.assertTrue(any('capacity' in error for error in result['hard_errors']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
