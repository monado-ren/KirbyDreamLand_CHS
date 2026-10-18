# SPDX-License-Identifier: MIT
"""Loader payload redundancy audit: the compacted page stays pixel-identical."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import audit_loader_payload


class LoaderPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = audit_loader_payload.analyse(audit_loader_payload.common.load_manifest())
        cls.stats = audit_loader_payload.summarize(cls.rows)

    def test_five_grown_bundles(self):
        self.assertEqual(self.stats['pages'], 5)
        self.assertEqual(self.stats['decoded'], 17792)

    def test_compaction_preserves_every_page(self):
        self.assertTrue(self.stats['all_pages_identical'])

    def test_compaction_saves_measured_bytes(self):
        self.assertEqual(self.stats['saving'], 12016)
        self.assertEqual(self.stats['unused_tiles'], 713)

    def test_document_is_current(self):
        expected = audit_loader_payload.render_markdown(self.rows)
        path = ROOT / 'docs' / 'LOADER_PAYLOAD.md'
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding='utf-8'), expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
