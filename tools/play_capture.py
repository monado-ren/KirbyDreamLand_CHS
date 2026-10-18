# SPDX-License-Identifier: MIT
"""Interactive playthrough recorder for the runtime page audit.

Run this on a machine with a display, play the localized ROM normally, and the
script snapshots the live VRAM (8 KiB), BG map/scroll registers and a screenshot
every ``--interval`` frames.  The resulting ``build/playthrough/`` directory is
analysed by ``tools/analyze_playthrough.py``; no manual labels are needed
because pages are identified from their tile/map bytes.

PyBoy keyboard controls: arrows = D-pad, A = A, S = B, Return = Start,
Backspace = Select, Esc = quit.  PyBoy is a local, gitignored investigation
dependency; the ROM and captures are never committed.

Usage:
    PYTHONPATH=build/pylibs python tools/play_capture.py [--rom ROM]
    # ... play through title/config/sound test/stages/gallery/ending ...
    # press Esc when done, then:
    PYTHONPATH=build/pylibs python tools/analyze_playthrough.py
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import common

DEFAULT_ROM = common.ROOT / 'KirbyDreamLand_CHS-Monado.gb'
DEFAULT_OUT = common.ROOT / 'build' / 'playthrough'


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rom', type=Path, default=DEFAULT_ROM)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--interval', type=int, default=30,
                        help='capture every N frames (default 30 = 0.5 s)')
    parser.add_argument('--scale', type=int, default=3, help='window scale')
    parser.add_argument('--window', default='SDL2', help='PyBoy window backend')
    parser.add_argument('--max-frames', type=int, default=0,
                        help='stop after N frames (mainly for smoke tests)')
    args = parser.parse_args(argv)
    common.require(args.rom.is_file(), 'ROM not found: ' + str(args.rom))
    common.require(args.interval > 0, '--interval must be positive')
    try:
        from pyboy import PyBoy
        from pyboy.utils import WindowEvent
    except ImportError as exc:
        raise common.ProjectError(
            'PyBoy is required; install it into the gitignored build/pylibs and '
            'run with PYTHONPATH=build/pylibs') from exc

    event_names = {getattr(WindowEvent, name): name for name in dir(WindowEvent)
                   if name.isupper() and isinstance(getattr(WindowEvent, name), int)}

    class RecordingPyBoy(PyBoy):
        """PyBoy that logs button events for deterministic replay."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.input_log = []

        def send_input(self, event, *args, **kwargs):
            name = event_names.get(event, str(event))
            if name.startswith(('PRESS_BUTTON', 'RELEASE_BUTTON',
                                'PRESS_ARROW', 'RELEASE_ARROW')):
                self.input_log.append({'frame': int(self.frame_count), 'event': name})
            return super().send_input(event, *args, **kwargs)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob('cap_*'):
        stale.unlink()
    manifest = {
        'format_version': 1,
        'rom': str(args.rom),
        'rom_sha256': _sha256(args.rom),
        'interval_frames': args.interval,
        'window': args.window,
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'captures': [],
    }
    print('PLAY_CAPTURE=START OUT=%s INTERVAL=%d' % (out, args.interval))
    print('controls: arrows=D-pad A=A S=B Return=Start Backspace=Select Esc=quit')
    pyboy = RecordingPyBoy(str(args.rom), window=args.window, scale=args.scale,
                           sound_emulated=False)
    capture_count = 0
    try:
        while True:
            if not pyboy.tick():
                break
            if args.max_frames and pyboy.frame_count >= args.max_frames:
                break
            if pyboy.frame_count % args.interval:
                continue
            stem = 'cap_%06d' % pyboy.frame_count
            vram = bytes(pyboy.memory[0x8000:0xA000])
            oam = bytes(pyboy.memory[0xFE00:0xFEA0])
            meta = {
                'frame': int(pyboy.frame_count),
                'lcdc': int(pyboy.memory[0xFF40]),
                'scy': int(pyboy.memory[0xFF42]),
                'scx': int(pyboy.memory[0xFF43]),
                'wy': int(pyboy.memory[0xFF4A]),
                'wx': int(pyboy.memory[0xFF4B]),
                'bg_map_base': 0x9C00 if pyboy.memory[0xFF40] & 0x08 else 0x9800,
                'vram': stem + '.vram',
                'oam': stem + '.oam',
                'screen': stem + '.png',
            }
            (out / meta['vram']).write_bytes(vram)
            (out / meta['oam']).write_bytes(oam)
            pyboy.screen.image.save(out / meta['screen'])
            (out / (stem + '.json')).write_text(json.dumps(meta, indent=1) + '\n')
            manifest['captures'].append(meta)
            capture_count += 1
            if capture_count % 20 == 0:
                print('PLAY_CAPTURE=PROGRESS FRAMES=%d CAPTURES=%d'
                      % (pyboy.frame_count, capture_count))
    except KeyboardInterrupt:
        print('PLAY_CAPTURE=INTERRUPTED')
    finally:
        manifest['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        manifest['frames'] = int(pyboy.frame_count)
        manifest['capture_count'] = len(manifest['captures'])
        manifest['inputs'] = pyboy.input_log
        manifest['input_count'] = len(pyboy.input_log)
        (out / 'index.json').write_text(json.dumps(manifest, indent=1) + '\n')
        try:
            pyboy.stop(save=False)
        except Exception:
            pass
    print('PLAY_CAPTURE=PASS FRAMES=%d CAPTURES=%d INPUTS=%d OUT=%s'
          % (manifest['frames'], manifest['capture_count'],
             manifest['input_count'], out))
    print('next: PYTHONPATH=build/pylibs python tools/analyze_playthrough.py')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, common.ProjectError) as exc:
        print('PLAY_CAPTURE=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
