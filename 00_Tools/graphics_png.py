# SPDX-License-Identifier: MIT
"""Lossless PNG source layer for decoded Game Boy tile and tilemap resources.

Two canonical PNG layouts are used, both fully reversible:

``tiles-2bpp-4gray``
    Indexed PNG, 8x8 pixels per 8x8 tile, tiles stored row-major.  Pixel
    palette index is the 2bpp value: 0 = white, 1 = light, 2 = dark, 3 = black.
    The PNG width must be ``tiles_per_row * 8``; the last tile row is padded
    with white and ignored on import.

``tilemap-8bpp-grayscale``
    8-bit grayscale PNG, one pixel per tile.  The gray value is the raw tile
    index byte (0-255), so the 32x32 background maps are lossless.

PNG encoding/decoding uses Pillow (pinned in ``requirements.txt``).  Decoding
is strict on purpose: PNGs with alpha/transparency, interlacing, anti-aliasing,
off-palette colours or wrong dimensions are rejected with a message instead of
being silently approximated.  Re-encoding a decoded resource always reproduces
the exact decoded bytes pinned by the manifest.
"""
from __future__ import annotations

from pathlib import Path
import io
import struct
import zlib

from PIL import Image

SIGNATURE = b'\x89PNG\r\n\x1a\n'

TILES_MODE = 'tiles-2bpp-4gray'
TILEMAP_MODE = 'tilemap-8bpp-grayscale'
TILEMAP_ADDRESSING = ('linear', '0x8800')

# 2bpp value -> canonical grayscale colour.  Shade 0 is the lightest pixel.
SHADES = ((255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0))
GRAY_TO_SHADE = {colour[0]: value for value, colour in enumerate(SHADES)}

GRAY = 0
RGB = 2
PALETTE = 3


class GraphicsError(ValueError):
    """A PNG source layer is malformed or not pixel-exact."""


def _require(condition, message):
    if not condition:
        raise GraphicsError(message)


def _chunk(tag, payload):
    """Build one PNG chunk; kept for tests that synthesise malformed PNGs."""
    return (struct.pack('>I', len(payload)) + tag + payload
            + struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF))


def _check_chunks(data):
    """Validate the PNG chunk stream strictly before Pillow sees it."""
    _require(data.startswith(SIGNATURE), 'Not a PNG file')
    position = len(SIGNATURE)
    first = True
    while position + 12 <= len(data):
        length, tag = struct.unpack_from('>I4s', data, position)
        end = position + 12 + length
        _require(end <= len(data), 'Truncated PNG chunk')
        payload = data[position + 8:position + 8 + length]
        crc = struct.unpack_from('>I', data, position + 8 + length)[0]
        _require((zlib.crc32(tag + payload) & 0xFFFFFFFF) == crc,
                 'PNG chunk checksum mismatch')
        if first:
            _require(tag == b'IHDR', 'PNG must start with IHDR')
            _require(len(payload) == 13, 'Invalid PNG IHDR length')
            interlace = payload[12]
            _require(interlace == 0, 'Interlaced PNG is not supported')
            first = False
        if tag == b'tRNS':
            raise GraphicsError('PNG transparency is not supported')
        position = end
        if tag == b'IEND':
            return
    raise GraphicsError('Truncated PNG file')


def decode_png(data):
    """Decode a non-interlaced PNG.

    Returns ``(width, height, color_type, samples, palette)`` where ``samples``
    holds one value per pixel: a gray level, a palette index, or an (r, g, b)
    tuple.  Alpha/transparency and interlacing are rejected because they cannot
    be mapped back to 2bpp game data exactly.
    """
    _check_chunks(data)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (OSError, ValueError) as exc:
        raise GraphicsError('PNG could not be decoded: ' + str(exc)) from exc
    width, height = image.size
    mode = image.mode
    if mode == 'P':
        raw_palette = image.getpalette() or []
        palette = [tuple(raw_palette[index:index + 3])
                   for index in range(0, len(raw_palette) - 2, 3)]
        samples = list(image.getdata())
        return width, height, PALETTE, samples, palette
    if mode == 'L':
        return width, height, GRAY, list(image.getdata()), None
    if mode == 'RGB':
        return width, height, RGB, list(image.getdata()), None
    if mode in ('RGBA', 'LA', 'PA', 'P'):
        raise GraphicsError('PNG transparency is not supported')
    raise GraphicsError('Unsupported PNG mode: ' + repr(mode))


def _pixel_shade(value, color_type, palette):
    if color_type == PALETTE:
        _require(palette is not None and value < len(palette),
                 'Palette index outside the PLTE chunk')
        red, green, blue = palette[value]
    elif color_type == GRAY:
        red = green = blue = value
    else:
        red, green, blue = value
    _require(red == green == blue and red in GRAY_TO_SHADE,
             'Off-palette colour: ' + str((red, green, blue))
             + '; allowed values are 255, 170, 85, 0')
    return GRAY_TO_SHADE[red]


