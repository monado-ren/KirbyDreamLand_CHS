# SPDX-License-Identifier: MIT
"""Reverse-direction audit: the ROM must decode back into the page sources.

`build.py` proves "sources produce this ROM"; these tests prove the converse for
the shipped ROM, so a stale or hand-edited ROM cannot pass while the editable
PNGs say something different.
"""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import audit_rom_pages
import common

TARGET_SHA256 = '084c5157fd9b9637661b8a38e87a73e240a68fe3637a5d4617b539b8a1932b19'


class RomPageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.rom_sha = audit_rom_pages.collect()

    def test_shipped_rom_decodes_back_into_page_sources(self):
        stats = audit_rom_pages.summarize(self.rows)
        self.assertEqual(stats['failed'], 0,
                         [row for row in self.rows if not row['ok']])
        self.assertEqual(stats['resources'], len(common.load_manifest()['resources']))

    def test_every_resource_matches_its_declared_digest(self):
        for row in self.rows:
            with self.subTest(resource=row['id']):
                self.assertTrue(row['ok'], row.get('problems'))

    def test_audit_detects_a_corrupted_byte(self):
        # Negative control: flipping one packed byte must fail exactly one
        # resource, otherwise the audit would be vacuous.
        original = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()
        tampered = bytearray(original)
        target = common.load_manifest()['resources'][5]
        tampered[target['offset'] + 5] ^= 0xFF
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tampered.gb'
            path.write_bytes(bytes(tampered))
            rows, _sha = audit_rom_pages.collect(path)
        failed = [row['id'] for row in rows if not row['ok']]
        self.assertEqual(failed, [target['id']])

    def test_report_is_current(self):
        document = ROOT / 'docs' / 'ROM_PAGES.md'
        self.assertTrue(document.is_file(), 'docs/ROM_PAGES.md is missing')
        expected = audit_rom_pages.render_markdown(self.rows, self.rom_sha)
        self.assertEqual(document.read_text(encoding='utf-8'), expected)

    def test_rom_hash_matches_the_documented_target(self):
        self.assertEqual(self.rom_sha, TARGET_SHA256)


if __name__ == '__main__':
    unittest.main(verbosity=2)
