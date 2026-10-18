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

Only Python's standard library is used.  Decoding is strict on purpose: PNGs
with alpha, anti-aliasing, off-palette colours or wrong dimensions are rejected
with a message instead of being silently approximated.  Re-encoding a decoded
resource always reproduces the exact decoded bytes pinned by the manifest.
"""
from __future__ import annotations

from pathlib import Path
import struct
import zlib

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
    return (struct.pack('>I', len(payload)) + tag + payload
            + struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF))


def _paeth(left, above, upper_left):
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_upper_left:
        return left
    if distance_above <= distance_upper_left:
        return above
    return upper_left


def _unfilter(raw, width, height, bits_per_pixel):
    """Reverse PNG scanline filters; no interlace support."""
    bytes_per_pixel = max(1, bits_per_pixel // 8)
    stride = (width * bits_per_pixel + 7) // 8
    _require(len(raw) == height * (stride + 1),
             'PNG image data length does not match its dimensions')
    out = bytearray()
    previous = bytearray(stride)
    position = 0
    for _ in range(height):
        method = raw[position]
        position += 1
        line = bytearray(raw[position:position + stride])
        position += stride
        if method == 0:
            pass
        elif method == 1:
            for index in range(stride):
                left = line[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                line[index] = (line[index] + left) & 0xFF
        elif method == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif method == 3:
            for index in range(stride):
                left = line[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif method == 4:
            for index in range(stride):
                left = line[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                line[index] = (line[index] + _paeth(left, previous[index], upper_left)) & 0xFF
        else:
            raise GraphicsError('Unsupported PNG filter type: ' + str(method))
        out.extend(line)
        previous = line
    return out, stride


def _unpack_indices(line, width, bit_depth):
    if bit_depth == 8:
        return list(line[:width])
    values = []
    mask = (1 << bit_depth) - 1
    per_byte = 8 // bit_depth
    for byte in line:
        for slot in range(per_byte):
            if len(values) == width:
                return values
            values.append((byte >> (8 - bit_depth * (slot + 1))) & mask)
    return values


def decode_png(data):
    """Decode a non-interlaced PNG.

    Returns ``(width, height, color_type, samples, palette)`` where ``samples``
    holds one value per pixel: a gray level, a palette index, or an (r, g, b)
    tuple.  Alpha and interlacing are rejected because they cannot be mapped
    back to 2bpp game data exactly.
    """
    _require(data.startswith(SIGNATURE), 'Not a PNG file')
    position = len(SIGNATURE)
    width = height = bit_depth = color_type = None
    palette = None
    transparent = False
    payload = bytearray()
    while position + 12 <= len(data):
        length, tag = struct.unpack_from('>I4s', data, position)
        position += 8
        _require(position + length + 4 <= len(data), 'Truncated PNG chunk')
        chunk = data[position:position + length]
        crc = struct.unpack_from('>I', data, position + length)[0]
        _require(zlib.crc32(tag + chunk) & 0xFFFFFFFF == crc,
                 'PNG chunk checksum mismatch: ' + tag.decode('ascii', 'replace'))
        position += length + 4
        if tag == b'IHDR':
            _require(length == 13, 'Invalid PNG header length')
            (width, height, bit_depth, color_type,
             compression, filtering, interlace) = struct.unpack('>IIBBBBB', chunk)
            _require(compression == 0 and filtering == 0,
                     'Unsupported PNG compression/filter method')
            _require(interlace == 0,
                     'Interlaced PNG is not accepted; export a non-interlaced PNG')
        elif tag == b'PLTE':
            _require(length % 3 == 0 and 3 <= length <= 768, 'Invalid PNG palette')
            palette = [tuple(chunk[index:index + 3]) for index in range(0, length, 3)]
        elif tag == b'tRNS':
            transparent = True
        elif tag == b'IDAT':
            payload.extend(chunk)
        elif tag == b'IEND':
            break
    _require(width is not None, 'PNG is missing its IHDR chunk')
    _require(not transparent, 'PNG transparency is not accepted; flatten the image first')
    _require(color_type in (GRAY, RGB, PALETTE),
             'Unsupported PNG colour type: ' + str(color_type))
    if color_type == PALETTE:
        _require(palette is not None, 'Indexed PNG is missing its palette')
        _require(bit_depth in (1, 2, 4, 8), 'Unsupported indexed PNG bit depth: ' + str(bit_depth))
        bits_per_pixel = bit_depth
    elif color_type == GRAY:
        _require(bit_depth == 8, 'Grayscale PNG must use 8 bits per sample')
        bits_per_pixel = 8
    else:
        _require(bit_depth == 8, 'RGB PNG must use 8 bits per sample')
        bits_per_pixel = 24
    raw = zlib.decompress(bytes(payload))
    lines, stride = _unfilter(raw, width, height, bits_per_pixel)
    samples = []
    for row in range(height):
        line = lines[row * stride:(row + 1) * stride]
        if color_type == PALETTE:
            samples.extend(_unpack_indices(line, width, bit_depth))
        elif color_type == GRAY:
            samples.extend(line[:width])
        else:
            for x in range(width):
                base = x * 3
                samples.append((line[base], line[base + 1], line[base + 2]))
    return width, height, color_type, samples, palette


def _pixel_shade(value, color_type, palette):
    """Map one decoded PNG sample to a 2bpp shade, rejecting inexact colours."""
    if color_type == PALETTE:
        _require(value < len(palette), 'Palette index outside the PLTE chunk')
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
    needed = tile_count
    tile_rows = (needed + tiles_per_row - 1) // tiles_per_row
    _require(height == tile_rows * 8,
             'Tileset PNG height does not match the expected tile count')
    shades = [_pixel_shade(value, color_type, palette) for value in samples]
    out = bytearray()
    for tile in range(needed):
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
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter: None keeps the file stable and easy to diff
        raw.extend(pixels[row * width:(row + 1) * width])
    return _assemble(width, height, 8, PALETTE, bytes(raw), palette=SHADES)


def tilemap_to_png(data, width, height):
    """Encode raw tile-index bytes as the canonical 8-bit grayscale PNG."""
    _require(width > 0 and height > 0, 'Tilemap dimensions must be positive')
    _require(len(data) == width * height, 'Tilemap size does not match its dimensions')
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw.extend(data[row * width:(row + 1) * width])
    return _assemble(width, height, 8, GRAY, bytes(raw))


def _assemble(width, height, bit_depth, color_type, raw, palette=None):
    png = bytearray(SIGNATURE)
    png.extend(_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, bit_depth,
                                          color_type, 0, 0, 0)))
    if palette is not None:
        png.extend(_chunk(b'PLTE', b''.join(bytes(colour) for colour in palette)))
    png.extend(_chunk(b'IDAT', zlib.compress(raw, 9)))
    png.extend(_chunk(b'IEND', b''))
    return bytes(png)


def shades_to_png(width, height, values):
    """Encode a 2bpp shade grid (one value per pixel) as a canonical PNG."""
    _require(width > 0 and height > 0, 'Image dimensions must be positive')
    _require(len(values) == width * height, 'Pixel count does not match the dimensions')
    pixels = bytearray(values)
    _require(all(value < len(SHADES) for value in pixels), 'Shade values must be 0-3')
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw.extend(pixels[row * width:(row + 1) * width])
    return _assemble(width, height, 8, PALETTE, bytes(raw), palette=SHADES)


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
