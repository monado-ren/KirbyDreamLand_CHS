# SPDX-License-Identifier: MIT
"""Automated page capture: cold boot where possible, labelled fixtures elsewhere.

The v0.5.1 BGB package could not be reused for two reasons: it pinned one ROM
hash, and it shipped BGB-native snapshots (`.sna`), which are full machine
snapshots -- CPU registers, VRAM and an embedded ROM MD5 -- not portable game
saves.  This tool rebuilds the same idea on PyBoy, which the original project
also used for its runtime checks.

Screens are reached in two ways, and every capture records which one:

  natural   driven by controller input from a cold boot (title, HUD, configuration)
  fixture   the original project's own technique: patch a throwaway ROM copy so
            a control-flow edge lands on an existing routine, or poke a WRAM
            variable at a hook.  A fixture capture shows that a screen *renders*
            correctly; it does not show that a player can reach it.

Nothing here proves playability -- the original project's unfinished manual
playthrough remains unfinished.

Usage:
    PYTHONPATH=build/pylibs python 00_Tools/capture_pages.py --out build/visual_regression
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import warnings

warnings.filterwarnings('ignore', message='Using SDL2 binaries.*')
from pyboy import PyBoy

import common
import hal_codec

ROOT = common.ROOT

# The game-over fixture the original project used: turn the START check into a
# jump straight to the no-lives-remaining routine.  Verified present in Rev1.
GAMEOVER_SITE = 0x180E4
GAMEOVER_ORIGINAL = bytes.fromhex('3effea')
GAMEOVER_FIXTURE = bytes.fromhex('c35747')

# Stage-intro fixture: the routine at bank 6:$40E4 runs during the intro; setting
# wCurStage there selects which stage bundle is loaded.
STAGE_HOOK_BANK = 6
STAGE_HOOK_ADDR = 0x40E4
W_CUR_STAGE = 0xD03B


# Clear-screen hint pages.  They follow a clear, so a cold boot cannot reach them;
# the title's START branch is pointed at the ending entry instead.  Two entries
# exist and the extra-mode flag decides which hint shows, so both are captured:
#   $40d4 sets wExtraGameEnabled then falls into $486c  -> extra-mode hint
#   $486c directly, flag left 0                          -> normal-mode hint
HINT_START_SITE = 0x1809C          # the `call PlaySE` inside the START branch
HINT_START_ORIGINAL = bytes.fromhex('cd961e')
HINT_FIXTURES = {
    'hint_normal': (bytes.fromhex('c36c48'), 'jp $486c, wExtraGameEnabled stays 0'),
    'hint_extra': (bytes.fromhex('c3d440'), 'jp $40d4, the extra-mode entry'),
}
TILESET_GLYPH_SHA = {}


def _tileset_sha(entry):
    """SHA-256 of a page's tileset as it lands in VRAM (first 6144 bytes)."""
    import hashlib
    import hal_codec
    rom = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()
    raw, _packed = hal_codec.decode(rom[entry['offset']:entry['offset'] + entry['packed_size']])
    return hashlib.sha256(raw[:0x9800 - 0x8000]).hexdigest()


def page_map_bytes(entry):
    """The BG map bytes a bundle/sheet page declares, from its map PNG."""
    import graphics_png
    bundle = entry['bundle']
    return list(graphics_png.png_to_tilemap(
        common.resource_path(bundle['map_png']).read_bytes(),
        bundle['width'], bundle['height']))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class Capture:
    def __init__(self, rom, package):
        self.rom = Path(rom)
        self.package = Path(package)
        self.package.mkdir(parents=True, exist_ok=True)
        self.rom_sha = hashlib.sha256(self.rom.read_bytes()).hexdigest()
        self.screens = []
        self.fixtures = []

    def snapshot(self, boy, name, label, method, note):
        directory = self.package / 'captures' / name
        vram = bytes(boy.memory[0x8000:0xA000])
        write(directory / 'vram.bin', vram)
        write(directory / 'bgmap.bin', vram[0x1800:0x1C00])
        write(directory / 'oam.bin', bytes(boy.memory[0xFE00:0xFEA0]))
        io = bytes(boy.memory[0xFF40:0xFF4C])
        write(directory / 'io.bin', io)
        boy.screen.image.save(directory / 'screen.png')
        state = {
            'LCDC': '0x%02X' % io[0], 'SCX': io[3], 'SCY': io[2],
            'BGP': '0x%02X' % io[7], 'OBP0': '0x%02X' % io[8],
            'OBP1': '0x%02X' % io[9], 'WX': io[0xB], 'WY': io[0xA],
            'LY': io[0x4], 'STAT': '0x%02X' % io[1],
            'rom_sha256': self.rom_sha, 'emulator': 'PyBoy',
            'screenshot_size': [160, 144],
            'reachability': method,
        }
        (directory / 'state.json').write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (directory / 'notes.txt').write_text(
            '%s\n到达方式：%s\n%s\n' % (label, method, note), encoding='utf-8')
        self.screens.append({'screen': name, 'label': label, 'reachability': method,
                             'note': note, 'frame': boy.frame_count})
        print('  %-18s frame %5d  %-8s %s' % (name, boy.frame_count, method, label))


