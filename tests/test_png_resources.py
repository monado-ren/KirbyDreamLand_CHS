# SPDX-License-Identifier: MIT
"""Lossless PNG graphics sources: round-trips and strict rejection tests."""
from pathlib import Path
import hashlib
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import common
import graphics_png as gp


def derive(entry, raw):
    """The tileset portion of a resource (bundles append a map on top)."""
    if entry.get('bundle') is not None:
        return raw[:entry['png']['tile_count'] * 16]
    return raw


def encode(raw, spec):
    if spec['mode'] == gp.TILES_MODE:
        return gp.tiles_to_png(raw, spec['tiles_per_row'])
    return gp.tilemap_to_png(raw, spec['width'], spec['height'])


def sample_tiles(count):
    """Deterministic synthetic tile bytes that exercise all four shades."""
    out = bytearray()
    for index in range(count):
        for row in range(8):
            out.append((index * 37 + row * 11) & 0xFF)
            out.append((index * 91 + row * 29) & 0xFF)
    return bytes(out)


class ManifestRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = common.load_manifest()

    def test_every_resource_derives_its_pinned_bytes(self):
        prepared = common.prepare_resources(self.manifest)
        self.assertEqual(len(prepared), 46)
        for entry, raw, _packed in prepared:
            with self.subTest(resource=entry['id']):
                path = ROOT / entry['source']
                self.assertTrue(path.is_file(), path)
                spec = dict(entry['png'], decoded_size=entry['decoded_size'])
                self.assertEqual(gp.load_resource(path, spec), derive(entry, raw))
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['decoded_sha256'])
                # The canonical encoder must reproduce the tracked PNG bytes.
                self.assertEqual(encode(derive(entry, raw), entry['png']), path.read_bytes())

    def test_manifest_uses_both_png_modes(self):
        modes = {entry['png']['mode'] for entry in self.manifest['resources']}
        self.assertEqual(modes, {gp.TILES_MODE, gp.TILEMAP_MODE})


class CanonicalRoundTripTests(unittest.TestCase):
    def test_tilesets_roundtrip_across_padding(self):
        for count in (1, 25, 128, 164, 188, 328, 384):
            with self.subTest(tiles=count):
                raw = sample_tiles(count)
                for tiles_per_row in (1, 4, 16, 32):
                    png = gp.tiles_to_png(raw, tiles_per_row)
                    self.assertEqual(gp.png_to_tiles(png, tiles_per_row, len(raw) // 16), raw)

    def test_tilemaps_roundtrip_every_byte(self):
        raw = bytes(range(256)) * 4
        png = gp.tilemap_to_png(raw, 32, 32)
        self.assertEqual(gp.png_to_tilemap(png, 32, 32), raw)

    def test_scanline_filters_are_reversed(self):
        raw = sample_tiles(8)
        width = 4 * 8
        pixels = list(gp.decode_png(gp.tiles_to_png(raw, 4))[3])
        stride = width
        height = len(pixels) // stride
        rows = [pixels[index * stride:(index + 1) * stride] for index in range(height)]
        for method in (1, 2, 3, 4):
            filtered = bytearray()
            previous = [0] * stride
            for row in rows:
                filtered.append(method)
                for index, value in enumerate(row):
                    left = row[index - 1] if index else 0
                    above = previous[index]
                    upper_left = previous[index - 1] if index else 0
                    if method == 1:
                        predictor = left
                    elif method == 2:
                        predictor = above
                    elif method == 3:
                        predictor = (left + above) // 2
                    else:
                        estimate = left + above - upper_left
                        distances = (abs(estimate - left), abs(estimate - above),
                                     abs(estimate - upper_left))
                        predictor = (left, above, upper_left)[distances.index(min(distances))]
                    filtered.append((value - predictor) & 0xFF)
                previous = row
            png = bytearray(gp.SIGNATURE)
            png.extend(gp._chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8,
                                                      gp.PALETTE, 0, 0, 0)))
            png.extend(gp._chunk(b'PLTE', b''.join(bytes(colour) for colour in gp.SHADES)))
            png.extend(gp._chunk(b'IDAT', zlib.compress(bytes(filtered), 9)))
            png.extend(gp._chunk(b'IEND', b''))
            with self.subTest(filter=method):
                self.assertEqual(gp.png_to_tiles(bytes(png), 4, len(raw) // 16), raw)


class StrictRejectionTests(unittest.TestCase):
    def setUp(self):
        self.raw = sample_tiles(4)
        self.png = gp.tiles_to_png(self.raw, 4)

    def test_off_palette_colour_rejected(self):
        width, height = 4 * 8, 8
        pixels = list(gp.decode_png(self.png)[3])
        rows = bytearray()
        for row in range(height):
            rows.append(0)
            for index in pixels[row * width:(row + 1) * width]:
                red, green, blue = gp.SHADES[index]
                rows.extend((red, green, blue))
        rows[3] = 128  # first pixel is now mid-gray, not a canonical shade
        rgb = bytearray(gp.SIGNATURE)
        rgb.extend(gp._chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8,
                                                  gp.RGB, 0, 0, 0)))
        rgb.extend(gp._chunk(b'IDAT', zlib.compress(bytes(rows), 9)))
        rgb.extend(gp._chunk(b'IEND', b''))
        with self.assertRaisesRegex(gp.GraphicsError, 'Off-palette'):
            gp.png_to_tiles(bytes(rgb), 4, len(self.raw) // 16)

    def test_transparency_rejected(self):
        width, height = 32, 8
        png = bytearray(gp.SIGNATURE)
        png.extend(gp._chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8,
                                                  gp.PALETTE, 0, 0, 0)))
        png.extend(gp._chunk(b'PLTE', b''.join(bytes(colour) for colour in gp.SHADES)))
        png.extend(gp._chunk(b'tRNS', b'\x00'))
        png.extend(gp._chunk(b'IDAT', zlib.compress(bytes(height * (width + 1)), 9)))
        png.extend(gp._chunk(b'IEND', b''))
        with self.assertRaisesRegex(gp.GraphicsError, 'transparency'):
            gp.png_to_tiles(bytes(png), 4, len(self.raw) // 16)

    def test_interlaced_rejected(self):
        png = bytearray(self.png)
        header = 8 + 8  # signature + IHDR length/type
        interlace_at = header + 12
        png[interlace_at] = 1
        struct.pack_into('>I', png, header + 13,
                         zlib.crc32(bytes(png[header - 4:header + 13])) & 0xFFFFFFFF)
        with self.assertRaisesRegex(gp.GraphicsError, 'Interlaced'):
            gp.png_to_tiles(bytes(png), 4, len(self.raw) // 16)

    def test_wrong_width_rejected(self):
        with self.assertRaisesRegex(gp.GraphicsError, 'width'):
            gp.png_to_tiles(self.png, 8, len(self.raw) // 16)

    def test_wrong_tile_count_rejected(self):
        with self.assertRaisesRegex(gp.GraphicsError, 'tile count'):
            gp.png_to_tiles(self.png, 4, len(self.raw) // 16 + 1)

    def test_wrong_tilemap_dimensions_rejected(self):
        png = gp.tilemap_to_png(bytes(1024), 32, 32)
        with self.assertRaisesRegex(gp.GraphicsError, 'dimensions'):
            gp.png_to_tilemap(png, 16, 64)

    def test_corrupt_chunk_checksum_rejected(self):
        png = bytearray(self.png)
        png[20] ^= 0xFF
        with self.assertRaisesRegex(gp.GraphicsError, 'checksum'):
            gp.decode_png(bytes(png))


if __name__ == '__main__':
    unittest.main()
