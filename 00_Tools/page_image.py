# SPDX-License-Identifier: MIT
"""Human-readable page layer: compose tilemaps into page PNGs and retile edits.

A page is a background-map resource rendered with its tileset at 8x8 pixels per
cell.  The full 32x32 map is rendered, including cells outside the 160x144
screen, so editing a page and splitting it back is lossless.

Tile addressing follows the Game Boy background map:

``linear``
    index 0-255 selects tile 0-255 (LCDC bit 4 clear, 0x8000 tile data).
``0x8800``
    index 0-127 selects tile 256-383; index 128-255 selects tile 128-255.

Retiling preserves every unchanged cell's original map byte, so an unedited
page always round-trips to byte-identical tileset and tilemap resources.
"""
from __future__ import annotations

from pathlib import Path

import common
import graphics_png as gp
import hal_codec

ADDRESSING = gp.TILEMAP_ADDRESSING

# A background cell whose map byte points outside this resource (for example the
# original game's 0x8000 tiles) cannot be reconstructed from the tracked data.
# Such cells are drawn as this fixed marker and are read-only when retiling.
PLACEHOLDER_BLOCK = bytes.fromhex(
    '0000' '0000' 'ffff' 'ffff' '0000' '0000' 'ffff' 'ffff')


def index_to_tile(index, addressing):
    if addressing == 'linear':
        return index
    return index + 256 if index < 128 else index


def tile_to_index(tile, addressing):
    """Return the map byte for a tile number, or None if it cannot be encoded."""
    if addressing == 'linear':
        return tile if 0 <= tile < 256 else None
    # 0x8800 addressing covers only VRAM tiles 128-383: indices 0-127 select
    # tiles 256-383 and indices 128-255 select tiles 128-255.
    if 256 <= tile <= 383:
        return tile - 256
    if 128 <= tile <= 255:
        return tile
    return None


