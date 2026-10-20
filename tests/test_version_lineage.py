# SPDX-License-Identifier: MIT
"""Keep the parallel version-numbering facts honest.

This repository and the original development workspace both use `v0.5.2` for
different ROMs.  The lineage document records that, and these tests make sure the
numbers it quotes stay tied to the artifacts that exist here.
"""
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common

LINEAGE = ROOT / 'docs' / 'VERSION_LINEAGE.md'

# From the archived development workspace; quoted for cross-reference only.
DEV_BASE = {
    'v0.5.1': '5b1a84b30977247236670cbab95b766be045c65837fa4cfc13b78b54c7689706',
    'v0.5.2': 'a9266a595ee2f78af1443323fec3e00e7b5fcfe08a3eb7e2b93291e597bc9491',
    'v0.5.3': 'f58da5e0c6b66290f0143e4edaf0edb0f0ea247ed9d03216547b1f62e8871dd6',
    'v0.5.4': '07cf119bb6042a19868f24a0d9bb22a621215f1e6b832b761bcfc0a8b499ac15',
    'v0.5.5': 'b359139710aed8f78f8eb00d91ce1bb405c6a9427c3d2c87ecda016afcd6f3f5',
}

# baserom.gb is the untouched Japanese Rev1 cartridge.
BASEROM_SHA = 'c4c6aff6242116c4f26bdcf3343b6c27836010853b8753da8b0cb953a200834a'
# v0.5.1 output ROM built from it.
JP_BASE_SHA = 'f96fe0ecac53cc586eac19b53fe1b50cef3fd1751261ae273c2356b2c6c62795'
JP_TARGET_SHA = 'bb754e254945009d2569ae47cd47c21c714cb59ad0cd005fbfa8348deb93f635'


class VersionLineageTests(unittest.TestCase):
    def test_lineage_doc_exists_and_names_both_branches(self):
        self.assertTrue(LINEAGE.is_file(), 'docs/VERSION_LINEAGE.md is missing')
        text = LINEAGE.read_text(encoding='utf-8')
        self.assertIn('KIRBY DREAM LAND', text)
        self.assertIn('HOSHINOKA-BI', text)
        self.assertIn('并行编号', text)

    def test_lineage_doc_quotes_the_hashes_it_should(self):
        text = LINEAGE.read_text(encoding='utf-8')
        self.assertIn(JP_BASE_SHA, text)
        self.assertIn(JP_TARGET_SHA, text)
        # leading digits of each archived release must appear
        for tag, sha in DEV_BASE.items():
            with self.subTest(tag=tag):
                self.assertIn(sha[:16], text)

    def test_manifest_release_matches_the_documented_target(self):
        manifest = common.load_manifest()
        self.assertEqual(manifest['release'], 'v0.5.3')
        self.assertEqual(manifest['target']['sha256'], JP_TARGET_SHA)

    def test_base_rom_is_the_japanese_revision(self):
        base = (ROOT / 'baserom.gb').read_bytes()
        self.assertEqual(hashlib.sha256(base).hexdigest(), BASEROM_SHA)
        # Japanese Rev1 cart title, not the US one.
        self.assertEqual(base[0x134:0x140], b'HOSHINOKA-BI')

    def test_release_survey_names_the_parallel_numbering(self):
        for name in ('CHANGELOG.md', 'docs/STATUS.md', 'README.md'):
            with self.subTest(file=name):
                text = (ROOT / name).read_text(encoding='utf-8')
                self.assertIn('VERSION_LINEAGE.md', text,
                              name + ' must point at the lineage document')


if __name__ == '__main__':
    unittest.main(verbosity=2)
