# SPDX-License-Identifier: MIT
"""Baseline+overlay page layer for tilemap and sheet pages.

A page can be stored in two ways:

``page``
    A full-page PNG under ``source/pages/`` (bundle pages: stage intros, title,
    configuration, sound test, game over, continue).

``edit``
    A small edit overlay under ``source/edits/``: the baseline page is rebuilt
    from the user-provided Rev1 ROM (original tileset + map, plus a few pinned
    external tiles), and only the changed 8x8 cells are stored, in a tiny
    4-colour atlas PNG plus a JSON index.  This keeps original-ROM artwork out
    of the repository and makes page edits explicit.

``render`` writes reconstructed pages to ``build/pages/`` (gitignored);
``check`` verifies baseline+overlay equals the page rendered from
``source/graphics``; ``extract`` folds an edited ``build/pages/<id>.png`` back
into its edit overlay after ``tools/pages.py retile`` has updated the graphics.
"""
import argparse
import json
from pathlib import Path
import sys

import common
import graphics_png as gp
import hal_codec
import page_image

EDITS_DIR = 'source/edits'
PAGES_BUILD = common.ROOT / 'build' / 'pages'


def _index(manifest):
    return {entry['id']: entry for entry in manifest['resources']}


def edit_entries(manifest):
    return [entry for entry in manifest['resources'] if entry.get('edit')]


def page_entries(manifest):
    return [entry for entry in manifest['resources'] if entry.get('page')]


def edit_path(entry):
    return common.ROOT / entry['edit']


def load_edit(entry):
    data = json.loads(edit_path(entry).read_text())
    common.require(data.get('id') == entry['id'], 'edit id mismatch for ' + entry['id'])
    common.require(data.get('page_size') and len(data['page_size']) == 2,
                   'edit page_size missing for ' + entry['id'])
    return data


def old_location(manifest, label):
    """Rev1 (bank, cpu) of a resource label, from the manifest patch preimages."""
    bank = addr = None
    for patch in manifest['patches']:
        for field in patch['field'].split(';'):
            base = field.replace('_load_pointer', '').replace('_bundle_load', '') \
                        .replace('_map_load', '').replace('_load', '').replace('_pointer', '')
            if base == label or field.startswith(label + '_'):
                expect = bytes.fromhex(patch['expected_hex'])
                replace = bytes.fromhex(patch['replacement_hex'])
                if len(expect) == 2 and len(replace) == 2:
                    addr = int.from_bytes(expect, 'little')
                elif len(expect) == 1 and len(replace) == 1 and expect[0] < 0x20:
                    bank = expect[0]
    if bank is not None and addr is None:
        addr = 0x4000
    return bank, addr


def _decode_at(base, bank, cpu):
    offset = bank * 0x4000 + (cpu - 0x4000) if bank else cpu
    return hal_codec.decode(base, offset, 65536)[0]


def _decode_file_offset(base, offset):
    return hal_codec.decode(base, offset, 65536)[0]


