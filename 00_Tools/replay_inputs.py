# SPDX-License-Identifier: MIT
"""Deterministically replay a recorded PyBoy input log (TAS-style).

``00_Tools/play_capture.py`` also records the exact button events; this script
boots a fresh headless PyBoy, replays those events frame by frame, captures the
requested frames and (optionally) verifies that the live VRAM hashes match the
original playthrough captures at the same frame.  Useful for re-capturing short
screens at every frame or proving that the recording is deterministic.

Usage:
    PYTHONPATH=build/pylibs python 00_Tools/replay_inputs.py --verify
    PYTHONPATH=build/pylibs python 00_Tools/replay_inputs.py --capture-every 1 --out build/replay
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import common

DEFAULT_DIR = common.ROOT / 'build' / 'playthrough'
DEFAULT_OUT = common.ROOT / 'build' / 'replay'


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _button_name(event):
    return event.rsplit('_', 1)[-1].lower()


def replay(capture_dir, out, capture_every=0, verify=False, limit_frames=0):
    try:
        from pyboy import PyBoy
    except ImportError as exc:
        raise common.ProjectError(
            'PyBoy is required; install it into the gitignored build/pylibs and '
            'run with PYTHONPATH=build/pylibs') from exc
    index = _load(capture_dir / 'index.json')
    common.require('inputs' in index, 'capture directory has no input log')
    original = {meta['frame']: meta for meta in index['captures']}
    if capture_every:
        capture_frames = set(range(0, index.get('frames', 0) + 1, capture_every))
    else:
        capture_frames = set(original)
    end_frame = limit_frames or (max(index.get('frames', 0),
                                     max((item['frame'] for item in index['inputs']),
                                         default=0)) + 1)
    events = {}
    for item in index['inputs']:
        events.setdefault(item['frame'], []).append(item['event'])
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob('cap_*'):
        stale.unlink()
    manifest = {
        'format_version': 1,
        'rom_sha256': index.get('rom_sha256'),
        'interval_frames': capture_every or index.get('interval_frames', 0),
        'replay_of': str(capture_dir),
        'captures': [],
    }
    pyboy = PyBoy(str(_rom_path(index)), window='null', sound_emulated=False)
    sync_ok = True
    mismatch_frame = None
    try:
        while pyboy.frame_count < end_frame:
            for event in events.get(int(pyboy.frame_count), []):
                button = _button_name(event)
                if event.startswith('PRESS_'):
                    pyboy.button_press(button)
                else:
                    pyboy.button_release(button)
            pyboy.tick()
            frame = int(pyboy.frame_count)
            if frame not in capture_frames:
                continue
            stem = 'cap_%06d' % frame
            vram = bytes(pyboy.memory[0x8000:0xA000])
            oam = bytes(pyboy.memory[0xFE00:0xFEA0])
            meta = {
                'frame': frame,
                'lcdc': int(pyboy.memory[0xFF40]),
                'scy': int(pyboy.memory[0xFF42]),
                'scx': int(pyboy.memory[0xFF43]),
                'wy': int(pyboy.memory[0xFF4A]),
                'wx': int(pyboy.memory[0xFF4B]),
                'bg_map_base': 0x9C00 if pyboy.memory[0xFF40] & 0x08 else 0x9800,
                'vram': stem + '.vram',
                'oam': stem + '.oam',
                'screen': stem + '.png',
                'vram_sha256': _sha256(vram),
            }
            (out / meta['vram']).write_bytes(vram)
            (out / meta['oam']).write_bytes(oam)
            pyboy.screen.image.save(out / meta['screen'])
            (out / (stem + '.json')).write_text(json.dumps(meta, indent=1) + '\n')
            manifest['captures'].append(meta)
            if verify and frame in original:
                expected = (capture_dir / original[frame]['vram']).read_bytes()
                if _sha256(expected) != meta['vram_sha256']:
                    sync_ok = False
                    if mismatch_frame is None:
                        mismatch_frame = frame
    finally:
        manifest['frames'] = int(pyboy.frame_count)
        manifest['capture_count'] = len(manifest['captures'])
        manifest['sync_ok'] = sync_ok
        manifest['first_mismatch_frame'] = mismatch_frame
        (out / 'index.json').write_text(json.dumps(manifest, indent=1) + '\n')
        try:
            pyboy.stop(save=False)
        except Exception:
            pass
    return manifest


def _rom_path(index):
    rom = Path(index.get('rom', ''))
    if not rom.is_absolute():
        rom = common.ROOT / rom
    common.require(rom.is_file(), 'ROM not found: ' + str(rom))
    return rom


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--capture-dir', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--capture-every', type=int, default=0,
                        help='capture every N frames (0 = same frames as the original)')
    parser.add_argument('--limit-frames', type=int, default=0)
    parser.add_argument('--verify', action='store_true',
                        help='compare replayed VRAM hashes with the original captures')
    args = parser.parse_args(argv)
    manifest = replay(args.capture_dir, args.out, capture_every=args.capture_every,
                      verify=args.verify, limit_frames=args.limit_frames)
    print('REPLAY=%s FRAMES=%d CAPTURES=%d SYNC=%s'
          % ('PASS' if manifest.get('sync_ok', True) else 'FAIL',
             manifest['frames'], manifest['capture_count'],
             'YES' if manifest.get('sync_ok', True) else
             'NO@%d' % manifest.get('first_mismatch_frame')))
    return 0 if manifest.get('sync_ok', True) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            common.ProjectError) as exc:
        print('REPLAY=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
