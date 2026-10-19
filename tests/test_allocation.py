# SPDX-License-Identifier: MIT
"""Edited-resource relocation: free space, loader patch rewriting and refusal."""
from pathlib import Path
import contextlib
import copy
import io
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import allocation
import common
import graphics_png as gp
import hal_codec


class AllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()

    def test_free_gaps_do_not_overlap_allocations(self):
        gaps = allocation.free_gaps(self.manifest)
        self.assertTrue(gaps)
        by_interval = allocation.allocations(self.manifest)
        for start, end in gaps:
            self.assertLess(start, end)
            self.assertGreaterEqual(start, allocation.GRAPHICS_LOW)
            self.assertLessEqual(end, allocation.GRAPHICS_HIGH)
            for used_start, used_end in by_interval:
                self.assertTrue(end <= used_start or start >= used_end)

    def test_refuses_resources_without_loader_patch(self):
        # v0.5.2 dropped every unreferenced copy, so synthesise one: relocation
        # must still refuse a resource that no loader can point at.
        manifest = copy.deepcopy(self.manifest)
        orphan = copy.deepcopy(manifest['resources'][0])
        orphan['referenced_by_current_localized_loaders'] = False
        # loader_patches matches on label, so give it one no loader uses.
        orphan['label'] = 'no_loader_references_this_label'
        with self.assertRaises(common.ProjectError):
            allocation.relocate(manifest, orphan, 64)

    def test_relocation_updates_loader_bank_bytes(self):
        manifest = copy.deepcopy(self.manifest)
        tileset = next(entry for entry in manifest['resources']
                       if entry['id'] == 'rom_048000')
        before = {item['field']: item['replacement_hex'] for item in manifest['patches']}
        with contextlib.redirect_stdout(io.StringIO()):
            allocation.relocate(manifest, tileset, tileset['packed_size'] + 16)
        after = {item['field']: item['replacement_hex'] for item in manifest['patches']}
        self.assertNotEqual(tileset['offset'], 0x48000)
        self.assertEqual(tileset['cpu_address'], 0x4000)  # bank-aligned graphics keep the address
        changed = [field for field in before if before[field] != after[field]]
        self.assertTrue(changed, 'expected at least one loader patch to change')
        common.validate_manifest(manifest)

    def test_relocation_updates_map_address_and_bank(self):
        manifest = copy.deepcopy(self.manifest)
        entry = next(item for item in manifest['resources'] if item['id'] == 'rom_048462')
        tileset = next(item for item in manifest['resources']
                       if item['id'] == entry['png']['tileset'])
        with contextlib.redirect_stdout(io.StringIO()):
            allocation.relocate(manifest, tileset, tileset['packed_size'] + 16)
        old = (entry['offset'], entry['bank'], entry['cpu_address'])
        with contextlib.redirect_stdout(io.StringIO()):
            allocation.relocate(manifest, entry, entry['packed_size'] + 8)
        self.assertNotEqual((entry['offset'], entry['bank'], entry['cpu_address']), old)
        patches = allocation.loader_patches(manifest, entry['label'])
        self.assertTrue(patches)
        addresses = entry['cpu_address'].to_bytes(2, 'little')
        self.assertTrue(any(addresses in bytes.fromhex(item['replacement_hex'])
                            for item in patches) or entry['cpu_address'] == 0x4000)
        common.validate_manifest(manifest)

    def test_relocation_does_not_overlap_or_cross_banks(self):
        manifest = copy.deepcopy(self.manifest)
        for entry_id in ('rom_048000', 'rom_048462'):
            entry = next(item for item in manifest['resources'] if item['id'] == entry_id)
            with contextlib.redirect_stdout(io.StringIO()):
                allocation.relocate(manifest, entry, entry['packed_size'] + 32)
        common.validate_manifest(manifest)


if __name__ == '__main__':
    unittest.main()
