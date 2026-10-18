# SPDX-License-Identifier: MIT
"""Static loader-cost audit matches the symbolic change surface."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import audit_loader_timing


class LoaderTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'baserom.gb').is_file():
            raise unittest.SkipTest('baserom.gb not present')
        cls.rows = audit_loader_timing.collect()
        cls.stats = audit_loader_timing.summarize(cls.rows)

    def test_every_loader_is_compared(self):
        self.assertEqual(self.stats['loaders'], 41)
        self.assertEqual(self.stats['compared'], 41)
        self.assertEqual(self.stats['unresolved'], 0)

    def test_title_and_config_grew_by_one_4k_block(self):
        by_site = {row['site']: row for row in self.rows}
        self.assertEqual(by_site['title_bundle_load']['delta'], 4096)
        self.assertEqual(by_site['configuration_map_full_bundle_load']['delta'], 4096)
        for site in ('sound_test_map_load', 'gameover_map_load', 'continue_map_load'):
            self.assertEqual(by_site[site]['delta'], 2048)

    def test_total_growth_matches_documented_value(self):
        self.assertEqual(self.stats['original_bytes'], 66720)
        self.assertEqual(self.stats['localized_bytes'], 81056)
        self.assertEqual(self.stats['delta_bytes'], 14336)
        self.assertEqual(self.stats['grown_loaders'], 5)

    def test_document_is_current(self):
        expected = audit_loader_timing.render_markdown(self.rows)
        path = ROOT / 'docs' / 'LOADER_TIMING.md'
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding='utf-8'), expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
