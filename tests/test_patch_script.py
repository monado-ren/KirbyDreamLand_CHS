# SPDX-License-Identifier: MIT
"""The one-command patch path must stay usable from a bare clone.

A fresh clone plus baserom.gb should be enough to produce the localized ROM:
``patch.sh`` needs xdelta3 and the tracked patch, nothing else.  These tests pin
the constants the script checks against, and the published checksum file that
users compare their result with -- that file had silently gone stale across a
release because nothing read it.
"""
from pathlib import Path
import hashlib
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common

SCRIPT = ROOT / 'patch.sh'
SUMS = ROOT / 'SHA256SUMS.txt'
PATCH = ROOT / 'patches' / 'KirbyDreamLand_CHS-Monado.xdelta3'
BASEROM = ROOT / 'baserom.gb'


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PatchScriptTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file(), 'patch.sh is the documented entry point')
        self.assertTrue(SCRIPT.stat().st_mode & 0o111, 'patch.sh must be executable')

    def test_script_does_not_require_the_python_toolchain(self):
        # Keeping this shell-only is the whole point: RGBDS and Pillow must not be
        # needed just to apply a released patch.  Comments are allowed to mention
        # them (to explain the absence), so only executable lines are inspected.
        lines = [line for line in SCRIPT.read_text(encoding='utf-8').splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        body = '\n'.join(lines)
        for forbidden in ('python', 'rgbasm', 'rgblink', 'build_rgbds', 'PIL'):
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, body)

    def test_script_pins_the_same_hashes_as_the_manifest(self):
        manifest = common.load_manifest()
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn(manifest['baseline']['sha256'], text)
        self.assertIn(manifest['target']['sha256'], text)

    def test_published_checksums_match_the_tree(self):
        entries = {}
        for line in SUMS.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            digest, name = re.split(r'\s+', line.strip(), maxsplit=1)
            entries[name.strip()] = digest
        self.assertEqual(set(entries), {
            'patches/KirbyDreamLand_CHS-Monado.xdelta3',
            'KirbyDreamLand_CHS-Monado.gb',
            'baserom.gb',
        })
        self.assertEqual(entries['patches/KirbyDreamLand_CHS-Monado.xdelta3'],
                         sha256_of(PATCH))
        self.assertEqual(entries['KirbyDreamLand_CHS-Monado.gb'],
                         common.load_manifest()['target']['sha256'])
        if BASEROM.is_file():
            self.assertEqual(entries['baserom.gb'], sha256_of(BASEROM))

    @unittest.skipUnless(shutil.which('xdelta3') and BASEROM.is_file(),
                         'needs xdelta3 and baserom.gb')
    def test_script_reproduces_the_release_from_a_clean_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='patch-script-test-') as folder:
            work = Path(folder)
            (work / 'patches').mkdir()
            shutil.copy2(SCRIPT, work / 'script.sh')
            shutil.copy2(PATCH, work / 'patches' / PATCH.name)
            shutil.copy2(BASEROM, work / 'baserom.gb')
            result = subprocess.run(['sh', str(work / 'script.sh')],
                                    capture_output=True, text=True,
                                    cwd=str(work), timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            produced = work / 'KirbyDreamLand_CHS-Monado.gb'
            self.assertTrue(produced.is_file())
            self.assertEqual(sha256_of(produced),
                             common.load_manifest()['target']['sha256'])

    def test_script_refuses_a_wrong_input(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('input is not Japanese Rev 1', text)
        self.assertIn('output already exists', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
