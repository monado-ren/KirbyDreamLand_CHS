# SPDX-License-Identifier: MIT
"""No-ROM public release checks and isolated scanner regression fixtures."""
from pathlib import Path
import base64
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import audit_public_tree as audit


class PublicTreeTests(unittest.TestCase):
    def test_public_candidates_are_clean(self):
        report = audit.audit_tree(ROOT)
        self.assertEqual(report['status'], 'PASS', report['findings'])
        self.assertGreater(report['files_checked'], 5)

    def test_ignore_covers_local_game_and_runtime_outputs(self):
        patterns = audit.read_ignore(ROOT)
        self.assertTrue(patterns, 'The source tree needs an explicit .gitignore')
        for path in ('baserom.gb', 'KirbyDreamLand_CHS-Monado.gb', 'local.gbc',
                     'capture.sna', 'slot.sav', 'tools/__pycache__/common.pyc',
                     '.venv/python.exe', 'dist/generated.gb'):
            with self.subTest(path=path):
                self.assertTrue(audit.is_ignored(path, patterns), path)
        self.assertFalse(audit.is_ignored('KirbyDreamLand_CHS-Monado.xdelta3', patterns))
        self.assertFalse(audit.is_ignored('source/manifest.json', patterns))

    def test_critical_local_files_not_selected(self):
        paths, _ = audit.public_paths(ROOT)
        self.assertFalse([str(p.relative_to(ROOT)) for p in paths
                          if p.suffix.lower() in {'.gb', '.gbc', '.sna', '.sav', '.exe', '.dll'}])

    def test_boot_signature_length(self):
        self.assertEqual(len(audit.GB_LOGO), 48)


class ScannerFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def scan_file(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf8') if isinstance(content, str) else content)
        return audit.audit_tree(self.root, [path])

    def rules(self, result):
        return {finding['rule'] for finding in result['findings']}

    @staticmethod
    def synthetic_header():
        # A minimal artificial header, never a real ROM or game-code fixture.
        data = bytearray(0x150)
        data[0x104:0x134] = audit.GB_LOGO
        data[0x134:0x13e] = b'TEST ONLY\0'
        return bytes(data)

    def test_plain_source_accepted(self):
        self.assertEqual(self.scan_file('tools/example.py', 'print("ok")\n')['status'], 'PASS')

    def test_local_rom_extension_rejected_even_if_empty(self):
        self.assertIn('FORBIDDEN_FILE_TYPE', self.rules(self.scan_file('input.gb', b'')))

    def test_state_and_archive_extensions_rejected(self):
        for suffix in ('.sna', '.sav', '.zip', '.7z', '.xlsx', '.exe', '.ttf'):
            with self.subTest(suffix=suffix):
                self.assertIn('FORBIDDEN_FILE_TYPE', self.rules(self.scan_file('sample' + suffix, b'')))

    def test_rom_header_detected_in_renamed_binary(self):
        self.assertIn('CARTRIDGE_HEADER_IN_CONTENT', self.rules(self.scan_file('source/cache.dat', self.synthetic_header())))

    def test_rom_header_detected_after_prefix(self):
        self.assertTrue(audit.contains_rom(b'prefix' + self.synthetic_header() + b'suffix'))

    def test_hex_encoded_header_rejected(self):
        result = self.scan_file('source/sample.json', json.dumps({'blob': self.synthetic_header().hex()}))
        self.assertIn('ENCODED_CARTRIDGE_HEADER', self.rules(result))

    def test_base64_encoded_header_rejected(self):
        text = base64.b64encode(self.synthetic_header()).decode('ascii')
        self.assertIn('ENCODED_CARTRIDGE_HEADER', self.rules(self.scan_file('source/sample.json', json.dumps({'blob': text}))))

    def test_integer_array_header_rejected(self):
        text = json.dumps({'blob': list(self.synthetic_header())})
        self.assertIn('ENCODED_CARTRIDGE_HEADER', self.rules(self.scan_file('source/sample.json', text)))

    def test_small_resource_binary_accepted(self):
        self.assertEqual(self.scan_file('source/resources/tile.bin', bytes(range(256)))['status'], 'PASS')

    def test_pe_content_rejected_without_executable_suffix(self):
        data = bytearray(96); data[:2] = b'MZ'; struct.pack_into('<I', data, 60, 64); data[64:68] = b'PE\0\0'
        self.assertIn('EXECUTABLE_RUNTIME_IN_CONTENT', self.rules(self.scan_file('source/cache.dat', data)))

    def test_elf_content_rejected(self):
        self.assertIn('EXECUTABLE_RUNTIME_IN_CONTENT', self.rules(self.scan_file('source/cache.dat', b'\x7fELF' + bytes(50))))

    def test_absolute_windows_path_rejected(self):
        value = 'C' + ':' + '/' + 'Users' + '/private/example.txt'
        self.assertIn('ABSOLUTE_PRIVATE_PATH', self.rules(self.scan_file('source/sample.json', json.dumps({'source': value}))))

    def test_absolute_user_path_rejected(self):
        value = '/' + 'home' + '/private/example.txt'
        self.assertIn('ABSOLUTE_PRIVATE_PATH', self.rules(self.scan_file('docs/example.md', value)))

    def test_token_pattern_rejected_without_exposing_secret(self):
        value = 'ghp_' + 'A' * 36
        result = self.scan_file('docs/example.md', value)
        self.assertIn('SECRET_PATTERN', self.rules(result))
        self.assertNotIn(value, json.dumps(result))

    def test_private_key_pattern_rejected(self):
        value = '-----BEGIN ' + 'PRIVATE KEY-----'
        self.assertIn('SECRET_PATTERN', self.rules(self.scan_file('source/sample.txt', value)))

    def test_email_outside_notice_rejected(self):
        value = 'private' + '@' + 'example.invalid'
        self.assertIn('EMAIL_OUTSIDE_LICENSE_NOTICE', self.rules(self.scan_file('docs/example.md', value)))

    def test_upstream_license_contact_retained(self):
        value = 'author' + '@' + 'example.invalid'
        self.assertEqual(self.scan_file('licenses/UPSTREAM.txt', value)['status'], 'PASS')

    def test_uppercase_license_directory_contact_retained(self):
        value = 'author' + '@' + 'example.invalid'
        self.assertEqual(self.scan_file('LICENSES/UPSTREAM.txt', value)['status'], 'PASS')

    def test_private_import_rejected(self):
        value = 'import ' + 'localize_jp_example\n'
        self.assertIn('PRIVATE_PROJECT_IMPORT', self.rules(self.scan_file('tools/example.py', value)))

    def test_malformed_json_rejected(self):
        self.assertIn('INVALID_JSON', self.rules(self.scan_file('source/example.json', '{')))

    def test_missing_index_file_reported(self):
        self.assertIn('MISSING_TRACKED_FILE', self.rules(audit.audit_tree(self.root, [self.root/'missing.py'])))

    def test_ignore_does_not_hide_explicit_tracked_rom(self):
        (self.root/'.gitignore').write_text('*.gb\n', encoding='utf8')
        path = self.root/'hidden.gb'; path.write_bytes(b'')
        self.assertIn('FORBIDDEN_FILE_TYPE', self.rules(audit.audit_tree(self.root, [path])))

    def test_directory_ignore_and_negation(self):
        self.assertTrue(audit.is_ignored('dist/output.txt', ['dist/']))
        self.assertTrue(audit.is_ignored('tools/__pycache__/test.pyc', ['__pycache__/']))
        self.assertFalse(audit.is_ignored('keep.gb', ['*.gb', '!keep.gb']))

    def test_git_root_uses_empty_prefix_not_cross_platform_absolute_path(self):
        def fake_run(args, **kwargs):
            if 'rev-parse' in args:
                if '--show-toplevel' in args:
                    return subprocess.CompletedProcess(args, 0, '/' + 'home' + '/Fixture/project\n', '')
                self.assertIn('--is-inside-work-tree', args)
                self.assertIn('--show-prefix', args)
                return subprocess.CompletedProcess(args, 0, 'true\r\n\r\n', '')
            return subprocess.CompletedProcess(args, 0, b'README.md\0tools/example.py\0', b'')
        with patch.object(audit.subprocess, 'run', side_effect=fake_run) as command:
            paths, selection = audit.public_paths(self.root, tracked=True)
        self.assertEqual(selection, 'git-index')
        self.assertEqual(paths, [self.root/'README.md', self.root/'tools/example.py'])
        self.assertEqual(command.call_count, 2)
        self.assertNotIn('--show-toplevel', command.call_args_list[0].args[0])

    def test_git_nested_directory_is_not_treated_as_its_own_repository(self):
        reply = subprocess.CompletedProcess(['git'], 0, 'true\nsubdirectory/\n', '')
        with patch.object(audit.subprocess, 'run', return_value=reply), self.assertRaisesRegex(ValueError, 'requires a Git repository'):
            audit.public_paths(self.root, tracked=True)

    def test_git_bare_repository_is_not_a_public_worktree(self):
        reply = subprocess.CompletedProcess(['git'], 0, 'false\n\n', '')
        with patch.object(audit.subprocess, 'run', return_value=reply), self.assertRaises(ValueError):
            audit.public_paths(self.root, tracked=True)

    def test_git_candidate_selection_includes_unignored_untracked_files(self):
        replies = [subprocess.CompletedProcess(['git'], 0, 'true\n\n', ''),
                   subprocess.CompletedProcess(['git'], 0, b'new.py\0', b'')]
        with patch.object(audit.subprocess, 'run', side_effect=replies) as command:
            paths, selection = audit.public_paths(self.root)
        self.assertEqual(selection, 'git-public-candidates')
        self.assertEqual(paths, [self.root/'new.py'])
        self.assertIn('--others', command.call_args.args[0])
        self.assertIn('--exclude-standard', command.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
