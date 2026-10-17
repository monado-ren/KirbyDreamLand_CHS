# SPDX-License-Identifier: MIT
"""Release CLI protection and xdelta invocation tests; no external binary needed."""
from pathlib import Path
from contextlib import redirect_stdout
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import common
import release
import apply_patch
import rollback
import xdelta_tools


class ReleaseGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.base = self.root/'baserom.gb'; self.base.write_bytes(b'dummy original')
        self.delta = self.root/'patch.xdelta3'; self.delta.write_bytes(b'dummy patch')
        self.manifest = self.root/'manifest.json'; self.manifest.write_text('{}', encoding='utf8')
        self.info = {'release': 'test', 'default_output': 'KirbyDreamLand_CHS-Monado.gb'}
        self.root_patch = patch.object(common, 'ROOT', self.root); self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop(); self.tmp.cleanup()

    def release_reject(self, output, delta):
        args = ['release.py','--rom',str(self.base),'--output',str(output),'--patch',str(delta),'--manifest',str(self.manifest)]
        with patch.object(sys, 'argv', args), patch.object(common, 'load_manifest', return_value=self.info), \
             patch.object(common, 'validate_input'), patch.object(xdelta_tools, 'executable') as external:
            with self.assertRaises(common.ProjectError):release.main()
            external.assert_not_called()
        self.assertEqual(self.base.read_bytes(), b'dummy original')
        self.assertEqual(self.manifest.read_text(encoding='utf8'), '{}')

    def test_release_rejects_rom_over_input(self):
        self.release_reject(self.base, self.delta)

    def test_release_rejects_patch_over_input(self):
        self.release_reject(self.root/'out.gb', self.base)

    def test_release_rejects_output_over_manifest(self):
        self.release_reject(self.manifest, self.delta)

    def test_release_rejects_same_rom_and_patch_destination(self):
        output = self.root/'out.gb'; self.release_reject(output, output)

    def test_release_rejects_output_in_source(self):
        self.release_reject(self.root/'source/out.gb', self.delta)

    def rollback_reject(self, target):
        args = ['rollback.py','--base',str(self.base),'--target',str(target)]
        with patch.object(sys,'argv',args), patch.object(common,'load_manifest',return_value=self.info), \
             patch.object(common,'validate_input'), patch.object(common,'verify_output') as verify:
            with self.assertRaises(common.ProjectError):rollback.main()
            verify.assert_not_called()
        self.assertEqual(self.base.read_bytes(), b'dummy original')

    def test_rollback_rejects_input_as_destination(self):
        self.rollback_reject(self.base)

    def test_rollback_rejects_main_build_as_destination(self):
        self.rollback_reject(self.root/self.info['default_output'])

    def test_rollback_separate_copy_restores_without_touching_main(self):
        target = self.root/'rollback.gb'; target.write_bytes(b'localized dummy')
        main = self.root/self.info['default_output']; main.write_bytes(b'localized dummy')
        args = ['rollback.py','--base',str(self.base),'--target',str(target)]
        with patch.object(sys,'argv',args), patch.object(common,'load_manifest',return_value=self.info), \
             patch.object(common,'validate_input'), patch.object(common,'verify_output') as verify:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(rollback.main(), 0)
            self.assertIn('ROLLBACK=PASS', output.getvalue())
            verify.assert_called_once_with(b'localized dummy', self.info)
        self.assertEqual(target.read_bytes(), b'dummy original')
        self.assertEqual(self.base.read_bytes(), b'dummy original')
        self.assertEqual(main.read_bytes(), b'localized dummy')

    def test_rollback_rejects_unverified_target_without_writing(self):
        target = self.root/'rollback.gb'; target.write_bytes(b'not localized')
        args = ['rollback.py','--base',str(self.base),'--target',str(target)]
        with patch.object(sys,'argv',args), patch.object(common,'load_manifest',return_value=self.info), \
             patch.object(common,'validate_input'), patch.object(common,'verify_output',side_effect=common.ProjectError('wrong target')):
            with self.assertRaisesRegex(common.ProjectError,'wrong target'):rollback.main()
        self.assertEqual(target.read_bytes(), b'not localized')

    def apply_reject(self, target):
        args = ['apply_patch.py','--rom',str(self.base),'--patch',str(self.delta),
                '--output',str(target),'--manifest',str(self.manifest)]
        def fake_decode(executable, base, delta, output):
            output.write_bytes(b'localized dummy')
        with patch.object(sys,'argv',args), patch.object(common,'load_manifest',return_value=self.info), \
             patch.object(common,'validate_input'), patch.object(common,'verify_output'), \
             patch.object(xdelta_tools,'executable',return_value='unused'), patch.object(xdelta_tools,'decode',side_effect=fake_decode):
            with self.assertRaises(common.ProjectError):apply_patch.main()
        self.assertEqual(self.base.read_bytes(), b'dummy original')
        self.assertEqual(self.delta.read_bytes(), b'dummy patch')
        self.assertEqual(self.manifest.read_text(encoding='utf8'), '{}')

    def test_apply_rejects_output_over_input_rom(self):
        self.apply_reject(self.base)

    def test_apply_rejects_output_over_patch(self):
        self.apply_reject(self.delta)

    def test_apply_rejects_output_over_manifest(self):
        self.apply_reject(self.manifest)


