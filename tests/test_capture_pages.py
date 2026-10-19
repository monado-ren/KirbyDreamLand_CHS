# SPDX-License-Identifier: MIT
"""Runtime capture tests: the built ROM must actually reach the expected screens.

`audit_rom_pages.py` proves the ROM *contains* the right bytes; this suite proves
the game *renders* them on screen.  Screens are matched by comparing captured
BG-map cells against the page models, so a capture only passes when the live
screen really is that page.

The 12 screens split into two reachability classes, recorded in the manifest:

  natural  controller input from a cold boot (title, menu, configuration, HUD)
  fixture  the original project's technique -- patch a throwaway ROM copy or poke
           a WRAM variable at a hook.  A fixture screen renders correctly; it is
           not proof a player can reach it.

PyBoy is optional: without it these tests skip rather than fail, because the
public CI installs only `requirements.txt`.
"""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '00_Tools'))

import analyze_playthrough
import common

try:                                            # optional dependency
    import pyboy                                # noqa: F401
    HAVE_PYBOY = True
except Exception:                               # noqa: BLE001 - any import problem means skip
    HAVE_PYBOY = False

ROM = ROOT / 'KirbyDreamLand_CHS-Monado.gb'
PACKAGE = ROOT / 'build' / 'visual_regression_capture_test'

# screen -> (page, minimum map/tile match ratio)
EXPECTED = {
    'title': ('rom_070000', 0.98),
    'title_animation': ('rom_070000', 0.98),
    'main_menu': ('rom_070000', 0.98),
    'configuration': ('rom_05c000', 0.98),
    'sound_test': ('rom_0438f6', 0.98),
    'stage_1_intro': ('rom_06c000', 0.98),
    'stage_2_intro': ('rom_06c70b', 0.98),
    'stage_3_intro': ('rom_06cda8', 0.98),
    'stage_4_intro': ('rom_06d490', 0.98),
    'stage_5_intro': ('rom_06db85', 0.98),
    'stage_5_intro_scrolled': ('rom_06db85', 0.98),
    'game_over': ('rom_04454c', 0.98),
    'continue': ('rom_044734', 0.98),
}


def page_models():
    manifest = common.load_manifest()
    spec = json.loads((ROOT / '06_ProgramFix' / 'change_surface.json').read_text(encoding='utf-8'))
    models, _roles = analyze_playthrough.page_models(manifest, spec)
    return models


def score(data, model, page_id):
    if page_id == 'rom_070000':
        return analyze_playthrough.title_row_shift(
            data, model['map'], model['width'], model['height'])[0]
    return analyze_playthrough.map_ratio(
        data, model['map'], model['width'], model['height'])


@unittest.skipUnless(HAVE_PYBOY, 'PyBoy is not installed; runtime capture skipped')
class CapturePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ROM.is_file():
            raise unittest.SkipTest('built ROM missing; run 00_Tools/build.py first')
        import capture_pages
        capture_pages.main(['--rom', str(ROM), '--out', str(PACKAGE)])
        cls.manifest = json.loads((PACKAGE / 'CAPTURE_MANIFEST.json').read_text(encoding='utf-8'))
        cls.models = page_models()

    def test_capture_manifest_records_the_built_rom(self):
        import hashlib
        expected = hashlib.sha256(ROM.read_bytes()).hexdigest()
        self.assertEqual(self.manifest['rom_sha256'], expected)

    def test_every_expected_screen_was_captured(self):
        captured = {screen['screen'] for screen in self.manifest['screens']}
        self.assertEqual(captured, set(EXPECTED))

    def test_each_screen_matches_its_page(self):
        for screen, (page, minimum) in sorted(EXPECTED.items()):
            with self.subTest(screen=screen):
                directory = PACKAGE / 'captures' / screen
                vram = (directory / 'vram.bin').read_bytes()
                bgmap = (directory / 'bgmap.bin').read_bytes()
                model = self.models[page]
                best = max(score(data, model, page)
                           for data in (bgmap, vram[0x1800:0x1C00], vram[0x1C00:0x2000]))
                self.assertGreaterEqual(best, minimum,
                                        '%s does not render %s (best %.3f)'
                                        % (screen, page, best))

    def test_reachability_is_labelled_on_every_capture(self):
        natural = fixture = 0
        for screen in self.manifest['screens']:
            with self.subTest(screen=screen['screen']):
                self.assertIn(screen['reachability'], ('natural', 'fixture'))
            if screen['reachability'] == 'natural':
                natural += 1
            else:
                fixture += 1
        self.assertEqual((natural, fixture), (5, 8))

    def test_fixtures_are_documented_with_their_mechanism(self):
        types = {item['type'] for item in self.manifest['fixtures']}
        self.assertIn('WRAM_POKE', types)
        self.assertIn('ROM_CONTROL_FLOW_TEST_COPY', types)
        for item in self.manifest['fixtures']:
            self.assertTrue(item['reason'], 'fixture without a documented reason')

    def test_capture_does_not_modify_the_released_rom(self):
        import hashlib
        before = hashlib.sha256(ROM.read_bytes()).hexdigest()
        self.assertEqual(before, self.manifest['rom_sha256'])
        # The game-over fixture lives in a throwaway copy inside the package.
        fixture = PACKAGE / 'gameover_test_only.gb'
        self.assertTrue(fixture.is_file())
        self.assertNotEqual(fixture.read_bytes(), ROM.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