def _blocks(data):
    return [data[i * 16:(i + 1) * 16] for i in range(len(data) // 16)]


def baseline_blocks(entry, edit, base):
    """Rebuild the baseline page cells from Rev1 using pinned provenance."""
    width, height = edit['page_size']
    cells = width * height
    spec = edit['baseline']
    tiles = spec.get('tiles')
    common.require(tiles, 'edit has no baseline tiles for ' + entry['id'])
    blocks = _blocks(_decode_at(base, tiles['bank'], int(tiles['cpu'], 16)))
    common.require(len(blocks) >= tiles['tiles'],
                   'baseline tileset is shorter than declared for ' + entry['id'])
    blocks = blocks[:tiles['tiles']]
    if edit['kind'] == 'sheet':
        return (blocks + [bytes(16)] * cells)[:cells]
    map_spec = spec.get('map')
    common.require(map_spec, 'tilemap edit has no baseline map for ' + entry['id'])
    map_bytes = _decode_at(base, map_spec['bank'], int(map_spec['cpu'], 16))[:map_spec['cells']]
    external = {}
    for key, value in spec.get('external', {}).items():
        index = int(key)
        if isinstance(value, str):  # legacy hex form, migrated away in v0.5.1
            external[index] = bytes.fromhex(value)
        else:
            data = _decode_file_offset(base, int(value['file_offset'], 16))
            tile = value['tile']
            external[index] = data[tile * 16:(tile + 1) * 16]
    addressing = spec.get('addressing', 'linear')
    out = []
    for index in map_bytes:
        number = index + 256 if addressing == '0x8800' and index < 128 else index
        if number < len(blocks):
            out.append(blocks[number])
        elif index in external:
            out.append(external[index])
        else:
            out.append(None)
    while len(out) < cells:
        out.append(None)
    return out


def atlas_blocks(edit, entry):
    path = common.ROOT / edit['overlay_atlas']
    data = path.read_bytes()
    per_row = 16
    tiles = gp.png_to_tiles(data, per_row, len(edit['cells']))
    return _blocks(tiles)


def render_blocks(entry, edit, base):
    baseline = baseline_blocks(entry, edit, base)
    overlay = atlas_blocks(edit, entry)
    common.require(len(overlay) == len(edit['cells']),
                   'overlay atlas tile count mismatch for ' + entry['id'])
    cells = list(baseline)
    for index, block in zip(edit['cells'], overlay):
        common.require(0 <= index < len(cells), 'overlay cell out of range for ' + entry['id'])
        cells[index] = block
    for index, block in enumerate(cells):
        common.require(block is not None,
                       'baseline cell %d unresolved for %s' % (index, entry['id']))
    return cells


def render_png(entry, edit, base):
    width, height = edit['page_size']
    cells = render_blocks(entry, edit, base)
    shades = bytearray()
    for cy in range(height):
        for row in range(8):
            for cx in range(width):
                shades.extend(_row_shades(cells[cy * width + cx], row))
    return gp.shades_to_png(width * 8, height * 8, bytes(shades))


def _row_shades(block, row):
    """Return the 8 shade values of one row of a 2bpp tile block."""
    lo = block[row * 2] if row * 2 < 16 else 0
    hi = block[row * 2 + 1] if row * 2 + 1 < 16 else 0
    out = []
    for bit in range(7, -1, -1):
        value = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
        out.append((0, 1, 2, 3)[value])
    return out


def graphics_page_png(entry, by_id):
    """Render the page from the tracked source/graphics PNGs."""
    png = entry['png']
    if entry.get('bundle'):
        bundle = entry['bundle']
        map_spec = {'mode': gp.TILEMAP_MODE, 'width': bundle['width'],
                    'height': bundle['height'], 'addressing': bundle['addressing']}
        tiles = gp.load_resource(common.ROOT / entry['source'], png)
        tilemap = gp.load_resource(common.ROOT / bundle['map_png'], map_spec)
        return page_image.page_png(tiles, tilemap, bundle['width'], bundle['height'],
                                   bundle['addressing'], True)
    if entry.get('page_kind') == 'sheet':
        tiles = gp.load_resource(common.ROOT / entry['source'], png)
        return gp.tiles_to_png(tiles, png['tiles_per_row'])
    tileset = by_id[png['tileset']]
    tiles = gp.load_resource(common.ROOT / tileset['source'], tileset['png'])
    tilemap = gp.load_resource(common.ROOT / entry['source'], png)
    return page_image.page_png(tiles, tilemap, png['width'], png['height'],
                               png['addressing'], False)


def check(manifest, base, verbose=False):
    by_id = _index(manifest)
    entries = edit_entries(manifest)
    common.require(entries, 'no edit-backed pages in the manifest')
    stale = []
    for entry in entries:
        edit = load_edit(entry)
        got = render_png(entry, edit, base)
        want = graphics_page_png(entry, by_id)
        if got != want:
            stale.append(entry['id'])
    common.require(not stale, 'edit pages are stale: ' + ', '.join(stale))
    print('PAGE_EDITS=PASS PAGES=%d' % len(entries))
    return 0


def render(manifest, base, check_only=False):
    by_id = _index(manifest)
    PAGES_BUILD.mkdir(parents=True, exist_ok=True)
    stale = []
    for entry in edit_entries(manifest):
        edit = load_edit(entry)
        payload = render_png(entry, edit, base)
        target = PAGES_BUILD / (entry['id'] + '.png')
        if check_only:
            want = graphics_page_png(entry, by_id)
            if payload != want:
                stale.append(entry['id'])
        else:
            target.write_bytes(payload)
    if check_only:
        common.require(not stale, 'edit pages are stale: ' + ', '.join(stale))
        print('PAGE_EDITS=PASS PAGES=%d' % len(edit_entries(manifest)))
    else:
        print('PAGE_EDITS=RENDERED=%d DIR=%s' % (len(edit_entries(manifest)), PAGES_BUILD))
    return 0


def extract(entry, page_bytes, base):
    """Fold an edited page PNG back into its edit overlay and atlas."""
    edit = load_edit(entry)
    width, height = edit['page_size']
    image_width, image_height, shades = gp.png_to_shades(page_bytes)
    common.require((image_width, image_height) == (width * 8, height * 8),
                   'edited page dimensions changed for ' + entry['id'])
    current = [page_image._block_from_page(shades, width * 8, cx, cy)
               for cy in range(height) for cx in range(width)]
    baseline = baseline_blocks(entry, edit, base)
    cells = [i for i, (old, new) in enumerate(zip(baseline, current))
             if old is None or old != new]
    blocks = [current[i] for i in cells]
    common.require(blocks, 'edited page has no changes for ' + entry['id'])
    atlas = gp.tiles_to_png(b''.join(blocks), 16)
    atlas_rel = '%s/%s_cells.png' % (EDITS_DIR, entry['id'])
    (common.ROOT / atlas_rel).write_bytes(atlas)
    edit['cells'] = cells
    edit['overlay_atlas'] = atlas_rel
    edit_path(entry).write_text(json.dumps(edit, ensure_ascii=False, indent=1) + '\n')
    print('EXTRACT=PASS PAGE=%s CELLS=%d' % (entry['id'], len(cells)))
    return cells


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('render', 'check', 'extract'))
    parser.add_argument('--base', type=Path, default=common.ROOT / 'baserom.gb')
    parser.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    parser.add_argument('--page', type=Path, help='edited page PNG for extract')
    args = parser.parse_args(argv)
    common.require(args.base.is_file(), 'baserom.gb is required for the page-edit layer')
    manifest = common.load_manifest(args.manifest)
    base = args.base.read_bytes()
    common.validate_input(base, manifest)
    if args.command == 'extract':
        common.require(args.page, 'extract needs --page build/pages/<id>.png')
        page_bytes = args.page.read_bytes()
        entry = next((e for e in edit_entries(manifest)
                      if e['id'] == args.page.stem), None)
        common.require(entry is not None, 'page is not edit-backed: ' + args.page.name)
        extract(entry, page_bytes, base)
        return 0
    return render(manifest, base, check_only=(args.command == 'check'))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print('PAGE_EDITS=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
