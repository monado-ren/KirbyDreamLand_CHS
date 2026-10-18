# SPDX-License-Identifier: MIT
"""Render, check and retile the human-readable page PNG layer.

A page is one of two kinds:

``tilemap``
    A resource that is a pure 32x32 background map, paired with a separate
    tileset resource (the gallery and ending-hint pages).

``bundle``
    A single resource holding a tile block followed by a background map, which
    the game copies to VRAM in one step (stage intros, title, configuration,
    sound test, game over, continue).  Cells whose map byte points outside the
    bundle (original-ROM tiles) are drawn as a placeholder and stay read-only.

``render`` writes ``source/pages/<id>.png``; ``check`` verifies the tracked
pages are in sync (used by tests); ``retile`` splits an edited page back into
its PNG sources and refreshes the manifest, then ``tools/repack.py`` records the
new hashes.
"""
import argparse
import json
from pathlib import Path
import sys

import allocation
import common
import graphics_png as gp
import hal_codec
import page_image


def _index(manifest):
    return {entry['id']: entry for entry in manifest['resources']}


def _pages(manifest):
    return [entry for entry in manifest['resources'] if entry.get('page')]


def _layout(by_id, entry):
    """Return (kind, tileset_entry, tiles_png, map_png, tiles_spec, map_spec, placeholders)."""
    png = entry['png']
    kind = entry.get('page_kind')
    if kind == 'tilemap':
        tileset = by_id[png['tileset']]
        return 'tilemap', tileset, tileset['source'], entry['source'], tileset['png'], png, False
    if kind == 'bundle':
        bundle = entry['bundle']
        map_spec = {'mode': gp.TILEMAP_MODE, 'width': bundle['width'],
                    'height': bundle['height'], 'addressing': bundle['addressing']}
        return 'bundle', entry, entry['source'], bundle['map_png'], png, map_spec, True
    common.require(kind == 'sheet', 'Unknown page kind for ' + entry['id'])
    return 'sheet', entry, entry['source'], None, png, None, False


def _render_png(layout):
    kind, _tileset, tiles_png, map_png, tiles_spec, map_spec, placeholders = layout
    tiles = gp.load_resource(common.ROOT / tiles_png, tiles_spec)
    if kind == 'sheet':
        return gp.tiles_to_png(tiles, tiles_spec['tiles_per_row'])
    tilemap = gp.load_resource(common.ROOT / map_png, map_spec)
    return page_image.page_png(tiles, tilemap, map_spec['width'], map_spec['height'],
                               map_spec['addressing'], placeholders)


def render(manifest, check_only=False):
    by_id = _index(manifest)
    pages = _pages(manifest)
    mismatched = []
    for entry in pages:
        payload = _render_png(_layout(by_id, entry))
        target = common.ROOT / entry['page']
        if check_only:
            if not target.is_file() or target.read_bytes() != payload:
                mismatched.append(entry['page'])
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    if check_only:
        common.require(not mismatched,
                       'Page previews are stale; run tools/pages.py render: '
                       + ', '.join(mismatched))
        print('PAGES=PASS PREVIEWS=' + str(len(pages)))
    else:
        print('PAGES=PASS RENDERED=' + str(len(pages)))
    return 0