class XdeltaWrapperTests(unittest.TestCase):
    def test_tracked_patch_is_binary_vcdiff_without_application_header(self):
        path = ROOT/'KirbyDreamLand_CHS-Monado.xdelta3'
        self.assertTrue(path.is_file(), 'The release patch must be present')
        self.assertEqual(path.read_bytes()[:5], bytes.fromhex('d6c3c40000'))

    def test_encoder_32_disables_armor_and_embedded_filenames(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'patch.xdelta3'
            def fake_run(exe, arguments):output.write_bytes(bytes.fromhex('d6c3c40000'))
            with patch.object(xdelta_tools,'version',return_value=(3,2,2)), patch.object(xdelta_tools,'run',side_effect=fake_run) as run:
                self.assertEqual(xdelta_tools.encode('unused','base.gb','out.gb',output), '3.2.2')
                args = run.call_args.args[1]
                self.assertEqual(args[:8], ['-a','-e','-9','-S','none','-A','-D','-s'])

    def test_encoder_31_does_not_use_new_armor_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'patch.xdelta3'
            def fake_run(exe, arguments):output.write_bytes(bytes.fromhex('d6c3c40000'))
            with patch.object(xdelta_tools,'version',return_value=(3,1,0)), patch.object(xdelta_tools,'run',side_effect=fake_run) as run:
                self.assertEqual(xdelta_tools.encode('unused','base.gb','out.gb',output), '3.1.0')
                self.assertNotIn('-a', run.call_args.args[1])
                self.assertIn('-A', run.call_args.args[1])

    def test_ambient_xdelta_options_are_removed(self):
        fake = subprocess.CompletedProcess(['unused'], 0, b'ok', b'')
        with patch.dict(os.environ, {'XDELTA':'untrusted options'}), patch.object(subprocess,'run',return_value=fake) as run:
            self.assertEqual(xdelta_tools.run('unused',['-V']), 'ok')
            self.assertNotIn('XDELTA', run.call_args.kwargs['env'])
            self.assertEqual(run.call_args.kwargs['timeout'], 120)

    def test_external_failure_is_checked(self):
        fake = subprocess.CompletedProcess(['unused'], 1, b'', b'fixture failure')
        with patch.object(subprocess,'run',return_value=fake), self.assertRaisesRegex(common.ProjectError,'fixture failure'):
            xdelta_tools.run('unused',['-V'])

    def test_unrecognized_version_rejected(self):
        with patch.object(xdelta_tools,'run',return_value='unknown tool'), self.assertRaises(common.ProjectError):
            xdelta_tools.version('unused')

    def test_version_parser_accepts_expected_version(self):
        with patch.object(xdelta_tools,'run',return_value='Xdelta version 3.2.2'):
            self.assertEqual(xdelta_tools.version('unused'), (3,2,2))


if __name__ == '__main__':
    unittest.main()