def _tile_blocks(tile_bytes):
    return [tile_bytes[16 * index:16 * (index + 1)]
            for index in range(len(tile_bytes) // 16)]


def _block_from_page(shades, page_width, cell_x, cell_y):
    block = bytearray()
    for row in range(8):
        low = high = 0
        base = (cell_y * 8 + row) * page_width + cell_x * 8
        for column in range(8):
            shade = shades[base + column]
            if shade & 1:
                low |= 0x80 >> column
            if shade & 2:
                high |= 0x80 >> column
        block.append(low)
        block.append(high)
    return bytes(block)


def compose(tile_bytes, map_bytes, width, height, addressing='linear', placeholders=False):
    """Render a tilemap as a flat shade grid (row-major, 8 pixels per cell)."""
    require = common.require
    require(addressing in ADDRESSING, 'Unknown tile addressing: ' + repr(addressing))
    tiles = _tile_blocks(tile_bytes)
    require(len(map_bytes) == width * height, 'Tilemap size does not match its layout')
    page_width = width * 8
    shades = [0] * (page_width * height * 8)
    for cell_y in range(height):
        for cell_x in range(width):
            index = map_bytes[cell_y * width + cell_x]
            tile = index_to_tile(index, addressing)
            if not 0 <= tile < len(tiles):
                require(placeholders,
                        'Tilemap index ' + str(index) + ' points outside the tileset')
                block = PLACEHOLDER_BLOCK
            else:
                block = tiles[tile]
            for row in range(8):
                low, high = block[row * 2], block[row * 2 + 1]
                for column in range(8):
                    bit = 7 - column
                    shade = (((high >> bit) & 1) << 1) | ((low >> bit) & 1)
                    shades[(cell_y * 8 + row) * page_width + cell_x * 8 + column] = shade
    return shades



def _compact(shades, map_bytes, width, height, addressing, sort_blocks=False,
             placeholders=False, max_tiles=None):
    """Rebuild a tileset from the page cells that this resource owns.

    For 0x8800 addressing the first 128 tile slots are unreachable by the map and
    are kept blank, so usable tiles start at number 128.  Cells that reference
    tiles outside this resource keep their original map byte.
    """
    require = common.require
    page_width = width * 8
    pad = 128 if addressing == '0x8800' else 0
    cells = []
    external = []
    for cell_y in range(height):
        for cell_x in range(width):
            block = _block_from_page(shades, page_width, cell_x, cell_y)
            original = map_bytes[cell_y * width + cell_x]
            tile = index_to_tile(original, addressing)
            cells.append((block, original, tile))
    order = []
    seen = set()
    for block, original, tile in cells:
        if not 0 <= tile:
            continue
        if block not in seen:
            seen.add(block)
            order.append(block)
    if sort_blocks:
        order.sort()
    tiles = [bytes(16)] * pad + order
    if max_tiles is not None:
        require(len(tiles) <= max_tiles,
                'Compacted tileset needs ' + str(len(tiles)) + ' tiles but the resource '
                'only has ' + str(max_tiles) + ' slots')
    lookup = {block: pad + index for index, block in enumerate(order)}
    owned = []
    for block, original, tile in cells:
        if not 0 <= tile:
            require(placeholders,
                    'Tilemap index ' + str(original) + ' points outside the tileset')
            require(block == PLACEHOLDER_BLOCK,
                    'Cannot edit a cell that references original ROM tiles')
            owned.append(None)
        else:
            owned.append(block)
    tilemap = bytearray()
    for block, original, tile in cells:
        if not 0 <= tile:
            tilemap.append(original)
            continue
        encoded = tile_to_index(lookup[block], addressing)
        require(encoded is not None,
                'Compacted tileset needs tile ' + str(lookup[block])
                + ', which the ' + addressing + ' map cannot address')
        tilemap.append(encoded)
    return b''.join(tiles), bytes(tilemap)


def page_png(tile_bytes, map_bytes, width, height, addressing='linear', placeholders=False):
    """Render a page PNG from decoded tileset and tilemap bytes."""
    shades = compose(tile_bytes, map_bytes, width, height, addressing, placeholders)
    return gp.shades_to_png(width * 8, height * 8, shades)


def decode_page(png_bytes, width, height):
    """Decode an edited page PNG into a shade grid."""
    return gp.png_to_shades(png_bytes, width * 8, height * 8)[2]


def render_page(png_tiles, png_map, tiles_spec, map_spec):
    """Render a page PNG from the tracked tileset and tilemap PNG files."""
    tile_bytes = gp.load_resource(png_tiles, tiles_spec)
    map_bytes = gp.load_resource(png_map, map_spec)
    return page_png(tile_bytes, map_bytes, map_spec['width'], map_spec['height'],
                    map_spec['addressing'])


def retile(page_bytes, png_tiles, png_map, tiles_spec, map_spec, placeholders=False):
    """Split an edited page back into tileset and tilemap bytes.

    Returns ``(tileset_bytes, tilemap_bytes, added_tile_numbers)``.  Unchanged
    cells keep their original map byte; new 8x8 blocks are appended to the
    tileset in first-use order and encoded with the resource's addressing mode.
    Cells that reference tiles outside this resource are preserved verbatim and
    must still show the placeholder marker.
    """
    tile_bytes = gp.load_resource(png_tiles, tiles_spec)
    map_bytes = gp.load_resource(png_map, map_spec)
    return retile_bytes(page_bytes, tile_bytes, map_bytes, tiles_spec, map_spec,
                        placeholders, tiles_spec.get('tile_count'))


def retile_bytes(page_bytes, tile_bytes, map_bytes, tiles_spec, map_spec,
                 placeholders=False, max_tiles=None):
    require = common.require
    width, height = map_spec['width'], map_spec['height']
    addressing = map_spec['addressing']
    blocks = _tile_blocks(tile_bytes)
    shades = decode_page(page_bytes, width, height)
    page_width = width * 8
    new_map = bytearray()
    added = []
    lookup = {}
    for number, block in enumerate(blocks):
        lookup.setdefault(block, number)
    for cell_y in range(height):
        for cell_x in range(width):
            block = _block_from_page(shades, page_width, cell_x, cell_y)
            original = map_bytes[cell_y * width + cell_x]
            original_tile = index_to_tile(original, addressing)
            if not 0 <= original_tile < len(blocks):
                require(placeholders,
                        'Tilemap index ' + str(original) + ' points outside the tileset')
                require(block == PLACEHOLDER_BLOCK,
                        'Cannot edit a cell that references original ROM tiles')
                new_map.append(original)
                continue
            if blocks[original_tile] == block:
                new_map.append(original)
                continue
            match = lookup.get(block)
            if match is not None and tile_to_index(match, addressing) is not None:
                new_map.append(tile_to_index(match, addressing))
                continue
            number = len(blocks)
            if max_tiles is not None:
                require(number < max_tiles,
                        'Edited page needs a new tile but the resource has no spare tile slot')
            encoded = tile_to_index(number, addressing)
            require(encoded is not None,
                    'Edited page needs tile ' + str(number)
                    + ', which the ' + addressing + ' map cannot address')
            blocks.append(block)
            lookup.setdefault(block, number)
            new_map.append(encoded)
            added.append(number)
    new_tiles = b''.join(blocks)
    rebuilt = compose(new_tiles, bytes(new_map), width, height, addressing, placeholders)
    require(rebuilt == shades, 'Retiled resources do not reproduce the edited page')
    return new_tiles, bytes(new_map), added


def retile_within_capacity(page_bytes, png_tiles, png_map, tiles_spec, map_spec,
                           tiles_capacity, map_capacity, placeholders=False,
                           max_tiles=None):
    """Retile an edited page with the smallest encoding that still fits.

    Strategies are tried in order: preserve existing tile numbers (identity for
    unedited pages and cheap layout edits), then compact the tileset by first
    use, then compact with blocks sorted for better compression.
    """
    width, height = map_spec['width'], map_spec['height']
    addressing = map_spec['addressing']
    shades = decode_page(page_bytes, width, height)
    map_bytes = gp.load_resource(png_map, map_spec)
    attempts = []
    try:
        tiles, tilemap, added = retile(page_bytes, png_tiles, png_map, tiles_spec,
                                       map_spec, placeholders)
        attempts.append(('preserve', tiles, tilemap, added))
    except common.ProjectError:
        pass
    for name, sort_blocks in (('compact-first-use', False), ('compact-sorted', True)):
        try:
            compact = _compact(shades, map_bytes, width, height, addressing,
                               sort_blocks=sort_blocks, placeholders=placeholders,
                               max_tiles=max_tiles)
            attempts.append((name, compact[0], compact[1], []))
        except common.ProjectError:
            pass
    common.require(attempts, 'Edited page cannot be encoded within this resource layout')
    shortfalls = []
    for name, candidate_tiles, candidate_map, extra in attempts:
        tiles_size = len(hal_codec.pack(candidate_tiles))
        map_size = len(hal_codec.pack(candidate_map))
        if tiles_size <= tiles_capacity and map_size <= map_capacity:
            return candidate_tiles, candidate_map, extra, name
        shortfalls.append(name + ': tileset +' + str(max(0, tiles_size - tiles_capacity))
                          + 'B, map +' + str(max(0, map_size - map_capacity)) + 'B')
    common.require(False, 'Edited page does not fit the fixed ROM allocation ('
                   + '; '.join(shortfalls) + ')')

def page_png(tile_bytes, map_bytes, width, height, addressing='linear', placeholders=False):
    """Render a page PNG from decoded tileset and tilemap bytes."""
    shades = compose(tile_bytes, map_bytes, width, height, addressing, placeholders)
    return gp.shades_to_png(width * 8, height * 8, shades)


def decode_page(png_bytes, width, height):
    """Decode an edited page PNG into a shade grid."""
    return gp.png_to_shades(png_bytes, width * 8, height * 8)[2]


def render_page(png_tiles, png_map, tiles_spec, map_spec):
    """Render a page PNG from the tracked tileset and tilemap PNG files."""
    tile_bytes = gp.load_resource(png_tiles, tiles_spec)
    map_bytes = gp.load_resource(png_map, map_spec)
    return page_png(tile_bytes, map_bytes, map_spec['width'], map_spec['height'],
                    map_spec['addressing'])

