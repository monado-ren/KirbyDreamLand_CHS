# SPDX-License-Identifier: MIT
"""The screen view of a page must be reconstructible, and labelled honestly.

A page has two different pictures:

  resource view  the resource's own tiles + map, which is what 03_Image/pages
                 stores and what the `linear` addressing annotation keeps
                 self-consistent.
  screen view    the live BG map rendered over live VRAM with the hardware's
                 addressing mode (LCDC=0xE7, i.e. 0x8800).  This is what a
                 player sees, and it needs the baseline VRAM tiles a single
                 resource does not carry.

`render_screens.py` produces the screen view when captures exist and falls back
to the resource view otherwise, recording which one it used.  These tests pin
that behaviour and the chip-level fact behind it.
"""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import common

ROM = ROOT / 'KirbyDreamLand_CHS-Monado.gb'
CAPTURES = ROOT / 'build' / 'visual_regression_capture_test'


class RenderScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ROM.is_file():
            raise unittest.SkipTest('built ROM missing; run 00_Tools/build.py first')
        import render_screens
        cls.module = render_screens

    def test_every_captured_screen_renders(self):
        rows = self.module.collect(CAPTURES if CAPTURES.is_dir() else None)
        self.assertEqual({row['screen'] for row in rows}, set(self.module.SCREENS))
        for row in rows:
            with self.subTest(screen=row['screen']):
                self.assertTrue(row['png'], 'no image produced')

    def test_capture_backed_screens_use_the_screen_view(self):
        if not CAPTURES.is_dir():
            self.skipTest('no captures available')
        rows = self.module.collect(CAPTURES)
        for row in rows:
            with self.subTest(screen=row['screen']):
                self.assertEqual(row['view'], 'screen',
                                 'a capture exists but the resource view was used')

    def test_without_captures_the_resource_view_is_labelled(self):
        rows = self.module.collect(None)
        for row in rows:
            with self.subTest(screen=row['screen']):
                self.assertEqual(row['view'], 'resource')

    def test_hardware_addressing_is_0x8800(self):
        if not CAPTURES.is_dir():
            self.skipTest('no captures available')
        # LCDC bit 4 clear means 0x8800 background addressing.  Every capture was
        # taken with that bit clear, which is why the resource view alone (linear)
        # cannot reproduce the screen.
        seen = 0
        for state in CAPTURES.glob('captures/*/state.json'):
            lcdc = int(json.loads(state.read_text(encoding='utf-8'))['LCDC'], 16)
            self.assertEqual((lcdc >> 4) & 1, 0, '%s runs with 0x8000 addressing'
                             % state.parent.name)
            seen += 1
        self.assertGreater(seen, 0)

    def test_resource_addressing_stays_linear_on_purpose(self):
        # The annotation is the resource's internal index space, not the LCD mode.
        # Flipping it to 0x8800 breaks pages.py render, so guard against it.
        manifest = common.load_manifest()
        for entry in manifest['resources']:
            if entry.get('bundle'):
                with self.subTest(resource=entry['id']):
                    self.assertEqual(entry['bundle']['addressing'], 'linear')


if __name__ == '__main__':
    unittest.main(verbosity=2)
