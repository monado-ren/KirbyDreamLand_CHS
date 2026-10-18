# SPDX-License-Identifier: MIT
"""Symbolic change surface: patches are derived from symbols + RGBDS assembly."""
from pathlib import Path
import copy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import common
import change_surface


class ChangeSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = change_surface.load_spec()
        cls.rgbds = change_surface.find_rgbds()
        if cls.rgbds is None:
            raise unittest.SkipTest('RGBDS not available; build it with 00_Tools/build_rgbds.py')
        cls.manifest = common.load_manifest()
        cls.raw_manifest = json.loads((ROOT / '04_Data' / 'manifest.json').read_text())
        cls.by_id = {r['id']: r for r in cls.spec['resources']}

    def test_spec_derives_the_authoritative_manifest(self):
        stats = change_surface.verify(self.spec, self.manifest, rgbds=self.rgbds)
        self.assertEqual(stats['patches'], 116)
        self.assertEqual(stats['bytes'], 216)
        self.assertEqual(stats['sites'], 49)
        self.assertEqual(stats['resources'], 71)
        self.assertEqual(stats['active'], 46)
        self.assertEqual(stats['legacy'], 25)
        self.assertEqual(stats['code_regions'], 1)
        self.assertEqual(self.raw_manifest['change_surface']['sha256'], stats['digest'])

    def test_manifest_no_longer_stores_hex_patches(self):
        self.assertNotIn('patches', self.raw_manifest)
        self.assertEqual(self.raw_manifest['change_surface']['patches'], 116)
        self.assertEqual(self.raw_manifest['change_surface']['bytes'], 216)
        self.assertEqual(self.manifest['patches'],
                         change_surface.derive_patches(self.spec, self.rgbds))

    def test_every_patch_is_semantically_named_and_typed(self):
        allowed = {'rom.size', 'hud.label_tile', 'loader.vram_base', 'sprite.x',
                   'loader.source_addr', 'loader.bank', 'stage.pointer_table', 'code.nop'}
        for site in self.spec['sites']:
            self.assertTrue(site['site'], site)
            self.assertTrue(site['purpose'], site)
            for patch in site['patches']:
                self.assertIn(patch['kind'], allowed, patch)
        derived = change_surface.derive_patches(self.spec, self.rgbds)
        self.assertEqual(len(derived), 116)
        self.assertEqual(sum(len(bytes.fromhex(p['replacement_hex'])) for p in derived), 216)
        self.assertEqual(len({p['offset'] for p in derived}), 116)

    def test_loader_sites_name_actual_resources(self):
        sites = [s for s in self.spec['sites'] if s['site'] not in
                 ('rom_size_512KiB', 'HUD_score_label_x16', 'stage_bundle_destination',
                  'two_row_vblank_queue_writer', 'gallery_page4_bat_x_only',
                  'title_dead_loads', 'configuration_dead_loads',
                  'stage_1_bundle_pointer')]
        self.assertEqual(len(sites), 41)
        for site in sites:
            self.assertIn('resource', site, site['site'])
            self.assertIn(site['resource'], self.by_id)
            self.assertEqual(self.by_id[site['resource']]['role'], 'active')

    def test_stage_pointer_table_is_structured(self):
        site = next(s for s in self.spec['sites'] if s['site'] == 'stage_1_bundle_pointer')
        table = site['patches'][0]
        self.assertEqual(table['kind'], 'stage.pointer_table')
        self.assertEqual(len(table['entries']), 5)
        self.assertEqual([e['stage'] for e in table['entries']],
                         ['stage_1', 'stage_2', 'stage_3', 'stage_4', 'stage_5'])
        for entry in table['entries']:
            self.assertEqual(entry['old']['bank'], 6)
            self.assertEqual(entry['new']['bank'], 27)
            self.assertIn(entry['resource'], self.by_id)

    def test_code_region_is_asm_only(self):
        site = next(s for s in self.spec['sites'] if s['site'] == 'two_row_vblank_queue_writer')
        region = site['region']
        self.assertEqual(site['kind'], 'code.region')
        self.assertEqual(region['length'], 41)
        self.assertNotIn('old_hex', region)
        self.assertNotIn('new_hex', region)
        for key in ('asm_rev1', 'asm'):
            self.assertTrue((ROOT / region[key]).is_file(), region[key])
        runs, old, new = change_surface.derive_region(site, self.rgbds)
        self.assertEqual(len(runs), 4)
        self.assertEqual(sum(len(bytes.fromhex(r['replacement_hex'])) for r in runs), 32)
        self.assertEqual(len(old), 41)
        self.assertEqual(len(new), 41)
        base = ROOT / 'baserom.gb'
        if base.is_file():
            self.assertEqual(old, base.read_bytes()[0x180A0:0x180A0 + 41])
        self.assertIn('0xCB00', ' '.join(region['notes']))

    def test_legacy_copies_are_marked_and_unreferenced(self):
        legacy = [r for r in self.spec['resources'] if r['role'] == 'legacy']
        self.assertEqual(len(legacy), 25)
        for res in legacy:
            self.assertIn('legacy_reason', res)
            self.assertIn('v0.5.1', res['legacy_reason'])
        active_ids = {r['id'] for r in self.spec['resources'] if r['role'] == 'active'}
        self.assertFalse({r['id'] for r in legacy} & active_ids)

    def test_checksum_policy_is_documented(self):
        header = self.spec['header']
        self.assertEqual(header['rom_size_code']['old'], 3)
        self.assertEqual(header['rom_size_code']['new'], 4)
        self.assertEqual(header['checksums']['policy'], 'recompute')
        self.assertEqual(header['checksums']['excluded_from_global'], ['0x014E', '0x014F'])

    def test_explain_renders_semantics(self):
        text = change_surface.explain(self.spec, rgbds=self.rgbds)
        for needle in ('normal_hud_load', 'rom_041000', 'loader.source_addr',
                       'stage.pointer_table', 'GAME OVER', 'vblank_two_row.rev1.asm'):
            self.assertIn(needle, text)

    def test_manifest_is_generated_from_symbols(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'manifest.json'
            change_surface.sync_manifest(self.spec, self.raw_manifest, path=out, write=True)
            self.assertEqual(out.read_bytes(), (ROOT / '04_Data' / 'manifest.json').read_bytes())

    def test_tampered_manifest_digest_is_rejected(self):
        broken = copy.deepcopy(self.raw_manifest)
        broken['change_surface']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            change_surface.verify(self.spec, broken, rgbds=self.rgbds)

    def test_tampered_spec_is_rejected(self):
        broken = copy.deepcopy(self.spec)
        site = next(s for s in broken['sites'] if s['site'] == 'normal_hud_load')
        site['patches'][1]['new'] = {'resource': 'rom_041000', 'field': 'no_such_field'}
        with self.assertRaises(ValueError):
            change_surface.derive_patches(broken, self.rgbds)

    def test_base_preimages_match_when_present(self):
        base = ROOT / 'baserom.gb'
        if not base.is_file():
            self.skipTest('baserom.gb not present (public CI has no ROM)')
        change_surface.verify(self.spec, self.manifest, rgbds=self.rgbds,
                              base=base.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
