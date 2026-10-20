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
import hashlib
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
    # The two clear-screen hint pages: their tilesets live in a separate
    # resource, named by the page's own `png.tileset` field.
    'hint_normal': 'rom_055050',
    'hint_extra': 'rom_056110',
    # Gallery pages.  Each is a tilemap resource whose tileset is the paired
    # `ending_*` bundle; `png.tileset` names it.
    'gallery_01': 'rom_048462', 'gallery_02': 'rom_04c4f4',
    'gallery_03': 'rom_0742b3', 'gallery_04': 'rom_04caf2',
    'gallery_05': 'rom_0496d4', 'gallery_06': 'rom_049bf8',
    'gallery_07': 'rom_04cd98', 'gallery_08': 'rom_04a3a1',
    'gallery_09': 'rom_04d0bb', 'gallery_10': 'rom_04ab1b',
    'gallery_11': 'rom_04b4db', 'gallery_12': 'rom_04d586',
    'gallery_13': 'rom_04b943', 'gallery_14': 'rom_04d918',
    # hud_* and ending_sign are sprite sheets, not laid-out pictures: they have no
    # tilemap of their own, so there is nothing to render as a page.  They are
    # covered by the capture/VRAM comparison instead.
}

VIEWPORT = (160, 144)


def page_entry(manifest, page_id):
    for entry in manifest['resources']:
        if entry['id'] == page_id:
            return entry
    raise ValueError('unknown page ' + page_id)


BUNDLE_MAP_WIDTH = 32
BUNDLE_MAP_HEIGHT = 18


def spec_of(entry):
    """The manifest's `png` block, which says how the resource is laid out."""
    return entry['png']


def kind_of(entry):
    return entry.get('page_kind') or 'tiles'


def decode_raw(rom, entry):
    raw, _packed = hal_codec.decode(rom[entry['offset']:entry['offset'] + entry['packed_size']])
    return raw[:entry['decoded_size']]


def bundle_parts(rom, entry):
    """(tiles, map, width, height, addressing) for a bundle page.

    A bundle is self-contained: decoded tiles first, then a tilemap indexing them
    in the resource's own index space.  The map is not always one screen high --
    stage 5 is 32x30 because its artwork scrolls -- so the height comes from the
    resource rather than a fixed 18.
    """
    raw = decode_raw(rom, entry)
    tiles = spec_of(entry)['tile_count'] * 16
    tilemap = raw[tiles:]
    if len(tilemap) % BUNDLE_MAP_WIDTH:
        raise ValueError('%s: %d map bytes is not a whole number of %d-wide rows'
                         % (entry['id'], len(tilemap), BUNDLE_MAP_WIDTH))
    return (raw[:tiles], tilemap, BUNDLE_MAP_WIDTH,
            bundle_map_height(entry), 'linear')


def bundle_map_height(entry):
    """Rows in a bundle page's tilemap; stage 5 is taller than one screen."""
    tilemap = entry['decoded_size'] - spec_of(entry)['tile_count'] * 16
    return tilemap // BUNDLE_MAP_WIDTH


def tilemap_parts(rom, manifest, entry):
    """(tiles, map, width, height, addressing) for a tilemap page.

    The map is this resource; the tiles come from the resource named by
    `png.tileset`.  Rendering one without the other produces noise, which is the
    mistake this split exists to prevent.
    """
    spec = spec_of(entry)
    tileset = page_entry(manifest, spec['tileset'])
    return (decode_raw(rom, tileset), decode_raw(rom, entry),
            spec['width'], spec['height'], spec['addressing'])


def resource_view(rom, entry, manifest):
    """Picture built only from decoded resource bytes, no emulator state."""
    kind = kind_of(entry)
    if kind == 'bundle':
        args = bundle_parts(rom, entry)
    elif kind in ('tilemap', 'None'):
        args = tilemap_parts(rom, manifest, entry)
    else:
        raise ValueError('resource view needs a tilemap or bundle page, got %s for %s'
                         % (kind, entry['id']))
    return page_image.page_png(*args, placeholders=True)


def capture_matches_rom(capture_dir, rom_sha256):
    """True when the capture was taken from the ROM currently built.

    A capture carries the VRAM of the ROM it was taken from.  Mixing old VRAM
    with the current map does not show the current screen, it shows the two
    revisions spliced together, so a stale capture must not be used as the
    screen view.
    """
    path = capture_dir / 'state.json'
    if not path.is_file():
        return False
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, TypeError):
        return False
    return state.get('rom_sha256') == rom_sha256


def screen_view(capture_dir, entry):
    """Picture from live VRAM: baseline tiles included, hardware addressing.

    Returns None when the capture lacks the inputs this reconstruction needs.
    """
    vram_path = capture_dir / 'vram.bin'
    bgmap_path = capture_dir / 'bgmap.bin'
    if not vram_path.is_file() or not bgmap_path.is_file():
        return None
    if kind_of(entry) in ('tilemap', 'None'):
        spec = spec_of(entry)
        width, height = spec['width'], spec['height']
        addressing = spec['addressing']
    else:
        width = BUNDLE_MAP_WIDTH
        height = bundle_map_height(entry)
        addressing = '0x%04X' % LCDC_8800
    vram = vram_path.read_bytes()
    live_map = bgmap_path.read_bytes()[:width * height]
    return page_image.page_png(vram, live_map, width, height, addressing, True)



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
    rom_sha256 = hashlib.sha256(rom).hexdigest()
    manifest = common.load_manifest()
    rows = []
    for screen, page_id in sorted(SCREENS.items()):
        entry = page_entry(manifest, page_id)
        capture_dir = (Path(captures) / 'captures' / screen) if captures else None
        png = None
        view = 'resource'
        scx = scy = 0
        if (capture_dir is not None and capture_dir.is_dir()
                and capture_matches_rom(capture_dir, rom_sha256)):
            png = screen_view(capture_dir, entry)
            if png is not None:
                view = 'screen'
                scx, scy = scroll_from_state(capture_dir)
        if png is None:
            png = resource_view(rom, entry, manifest)
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
