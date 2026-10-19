# SPDX-License-Identifier: MIT
"""Render each page the way the screen actually shows it, not just as a resource.

There are two different pictures for the same page, and confusing them is easy:

*resource view*
    `page_png(tiles, map)` over one resource.  This is what `03_Image/pages/`
    stores, and `linear` addressing keeps it self-consistent: a map code indexes
    the resource's own tile table.  It is *not* what a player sees, because the
    live BG map also references baseline VRAM tiles the resource does not carry.

*screen view*
    the same map bytes rendered against the *live VRAM* with the hardware's real
    addressing mode.  Every captured screen runs with LCDC=0xE7 (bit 4 clear), so
    the hardware uses 0x8800 addressing, which is why `linear` on one resource
    alone cannot reconstruct the picture.

This tool produces the screen view when a PyBoy capture is available, and falls
back to the resource view otherwise, labelling which one it produced.  Captures
come from `00_Tools/capture_pages.py`; nothing here touches the released ROM.

Usage:
    PYTHONPATH=build/pylibs python 00_Tools/render_screens.py \
        --captures build/visual_regression/capture_test \
        --out build/screens

Exit status is 0 when every requested page rendered (either mode).
"""
import argparse
import json
from pathlib import Path
import sys

import common
import graphics_png as gp
import hal_codec
import page_image

ROOT = common.ROOT

# The hardware's background addressing when LCDC bit 4 is clear.
LCDC_8800 = 0x8800

# screen directory -> page resource
SCREENS = {
    'title': 'rom_070000',
    'title_animation': 'rom_070000',
    'main_menu': 'rom_070000',
    'configuration': 'rom_05c000',
    'sound_test': 'rom_0438f6',
    'stage_1_intro': 'rom_06c000',
    'stage_2_intro': 'rom_06c70b',
    'stage_3_intro': 'rom_06cda8',
    'stage_4_intro': 'rom_06d490',
    'stage_5_intro': 'rom_06db85',
    'stage_5_intro_scrolled': 'rom_06db85',
    'game_over': 'rom_04454c',
    'continue': 'rom_044734',
}

VIEWPORT = (160, 144)


def page_entry(manifest, page_id):
    for entry in manifest['resources']:
        if entry['id'] == page_id:
            return entry
    raise ValueError('unknown page ' + page_id)


def decode_page(rom, entry):
    """Decoded stream of one page, split into (tiles, map)."""
    raw, _packed = hal_codec.decode(rom[entry['offset']:])
    bundle = entry['bundle']
    size = bundle['width'] * bundle['height']
    return raw[:len(raw) - size], raw[len(raw) - size:]


def resource_view(rom, entry):
    """Picture from the resource alone: the same bytes 03_Image/pages stores."""
    tiles, tilemap = decode_page(rom, entry)
    bundle = entry['bundle']
    return page_image.page_png(tiles, tilemap, bundle['width'], bundle['height'],
                               bundle['addressing'], True)


def screen_view(capture_dir, entry):
    """Picture from live VRAM: baseline tiles included, hardware addressing.

    Returns None when the capture lacks the inputs this reconstruction needs.
    """
    vram_path = capture_dir / 'vram.bin'
    bgmap_path = capture_dir / 'bgmap.bin'
    if not vram_path.is_file() or not bgmap_path.is_file():
        return None
    bundle = entry['bundle']
    width, height = bundle['width'], bundle['height']
    vram = vram_path.read_bytes()
    live_map = bgmap_path.read_bytes()[:width * height]
    return page_image.page_png(vram, live_map, width, height,
                               '0x%04X' % LCDC_8800, True)


def scroll_from_state(capture_dir):
    """SCX/SCY the emulator had when it took the screenshot."""
    path = capture_dir / 'state.json'
    if not path.is_file():
        return (0, 0)
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        return (int(state.get('SCX', 0)), int(state.get('SCY', 0)))
    except (ValueError, TypeError):
        return (0, 0)


def crop_to_viewport(png_bytes, scx, scy, size=VIEWPORT):
    """Cut the 160x144 window the LCD shows, honouring the scroll registers."""
    width, height = size
    from PIL import Image
    import io
    source = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    sw, sh = source.size
    window = Image.new('RGB', (width, height), (255, 255, 255))
    for y in range(height):
        for x in range(width):
            window.putpixel((x, y), source.getpixel(((x + scx) % sw, (y + scy) % sh)))
    return window


def collect(captures=None):
    rom = (ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()
    manifest = common.load_manifest()
    rows = []
    for screen, page_id in sorted(SCREENS.items()):
        entry = page_entry(manifest, page_id)
        capture_dir = (Path(captures) / 'captures' / screen) if captures else None
        png = None
        view = 'resource'
        scx = scy = 0
        if capture_dir is not None and capture_dir.is_dir():
            png = screen_view(capture_dir, entry)
            if png is not None:
                view = 'screen'
                scx, scy = scroll_from_state(capture_dir)
        if png is None:
            png = resource_view(rom, entry)
        rows.append({'screen': screen, 'page': page_id, 'view': view,
                     'png': png, 'scx': scx, 'scy': scy})
    return rows


def summarize(rows):
    return {
        'screens': len(rows),
        'screen_view': sum(1 for row in rows if row['view'] == 'screen'),
        'resource_view': sum(1 for row in rows if row['view'] == 'resource'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--captures', type=Path,
                        help='directory holding captures/<screen>/ from capture_pages.py')
    parser.add_argument('--out', type=Path, default=ROOT / 'build' / 'screens')
    parser.add_argument('--scale', type=int, default=2)
    args = parser.parse_args(argv)
    if not (ROOT / 'KirbyDreamLand_CHS-Monado.gb').is_file():
        print('RENDER=ERROR missing built ROM; run 00_Tools/build.py first',
              file=sys.stderr)
        return 1
    rows = collect(args.captures)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for row in rows:
        window = crop_to_viewport(row['png'], row['scx'], row['scy'])
        if args.scale > 1:
            from PIL import Image as _Image
            window = window.resize((window.width * args.scale, window.height * args.scale),
                                   _Image.NEAREST)
        path = out / (row['screen'] + '.png')
        window.save(path)
        index.append({'screen': row['screen'], 'page': row['page'],
                      'view': row['view'], 'scx': row['scx'], 'scy': row['scy'],
                      'file': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)})
        print('  %-24s %-8s page=%s' % (row['screen'], row['view'], row['page']))
    (out / 'index.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    stats = summarize(rows)
    print('RENDER=PASS SCREENS=%d SCREEN_VIEW=%d RESOURCE_VIEW=%d OUT=%s'
          % (stats['screens'], stats['screen_view'], stats['resource_view'], out))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('RENDER=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