def _write_candidate(layout, entry, tiles, tilemap, added, strategy):
    kind, tileset, tiles_png, map_png, tiles_spec, map_spec, _ph = layout
    if kind == 'bundle':
        entry['png']['tile_count'] = len(tiles) // 16
        entry['decoded_size'] = len(tiles) + len(tilemap)
        gp.write_resource(common.ROOT / tiles_png, tiles, entry['png'])
        gp.write_resource(common.ROOT / map_png, tilemap, map_spec)
        page_payload = page_image.page_png(tiles, tilemap, map_spec['width'],
                                           map_spec['height'], map_spec['addressing'], True)
        (common.ROOT / entry['page']).write_bytes(page_payload)
        print('RETILE=PASS PAGE=' + entry['id'] + ' KIND=bundle TILES='
              + str(len(tiles) // 16) + ' ADDED=' + str(len(added))
              + ' STRATEGY=' + strategy)
    else:
        gp.write_resource(common.ROOT / tiles_png, tiles, tiles_spec)
        gp.write_resource(common.ROOT / map_png, tilemap, map_spec)
        page_payload = page_image.page_png(tiles, tilemap, map_spec['width'],
                                           map_spec['height'], map_spec['addressing'], False)
        (common.ROOT / entry['page']).write_bytes(page_payload)
        print('RETILE=PASS PAGE=' + entry['id'] + ' KIND=tilemap TILES='
              + str(len(tiles) // 16) + ' ADDED=' + str(len(added))
              + ' STRATEGY=' + strategy)


def retile(manifest, manifest_path, page_path):
    page_path = page_path.resolve()
    page_rel = page_path.relative_to(common.ROOT.resolve()).as_posix()
    common.validate_page_path(page_rel)
    by_id = _index(manifest)
    entry = next((item for item in _pages(manifest) if item['page'] == page_rel), None)
    common.require(entry is not None, 'Page is not listed in the manifest: ' + page_rel)
    layout = _layout(by_id, entry)
    kind, tileset = layout[0], layout[1]
    tiles_png, map_png, tiles_spec, map_spec = layout[2], layout[3], layout[4], layout[5]
    placeholders = layout[6]
    page_bytes = page_path.read_bytes()
    if kind == 'sheet':
        tiles = gp.png_to_tiles(page_bytes, tiles_spec['tiles_per_row'],
                                tiles_spec['tile_count'])
        packed = len(hal_codec.pack(tiles))
        if packed > entry['capacity']:
            allocation.relocate(manifest, entry, max(packed, 16))
        gp.write_resource(common.ROOT / tiles_png, tiles, tiles_spec)
        (common.ROOT / entry['page']).write_bytes(
            gp.tiles_to_png(tiles, tiles_spec['tiles_per_row']))
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                 encoding='utf-8')
        print('RETILE=PASS PAGE=' + entry['id'] + ' KIND=sheet TILES='
              + str(len(tiles) // 16))
        print('NEXT=python tools/repack.py --version <new-version>')
        return 0
    shades = page_image.decode_page(page_bytes, map_spec['width'], map_spec['height'])
    tile_bytes = gp.load_resource(common.ROOT / tiles_png, tiles_spec)
    map_bytes = gp.load_resource(common.ROOT / map_png, map_spec)

    max_tiles = tiles_spec['tile_count']
    candidates = []
    try:
        tiles, tilemap, added = page_image.retile(page_bytes, common.ROOT / tiles_png,
                                                  common.ROOT / map_png, tiles_spec,
                                                  map_spec, placeholders)
        candidates.append(('preserve', tiles, tilemap, added))
    except common.ProjectError:
        pass
    for name, sort_blocks in (('compact-first-use', False), ('compact-sorted', True)):
        try:
            compact = page_image._compact(shades, map_bytes, map_spec['width'],
                                          map_spec['height'], map_spec['addressing'],
                                          sort_blocks=sort_blocks,
                                          placeholders=placeholders, max_tiles=max_tiles)
            candidates.append((name, compact[0], compact[1], []))
        except common.ProjectError:
            pass
    common.require(candidates, 'Edited page cannot be encoded within this resource layout')

    def choose(capacity):
        for name, tiles_candidate, map_candidate, extra in candidates:
            packed = len(hal_codec.pack(tiles_candidate + map_candidate))
            if packed <= capacity:
                return name, tiles_candidate, map_candidate, extra, packed
        smallest = min(candidates, key=lambda item: len(hal_codec.pack(item[1] + item[2])))
        return (smallest[0] + '+relocated', smallest[1], smallest[2], smallest[3],
                len(hal_codec.pack(smallest[1] + smallest[2])))

    if kind == 'bundle':
        name, tiles, tilemap, added, packed = choose(entry['capacity'])
        if packed > entry['capacity']:
            allocation.relocate(manifest, entry, max(packed, 16))
        _write_candidate(layout, entry, tiles, tilemap, added, name)
    else:
        tileset_capacity = tileset['capacity']
        map_capacity = entry['capacity']
        name, tiles, tilemap, added = 'preserve', tiles, tilemap, added
        tiles_packed = len(hal_codec.pack(tiles))
        map_packed = len(hal_codec.pack(tilemap))
        if tiles_packed > tileset_capacity or map_packed > map_capacity:
            best = None
            for candidate in candidates:
                c_name, c_tiles, c_map, c_added = candidate
                tp = len(hal_codec.pack(c_tiles)); mp = len(hal_codec.pack(c_map))
                score = (max(0, tp - tileset_capacity) + max(0, mp - map_capacity), tp + mp)
                if best is None or score < best[0]:
                    best = (score, c_name, c_tiles, c_map, c_added)
            _score, name, tiles, tilemap, added = best
            if len(hal_codec.pack(tiles)) > tileset_capacity:
                allocation.relocate(manifest, tileset, max(len(hal_codec.pack(tiles)), 16))
            if len(hal_codec.pack(tilemap)) > map_capacity:
                allocation.relocate(manifest, entry, max(len(hal_codec.pack(tilemap)), 16))
        _write_candidate(layout, entry, tiles, tilemap, added, name)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8')
    print('NEXT=python tools/repack.py --version <new-version>')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    sub = parser.add_subparsers(dest='command', required=True)
    render_parser = sub.add_parser('render', help='write page previews from tracked sources')
    render_parser.add_argument('--check', action='store_true',
                               help='only verify that tracked pages are up to date')
    retile_parser = sub.add_parser('retile', help='split an edited page back into resources')
    retile_parser.add_argument('page', type=Path)
    args = parser.parse_args()
    manifest = common.load_manifest(args.manifest)
    if args.command == 'render':
        return render(manifest, args.check)
    return retile(manifest, args.manifest, args.page)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print('PAGES=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