def drive(boy, frames, *buttons):
    for button in buttons:
        boy.button_press(button)
    for _ in range(frames):
        boy.tick()
    for button in buttons:
        boy.button_release(button)
    boy.tick()


def tap(boy, button, frames=2, settle=30):
    """Single short press, then let the screen settle."""
    boy.button_press(button)
    for _ in range(frames):
        boy.tick()
    boy.button_release(button)
    for _ in range(settle):
        boy.tick()


def run(rom, package):
    capture = Capture(rom, package)
    capture.package = Path(package)

    # --- natural: cold boot to the title -------------------------------------
    boy = PyBoy(str(rom), window='null', sound_emulated=False, log_level='ERROR')
    boy.set_emulation_speed(0)
    try:
        for _ in range(232):
            boy.tick()
        capture.snapshot(boy, 'title', '标题', 'natural',
                         '冷启动到标题输入循环（$D050==8）')
        for _ in range(70):
            boy.tick()
        capture.snapshot(boy, 'title_animation', '标题（动画）', 'natural',
                         '标题画面动画推进后')

        if boy.memory[0xD050] == 8:
            drive(boy, 4, 'up', 'select', 'a')
            for _ in range(30):
                boy.tick()
            capture.snapshot(boy, 'main_menu', '主界面（额外游戏）', 'natural',
                             'Up+Select+A 密码开启额外游戏')
            for _ in range(40):
                boy.tick()

        # Configuration and sound test share the title password path.
        # They must be captured while the title loop is still running, before
        # any Start press leaves it.
        if boy.memory[0xD050] == 8:
            drive(boy, 4, 'down', 'select', 'b')
            for _ in range(90):
                boy.tick()
            capture.snapshot(boy, 'configuration', '配置页', 'natural',
                             'Down+Select+B 密码进入配置页')
            # wTemp ($D06B) is the configuration menu index: 2 selects the
            # sound test row, then A confirms it.
            for _ in range(2):
                tap(boy, 'down')
            tap(boy, 'a', settle=90)
            capture.snapshot(boy, 'sound_test', '声音测试', 'natural',
                             '配置页 wTemp=2 后按 A 进入声音测试')

    finally:
        boy.stop(save=False)

    # --- fixture: stage intros ------------------------------------------------
    # The intro routine at bank 6:$40E4 selects the bundle from wCurStage.  The
    # original project poked $D03B from a hook there; the same trick works here
    # and each value maps to exactly one stage page.  Marked `fixture` because a
    # player never reaches these from a cold boot in PyBoy.
    for stage in range(5):
        _boy_ref = []
        with PyBoy(str(rom), window='null', sound_emulated=False,
                   log_level='ERROR') as stage_boy:
            stage_boy.set_emulation_speed(0)
            injected = []

            def inject(_context, stage=stage, injected=injected,
                       _holder=_boy_ref):
                if not injected:
                    current = _holder[0]
                    current.memory[W_CUR_STAGE] = stage
                    injected.append(current.frame_count)

            _boy_ref.append(stage_boy)
            stage_boy.hook_register(STAGE_HOOK_BANK, STAGE_HOOK_ADDR, inject, None)
            for _ in range(232):
                stage_boy.tick()
            stage_boy.button_press('start')
            for _ in range(10):
                stage_boy.tick()
            stage_boy.button_release('start')
            for _ in range(110):
                stage_boy.tick()
            capture.snapshot(stage_boy, 'stage_%d_intro' % (stage + 1),
                             '场景 %d 介绍' % (stage + 1), 'fixture',
                             '冷启动后在 bank6:$40E4 钩子把 wCurStage($D03B) 设为 %d，'
                             '由 game 自己的装载路径载入该关介绍' % stage)
            if stage == 4:
                # Stage 5 is a 256x240 page: the intro scrolls down to reveal the
                # artwork below the caption, so a single frame only shows the top.
                # Capture the scrolled view too.
                for _ in range(300):
                    stage_boy.tick()
                    if stage_boy.memory[0xFF42] >= 60:
                        break
                capture.snapshot(stage_boy, 'stage_5_intro_scrolled',
                                 '场景 5 介绍（滚动后）', 'fixture',
                                 '场景 5 是 256x240 的高图，滚动到 SCY>=60 后可见下方背景')
            capture.fixtures.append({
                'screen': 'stage_%d_intro' % (stage + 1),
                'type': 'WRAM_POKE', 'address': '$D03B', 'value': stage,
                'hook': 'bank6:$40E4',
                'reason': 'Isolated stage-intro load test, not natural progression.',
            })

    # --- fixture: GAME OVER / CONTINUE ---------------------------------------
    # Turn the START check into a jump to the existing no-lives routine, exactly
    # the fixture the original project used at the same Rev1 offset.
    fixture_rom = capture.package / 'gameover_test_only.gb'
    data = bytearray(capture.rom.read_bytes())
    if data[GAMEOVER_SITE:GAMEOVER_SITE + 3] != GAMEOVER_ORIGINAL:
        raise SystemExit('GAMEOVER fixture site 0x%05X does not hold %s'
                         % (GAMEOVER_SITE, GAMEOVER_ORIGINAL.hex()))
    data[GAMEOVER_SITE:GAMEOVER_SITE + 3] = GAMEOVER_FIXTURE
    fixture_rom.write_bytes(bytes(data))
    capture.fixtures.append({
        'screen': 'game_over', 'type': 'ROM_CONTROL_FLOW_TEST_COPY',
        'offset': '0x%05X' % GAMEOVER_SITE,
        'before': GAMEOVER_ORIGINAL.hex(), 'after': GAMEOVER_FIXTURE.hex(),
        'reason': 'Enter existing noLivesRemaining routine after START; not a playthrough.',
        'rom': 'gameover_test_only.gb',
    })
    with PyBoy(str(fixture_rom), window='null', sound_emulated=False,
               log_level='ERROR') as fail_boy:
        fail_boy.set_emulation_speed(0)
        for _ in range(232):
            fail_boy.tick()
        fail_boy.button_press('start')
        for _ in range(10):
            fail_boy.tick()
        fail_boy.button_release('start')
        for _ in range(50):
            fail_boy.tick()
        capture.snapshot(fail_boy, 'game_over', 'GAME OVER', 'fixture',
                         '启动时把 START 判定改成跳到 noLivesRemaining 例程')
        # The CONTINUE page fades in, and during the fade the palette reads
        # 0x00 (a blank screenshot).  Rather than guess a frame count, wait until
        # the live BG map actually matches the CONTINUE page and the palette has
        # settled -- both signals must agree before the screenshot is taken.
        from analyze_playthrough import map_ratio
        manifest = common.load_manifest()
        continue_entry = next(entry for entry in manifest['resources']
                              if entry['label'] == 'continue_map')
        continue_map = page_map_bytes(continue_entry)
        width = continue_entry['bundle']['width']
        height = continue_entry['bundle']['height']
        matched = False
        for _ in range(900):
            fail_boy.tick()
            if fail_boy.memory[0xFF47] != 0xE4:
                continue
            live = bytes(fail_boy.memory[0x9800:0x9C00])
            if map_ratio(live, continue_map, width, height) >= 0.98:
                matched = True
                break
        if not matched:
            raise SystemExit('CONTINUE page never settled')
        capture.snapshot(fail_boy, 'continue', 'CONTINUE / END', 'fixture',
                         'GAME OVER 结束后自动进入继续画面（等到 BG map 与页面源一致且淡入完成）')

    # --- fixture: clear-screen hint pages ------------------------------------
    # These follow a clear, so they cannot be driven from a cold boot.  Pointing
    # the title's START branch at the ending entry walks the game's own ending
    # sequence, which loads each hint page through its real loader.  The capture
    # is taken when the tileset in VRAM hashes exactly to the expected one, so it
    # is proof the page was loaded, not just that it renders in isolation.
    manifest_for_hints = common.load_manifest()
    by_label = {entry['label']: entry for entry in manifest_for_hints['resources']}
    hint_pairs = {
        # screen -> (page label, tileset label)
        'hint_normal': ('ending_03be31', 'ending_03adda'),
        'hint_extra': ('ending_03acec', 'ending_039cbf'),
    }
    import hashlib
    src = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()
    if src[HINT_START_SITE:HINT_START_SITE + len(HINT_START_ORIGINAL)] != HINT_START_ORIGINAL:
        raise SystemExit('hint fixture site 0x%05X does not hold %s'
                         % (HINT_START_SITE, HINT_START_ORIGINAL.hex()))
    for screen, (page_label, tileset_label) in hint_pairs.items():
        patch_bytes, reason = HINT_FIXTURES[screen]
        fixture_rom = capture.package / ('hint_%s_test_only.gb' % screen.split('_')[1])
        data = bytearray(src)
        data[HINT_START_SITE:HINT_START_SITE + len(patch_bytes)] = patch_bytes
        fixture_rom.write_bytes(bytes(data))
        expected_tileset = _tileset_sha(by_label[tileset_label])
        capture.fixtures.append({
            'screen': screen,
            'type': 'ROM_TRAMPOLINE',
            'offset': '0x%05X' % HINT_START_SITE,
            'before': HINT_START_ORIGINAL.hex(),
            'after': patch_bytes.hex(),
            'reason': reason,
            'rom': fixture_rom.name,
        })
        with PyBoy(str(fixture_rom), window='null', sound_emulated=False,
                   log_level='ERROR') as hint_boy:
            hint_boy.set_emulation_speed(0)
            for _ in range(232):
                hint_boy.tick()
            hint_boy.button_press('start')
            for _ in range(12):
                hint_boy.tick()
            hint_boy.button_release('start')
            # The tileset lands before the fade finishes, and a mid-fade frame has
            # BGP=0 -- a blank white screenshot.  A page that is actually being
            # shown has the normal palette (0xE4) and a BG map matching its source,
            # so both signals must agree before the screenshot is taken.
            from analyze_playthrough import map_ratio
            manifest_h = common.load_manifest()
            page_entry = next(e for e in manifest_h['resources']
                              if e['label'] == page_label)
            # A tilemap page spells its own map size; only bundle pages carry a
            # `bundle` block, which is why this does not reuse page_map_bytes.
            spec = page_entry['png']
            width, height = spec['width'], spec['height']
            expected_map = list(hal_codec.decode(
                common.ROOT.joinpath('KirbyDreamLand_CHS-Monado.gb').read_bytes()[
                    page_entry['offset']:page_entry['offset'] + page_entry['packed_size']])[0])
            seen = False
            for _ in range(40000):
                hint_boy.tick()
                live = bytes(hint_boy.memory[0x8000:0x8000 + 0x1800])
                if hashlib.sha256(live).hexdigest() != expected_tileset:
                    continue
                if hint_boy.memory[0xFF47] != 0xE4:
                    continue
                if map_ratio(bytes(hint_boy.memory[0x9800:0x9C00]),
                             expected_map, width, height) >= 0.98:
                    seen = True
                    break
            if not seen:
                raise SystemExit('%s: hint page never settled' % screen)
            capture.snapshot(hint_boy, screen,
                             '通关提示页（%s）' % ('普通模式' if screen == 'hint_normal'
                                                  else '额外模式'),
                             'fixture',
                             '把标题 START 分支改跳结局入口，走游戏自己的结局序列；'
                             '等到 VRAM 里的 tileset 与期望页完全一致时截取')
        fixture_rom.unlink()

    manifest = {
        'rom_sha256': capture.rom_sha,
        'emulator': 'PyBoy',
        'count': len(capture.screens),
        'screens': capture.screens,
        'fixtures': capture.fixtures,
        'reachability_note': 'natural = controller input from cold boot; '
                             'fixture = patched throwaway ROM copy or WRAM poke, '
                             'renders correctly but not proven player-reachable.',
    }
    (capture.package / 'CAPTURE_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    natural = sum(1 for s in capture.screens if s['reachability'] == 'natural')
    fixture = len(capture.screens) - natural
    print('CAPTURES=%d NATURAL=%d FIXTURE=%d ROM_SHA256=%s'
          % (len(capture.screens), natural, fixture, capture.rom_sha))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rom', type=Path,
                        default=ROOT / 'KirbyDreamLand_CHS-Monado.gb')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'build' / 'visual_regression')
    args = parser.parse_args(argv)
    if not args.rom.is_file():
        print('CAPTURE=ERROR missing ROM ' + str(args.rom), file=sys.stderr)
        return 1
    return run(args.rom, args.out)


if __name__ == '__main__':
    sys.exit(main())