def png_to_tiles(data, tiles_per_row, tile_count):
    """Decode a tileset PNG back to its exact decoded tile bytes."""
    _require(isinstance(tiles_per_row, int) and tiles_per_row > 0,
             'tiles_per_row must be a positive integer')
    _require(isinstance(tile_count, int) and tile_count > 0,
             'tile_count must be a positive integer')
    width, height, color_type, samples, palette = decode_png(data)
    _require(width == tiles_per_row * 8, 'Tileset PNG width must be tiles_per_row * 8')
    _require(height > 0 and height % 8 == 0, 'Tileset PNG height must be a multiple of 8')
    tile_rows = (tile_count + tiles_per_row - 1) // tiles_per_row
    _require(height == tile_rows * 8,
             'Tileset PNG height does not match the expected tile count')
    shades = [_pixel_shade(value, color_type, palette) for value in samples]
    out = bytearray()
    for tile in range(tile_count):
        tile_x = tile % tiles_per_row
        tile_y = tile // tiles_per_row
        for row in range(8):
            low = high = 0
            base = (tile_y * 8 + row) * width + tile_x * 8
            for column in range(8):
                shade = shades[base + column]
                if shade & 1:
                    low |= 0x80 >> column
                if shade & 2:
                    high |= 0x80 >> column
            out.append(low)
            out.append(high)
    return bytes(out)


def png_to_tilemap(data, width, height):
    """Decode a tilemap PNG back to its exact raw tile-index bytes."""
    _require(isinstance(width, int) and isinstance(height, int)
             and width > 0 and height > 0, 'Tilemap dimensions must be positive')
    image_width, image_height, color_type, samples, palette = decode_png(data)
    _require((image_width, image_height) == (width, height),
             'Tilemap PNG dimensions do not match the manifest')
    out = bytearray()
    for value in samples:
        if color_type == PALETTE:
            _require(value < len(palette), 'Palette index outside the PLTE chunk')
            red, green, blue = palette[value]
        elif color_type == GRAY:
            red = green = blue = value
        else:
            red, green, blue = value
        _require(red == green == blue, 'Tilemap PNG colours must be neutral gray')
        out.append(red)
    return bytes(out)


def _encode_indexed(width, height, pixels):
    image = Image.frombytes('P', (width, height), bytes(pixels))
    image.putpalette([component for colour in SHADES for component in colour])
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=False, compress_level=9)
    return buffer.getvalue()


def _encode_gray(width, height, pixels):
    image = Image.frombytes('L', (width, height), bytes(pixels))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=False, compress_level=9)
    return buffer.getvalue()


def tiles_to_png(data, tiles_per_row):
    """Encode decoded tile bytes as the canonical indexed PNG."""
    _require(len(data) % 16 == 0, 'Decoded tile size must be a multiple of 16')
    _require(tiles_per_row > 0, 'tiles_per_row must be positive')
    tiles = len(data) // 16
    _require(tiles > 0, 'Cannot encode an empty tileset')
    rows = (tiles + tiles_per_row - 1) // tiles_per_row
    width = tiles_per_row * 8
    height = rows * 8
    pixels = bytearray(width * height)  # palette index 0 = white padding
    for tile in range(tiles):
        tile_x = tile % tiles_per_row
        tile_y = tile // tiles_per_row
        base = tile * 16
        for row in range(8):
            low = data[base + row * 2]
            high = data[base + row * 2 + 1]
            offset = (tile_y * 8 + row) * width + tile_x * 8
            for column in range(8):
                bit = 7 - column
                pixels[offset + column] = (((high >> bit) & 1) << 1) | ((low >> bit) & 1)
    return _encode_indexed(width, height, pixels)


def tilemap_to_png(data, width, height):
    """Encode raw tile-index bytes as the canonical 8-bit grayscale PNG."""
    _require(width > 0 and height > 0, 'Tilemap dimensions must be positive')
    _require(len(data) == width * height, 'Tilemap size does not match its dimensions')
    return _encode_gray(width, height, data)


def shades_to_png(width, height, values):
    """Encode a 2bpp shade grid (one value per pixel) as a canonical PNG."""
    _require(width > 0 and height > 0, 'Image dimensions must be positive')
    _require(len(values) == width * height, 'Pixel count does not match the dimensions')
    pixels = bytearray(values)
    _require(all(value < len(SHADES) for value in pixels), 'Shade values must be 0-3')
    return _encode_indexed(width, height, pixels)


def png_to_shades(data, width=None, height=None):
    """Decode a canonical 4-colour image into a flat shade grid."""
    image_width, image_height, color_type, samples, palette = decode_png(data)
    if width is not None or height is not None:
        _require((image_width, image_height) == (width, height),
                 'Image dimensions do not match the expected layout')
    return image_width, image_height, [_pixel_shade(value, color_type, palette)
                                       for value in samples]


def load_resource(path, spec):
    """Decode one manifest graphics entry, dispatching on its PNG mode."""
    _require(isinstance(spec, dict), 'Resource is missing its PNG description')
    mode = spec.get('mode')
    data = Path(path).read_bytes()
    if mode == TILES_MODE:
        tiles_per_row = spec.get('tiles_per_row')
        tile_count = spec.get('tile_count')
        _require(isinstance(tile_count, int) and tile_count > 0,
                 'Tileset entry is missing tile_count')
        return png_to_tiles(data, tiles_per_row, tile_count)
    if mode == TILEMAP_MODE:
        width, height = spec.get('width'), spec.get('height')
        return png_to_tilemap(data, width, height)
    raise GraphicsError('Unknown PNG resource mode: ' + repr(mode))


def write_resource(path, data, spec):
    """Encode decoded resource bytes into the canonical PNG form."""
    mode = spec.get('mode')
    if mode == TILES_MODE:
        payload = tiles_to_png(data, spec.get('tiles_per_row'))
    elif mode == TILEMAP_MODE:
        payload = tilemap_to_png(data, spec.get('width'), spec.get('height'))
    else:
        raise GraphicsError('Unknown PNG resource mode: ' + repr(mode))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return payload
