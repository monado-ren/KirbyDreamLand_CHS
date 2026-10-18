# SPDX-License-Identifier: MIT
"""Portable no-ROM tests. All cartridge-sized fixtures are generated dummy data."""
from pathlib import Path
import copy
import hashlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import common
import graphics_png
import hal_codec

BASE_SHA256 = 'c4c6aff6242116c4f26bdcf3343b6c27836010853b8753da8b0cb953a200834a'
TARGET_SHA256 = 'f96fe0ecac53cc586eac19b53fe1b50cef3fd1751261ae273c2356b2c6c62795'
REV1_FIXES = ((0x37B1, bytes.fromhex('fa14d4a7c0')),
              (0x434B, bytes.fromhex('ea14d4')),
              (0x1418C, bytes.fromhex('3807')))
BAT = bytes.fromhex('0302eff8195308402534')


class ReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()

    def test_exact_input_and_output_fingerprints(self):
        m = self.manifest
        self.assertEqual(m['baseline']['size'], 0x40000)
        self.assertEqual(m['target']['size'], 0x80000)
        self.assertEqual(m['baseline']['sha256'], BASE_SHA256)
        self.assertEqual(m['target']['sha256'], TARGET_SHA256)
        self.assertEqual(m['baseline']['md5'], '995ce81fe91162cff295badd94e366f3')
        self.assertEqual(m['target']['md5'], '8b88da8006dd245bcecf87ee1d65b2c8')

    def test_rev1_code_and_revision_are_not_patch_targets(self):
        used = {at for item in self.manifest['patches']
                for at in range(item['offset'], item['offset'] + len(bytes.fromhex(item['replacement_hex'])))}
        self.assertTrue(used)
        for offset, value in REV1_FIXES:
            self.assertFalse(used & set(range(offset, offset + len(value))))
        self.assertNotIn(0x14C, used)
        self.assertNotIn(0x3DA21, used)
        self.assertNotIn(0x3DA22, used)

    def test_patches_are_small_preimage_checked_changes(self):
        self.assertEqual(len(self.manifest['patches']), 110)
        self.assertEqual(sum(len(bytes.fromhex(p['replacement_hex'])) for p in self.manifest['patches']), 198)
        for item in self.manifest['patches']:
            self.assertEqual(len(item['expected_hex']), len(item['replacement_hex']))

    def test_all_raw_resources_recompress_exactly(self):
        prepared = common.prepare_resources(self.manifest)
        self.assertEqual(len(prepared), 71)
        for spec, raw, packed in prepared:
            with self.subTest(resource=spec['id']):
                self.assertEqual(hal_codec.decode(packed), (raw, len(packed)))
                self.assertEqual(hashlib.sha256(raw).hexdigest(), spec['decoded_sha256'])
                self.assertEqual(hashlib.sha256(packed).hexdigest(), spec['packed_sha256'])
                self.assertLessEqual(len(packed), spec['capacity'])

    def test_wrong_revision_sized_dummy_rom_rejected(self):
        with self.assertRaisesRegex(common.ProjectError, 'Wrong base ROM'):
            common.validate_input(bytes(0x40000), self.manifest)

    def test_truncated_input_rejected(self):
        with self.assertRaisesRegex(common.ProjectError, 'size mismatch'):
            common.validate_input(b'not a ROM', self.manifest)

    def test_cli_missing_input_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'out.gb'
            result = subprocess.run([sys.executable, '-B', '-S', str(ROOT/'tools/build.py'),
                '--rom', str(Path(directory)/'missing.gb'), '--output', str(target)],
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('BUILD=ERROR', result.stderr)
            self.assertFalse(target.exists())

    def test_cli_wrong_input_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'dummy.gb'; source.write_bytes(bytes(0x40000))
            target = Path(directory)/'out.gb'
            result = subprocess.run([sys.executable, '-B', '-S', str(ROOT/'tools/build.py'),
                '--rom', str(source), '--output', str(target)], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Wrong base ROM', result.stderr)
            self.assertEqual(source.read_bytes(), bytes(0x40000))
            self.assertFalse(target.exists())

    def test_builder_imports_without_site_packages(self):
        result = subprocess.run([sys.executable, '-B', '-S', str(ROOT/'tools/build.py'), '--help'],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--rom', result.stdout)

    def test_selftest_requires_no_rom_or_site_packages(self):
        result = subprocess.run([sys.executable, '-B', '-S', str(ROOT/'tools/selftest.py')],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SELFTEST=PASS', result.stdout)
        self.assertIn('NO_ROM=YES', result.stdout)


class SyntheticCompilerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        resource = self.root/'source/graphics/example.png'; resource.parent.mkdir(parents=True)
        self.raw = bytes(range(16))*4
        self.png = graphics_png.tiles_to_png(self.raw, 4); resource.write_bytes(self.png)
        packed = hal_codec.pack(self.raw)
        base = bytearray(0x40000); base[0x14C] = 1; base[0x148] = 3
        for offset, value in REV1_FIXES:base[offset:offset + len(value)] = value
        base[0x3DA1D:0x3DA27] = BAT
        self.base = bytes(base)
        expected = bytearray(self.base); expected.extend(b'\xff'*0x40000)
        expected[0x148] = 4; expected[0x40000:0x40000 + len(packed)] = packed
        self.expected = common.checksums(expected)
        self.manifest = {
            'schema_version': 1, 'release': 'test', 'fill_byte': 255,
            'baseline': common.fingerprints(self.base), 'target': common.fingerprints(self.expected),
            'patches': [{'offset': 0x148, 'expected_hex': '03', 'replacement_hex': '04', 'field': 'test'}],
            'resources': [{'id': 'test', 'offset': 0x40000, 'capacity': 256, 'bank': 16, 'cpu_address': 0x4000,
                'format': 'hal-greedy-v1', 'source': 'source/graphics/example.png',
                'png': {'mode': graphics_png.TILES_MODE, 'tiles_per_row': 4, 'tile_count': 4},
                'decoded_size': len(self.raw), 'decoded_sha256': hashlib.sha256(self.raw).hexdigest(),
                'packed_size': len(packed), 'packed_sha256': hashlib.sha256(packed).hexdigest()}],
        }
        self.root_mock = patch.object(common, 'ROOT', self.root); self.root_mock.start()

    def tearDown(self):
        self.root_mock.stop(); self.tmp.cleanup()

    def test_construct_expands_and_matches_all_output_hashes(self):
        result = common.construct(self.base, self.manifest)
        self.assertEqual(result, self.expected)
        self.assertEqual(len(result), 0x80000)
        self.assertEqual(common.verify_output(result, self.manifest), common.fingerprints(result))

    def test_repeated_build_is_deterministic(self):
        self.assertEqual(common.construct(self.base, self.manifest), common.construct(self.base, self.manifest))

    def test_base_is_unchanged(self):
        original = self.base[:]; common.construct(self.base, self.manifest)
        self.assertEqual(self.base, original)

    def test_patch_preimage_is_checked(self):
        m = copy.deepcopy(self.manifest); m['patches'][0]['expected_hex'] = '02'
        with self.assertRaisesRegex(common.ProjectError, 'preimage'):
            common.construct(self.base, m)

    def test_changed_resource_rejected_in_strict_build(self):
        (self.root/'source/graphics/example.png').write_bytes(
            graphics_png.tiles_to_png(bytes(reversed(self.raw)), 4))
        with self.assertRaisesRegex(common.ProjectError, 'Resource changed'):
            common.construct(self.base, self.manifest)

    def test_resource_hash_tamper_rejected(self):
        m = copy.deepcopy(self.manifest); m['resources'][0]['decoded_sha256'] = '0'*64
        with self.assertRaises(common.ProjectError):common.construct(self.base, m)

    def test_packed_hash_tamper_rejected(self):
        m = copy.deepcopy(self.manifest); m['resources'][0]['packed_sha256'] = '0'*64
        with self.assertRaises(common.ProjectError):common.construct(self.base, m)

    def test_output_hash_tamper_rejected(self):
        m = copy.deepcopy(self.manifest); m['target']['sha256'] = '0'*64
        with self.assertRaisesRegex(common.ProjectError, 'sha256'):
            common.construct(self.base, m)

    def test_rev1_guard_checked_even_with_matching_fingerprints(self):
        for offset, value in REV1_FIXES:
            with self.subTest(offset=offset):
                changed = bytearray(self.expected); changed[offset] ^= 1
                changed = common.checksums(changed)
                m = copy.deepcopy(self.manifest); m['target'] = common.fingerprints(changed)
                with self.assertRaisesRegex(common.ProjectError, 'Native Rev1 fix'):
                    common.verify_output(changed, m)

    def test_bat_rev1_animation_pointer_checked(self):
        changed = bytearray(self.expected); changed[0x3DA21] ^= 1
        changed = common.checksums(changed); m = copy.deepcopy(self.manifest)
        m['target'] = common.fingerprints(changed)
        with self.assertRaisesRegex(common.ProjectError, 'animation pointer'):
            common.verify_output(changed, m)

    def test_bad_revision_checked_after_hashes(self):
        changed = bytearray(self.expected); changed[0x14C] = 0
        changed = common.checksums(changed); m = copy.deepcopy(self.manifest)
        m['target'] = common.fingerprints(changed)
        with self.assertRaisesRegex(common.ProjectError, 'Revision'):
            common.verify_output(changed, m)

    def test_overlapping_patches_rejected(self):
        m = copy.deepcopy(self.manifest); m['patches'].append(m['patches'][0].copy())
        with self.assertRaisesRegex(common.ProjectError, 'Overlapping'):
            common.validate_manifest(m)

    def test_resource_bank_crossing_rejected(self):
        m = copy.deepcopy(self.manifest); m['resources'][0]['capacity'] = 0x4001
        with self.assertRaisesRegex(common.ProjectError, 'crosses bank'):
            common.validate_manifest(m)

    def test_resource_path_escape_rejected(self):
        for path in ('../outside.png', 'source/graphics/../../../outside.png', '/' + 'tmp/outside.png', 'C' + ':' + '/outside.png', 'source/graphics/example.bin'):
            with self.subTest(path=path), self.assertRaises(common.ProjectError):common.resource_path(path)

    def test_write_does_not_overwrite_inputs(self):
        path = self.root/'input.gb'; path.write_bytes(b'original')
        with self.assertRaises(common.ProjectError):common.write_output(path, b'changed', (path,))
        self.assertEqual(path.read_bytes(), b'original')

    def test_write_output_roundtrip(self):
        path = self.root/'build/out.gb'; common.write_output(path, self.expected)
        self.assertEqual(path.read_bytes(), self.expected)

    def test_rollback_uses_separate_copy(self):
        modified = common.construct(self.base, self.manifest)
        target = self.root/'modified.gb'; rollback = self.root/'rollback.gb'
        common.write_output(target, modified); common.write_output(rollback, modified)
        common.write_output(rollback, self.base)
        self.assertEqual(rollback.read_bytes(), self.base)
        self.assertEqual(target.read_bytes(), modified)

    def test_explicit_resource_repack_records_new_target(self):
        changed = bytes(reversed(self.raw))
        (self.root/'source/graphics/example.png').write_bytes(graphics_png.tiles_to_png(changed, 4))
        m, output = common.refreshed_manifest(self.base, self.manifest, 'test-edit')
        self.assertEqual(m['parent_release'], 'test')
        self.assertEqual(m['release'], 'test-edit')
        self.assertEqual(len(m['resource_edits']), 1)
        self.assertEqual(common.construct(self.base, m), output)
        self.assertNotEqual(output, self.expected)


class CodecAndPatchTests(unittest.TestCase):
    def test_hal_resource_roundtrips(self):
        for value in (b'', b'A', b'A'*1024, b'AB'*600, bytes(range(256))*3):
            with self.subTest(size=len(value)):
                packed = hal_codec.pack(value)
                self.assertEqual(hal_codec.decode(packed), (value, len(packed)))

    def test_hal_truncation_rejected(self):
        for value in (b'', b'\x00', b'\xe0'):
            with self.subTest(value=value), self.assertRaises(ValueError):hal_codec.decode(value)

    def test_ips_literal_rle_expansion_roundtrip(self):
        base = b'base-data'; target = base + b'Z'*2048 + bytes(range(256))
        encoded = common.create_ips(base, target)
        self.assertTrue(encoded.startswith(b'PATCH') and encoded.endswith(b'EOF'))
        self.assertEqual(common.apply_ips(base, encoded), target)
        self.assertIn(b'\x00\x00\x08\x00Z', encoded)

    def test_ips_equal_input_is_noop(self):
        self.assertEqual(common.apply_ips(b'unchanged', common.create_ips(b'unchanged', b'unchanged')), b'unchanged')

    def test_invalid_ips_rejected(self):
        for value in (b'', b'PATCH', b'PATCHEOFextra', b'PATCH\x00\x00\x00\x00\x01', b'PATCH\x00\x00\x00\x00\x00\x00\x00ZEOF'):
            with self.subTest(value=value), self.assertRaises(common.ProjectError):common.apply_ips(b'', value)

    def test_ips_optional_truncation(self):
        self.assertEqual(common.apply_ips(b'abcdef', b'PATCHEOF\x00\x00\x03'), b'abc')


if __name__ == '__main__':
    unittest.main()
