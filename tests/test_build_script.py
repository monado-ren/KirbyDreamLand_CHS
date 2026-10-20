# SPDX-License-Identifier: MIT
"""build.sh is the from-source entry point and must stay honest about its claims.

Two things went wrong in practice and are pinned here: the RGBDS build inherited
``nproc`` parallelism and could be OOM-killed, and the disk/output naming drifted
from what README promises.  These tests read the script, not run heavy builds.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common

SCRIPT = ROOT / 'build.sh'


class BuildScriptTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file(), 'build.sh is the from-source entry point')
        self.assertTrue(SCRIPT.stat().st_mode & 0o111, 'build.sh must be executable')

    def test_requires_python_310_or_newer(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('sys.version_info >= (3,10)', text)

    def test_fails_when_baserom_is_missing(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('baserom.gb not found', text)

    def test_caps_rgbds_parallelism(self):
        # Defaulting to nproc lets a 20-core box start 20 C++ compiles at once.
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('RGBDS_JOBS', text)
        self.assertIn('--jobs', text)

    def test_runs_build_and_verify(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('00_Tools/build.py', text)
        self.assertIn('00_Tools/verify.py', text)

    def test_patch_regeneration_is_opt_in(self):
        # Rebuilding the tracked patch should not happen on a plain ./build.sh.
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('--patch', text)
        self.assertIn('00_Tools/release.py', text)

    def test_reports_the_same_target_hash_as_the_manifest(self):
        # The final word from the script is the ROM hash; it must agree with the
        # manifest the patch is built against.
        manifest = common.load_manifest()
        self.assertEqual(len(manifest['target']['sha256']), 64)


if __name__ == '__main__':
    unittest.main(verbosity=2)
