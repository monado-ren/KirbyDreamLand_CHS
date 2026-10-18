# SPDX-License-Identifier: MIT
"""Text layers: font typesetting derived from font subsets + translations.

The localized pages contain text pixels that were typeset by hand.  This module
turns those pixels into data:

* ``02_Text/layout.json`` records, per text entry, the page/font/line-height and
  the (x, y) anchor of every rendered line.
* ``03_Image/text-base/<page>.png`` stores the same page with the text ink
  removed (replaced by nearby background), so a page can be regenerated as
  ``base + font(translation, layout)``.
* ``render`` regenerates pages from base + font + layout + translations and can
  verify byte-identical output against the tracked pages.

Only text that can be matched exactly against the pinned font subset is
converted; anything else stays hand art and is reported as ``manual``.

Usage:
    python 00_Tools/text_layout.py extract [--write]
    python 00_Tools/text_layout.py check
    python 00_Tools/text_layout.py render [--write]
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import common
import graphics_png

ROOT = common.ROOT
TEXT_JSON = ROOT / '02_Text' / 'zh-Hans.json'
LAYOUT_JSON = ROOT / '02_Text' / 'layout.json'
FONT_12 = ROOT / '05_Font' / 'generated' / 'jpzh-bitmap-12.json'
FONT_8 = ROOT / '05_Font' / 'generated' / 'jpzh-bitmap-hud-8.json'
BASE_DIR = ROOT / '03_Image' / 'text-base'

FONT_SPECS = {
    '12px': {'path': FONT_12, 'height': 12, 'line_height': 12, 'ink': 3},
    '8px': {'path': FONT_8, 'height': 8, 'line_height': 8, 'ink': 3},
}

# text entry -> (page resource id, font) for pages whose text is typeset.
TEXT_PAGES = {
    'stage_1_name': ('rom_06c000', '12px'),
    'stage_2_name': ('rom_06c70b', '12px'),
    'stage_3_name': ('rom_06cda8', '12px'),
    'stage_4_name': ('rom_06d490', '12px'),
    'stage_5_name': ('rom_06db85', '12px'),
    'sound_test': ('rom_0438f6', '12px'),
    'music': ('rom_0438f6', '12px'),
    'sound': ('rom_0438f6', '12px'),
    'game_over': ('rom_04454c', '12px'),
    'continue': ('rom_044734', '12px'),
    'end': ('rom_044734', '12px'),
}


class TextLayoutError(ValueError):
    pass


def require(cond, message):
    if not cond:
        raise TextLayoutError(message)


def load_fonts():
    fonts = {}
    for name, spec in FONT_SPECS.items():
        require(spec['path'].is_file(),
                'missing font subset %s; run 00_Tools/fetch_fonts.py' % spec['path'])
        fonts[name] = json.loads(spec['path'].read_text(encoding='utf-8'))['glyphs']
    return fonts


def load_translations():
    data = json.loads(TEXT_JSON.read_text(encoding='utf-8'))
    return {entry['id']: entry for entry in data['entries']}


def glyph_ink(glyph):
    rows = glyph['rows']
    return glyph['width'], len(rows), [(x, y) for y, row in enumerate(rows)
                                       for x, value in enumerate(row) if value == '1']


def line_width(font, line):
    return sum(font[char]['width'] for char in line)


def match_lines(shades, width, height, font, lines, anchor_x, anchor_y):
    """True when every ink pixel of the typeset lines is the ink shade."""
    cursor_y = anchor_y
    for line in lines:
        cursor_x = anchor_x
        for char in line:
            glyph = font.get(char)
            if glyph is None:
                return False
            glyph_width, glyph_height, ink = glyph_ink(glyph)
            for dx, dy in ink:
                px, py = cursor_x + dx, cursor_y + dy
                if not (0 <= px < width and 0 <= py < height):
                    return False
                if shades[py * width + px] != 3:
                    return False
            cursor_x += glyph_width
        cursor_y += FONT_SPECS['12px']['height'] if False else glyph_height
    return True


def count_extra_ink(shades, width, lines, font, anchor_x, anchor_y, line_height):
    extra = 0
    cursor_y = anchor_y
    for line in lines:
        cursor_x = anchor_x
        for char in line:
            glyph = font[char]
            glyph_width, glyph_height, ink = glyph_ink(glyph)
            for row in range(glyph_height):
                if cursor_y + row >= len(shades) // width:
                    continue
                for column in range(glyph_width):
                    if cursor_x + column >= width or (column, row) in ink:
                        continue
                    if shades[(cursor_y + row) * width + cursor_x + column] == 3:
                        extra += 1
            cursor_x += glyph_width
        cursor_y += line_height
    return extra


def find_anchor(shades, width, height, font, text, line_height):
    """Locate one typeset text (may contain newlines) exactly in a page."""
    lines = text.split('\n')
    first = font.get(lines[0][0]) if lines and lines[0] else None
    if first is None:
        return None
    if any(char not in font for line in lines for char in line):
        return None
    glyph_width, glyph_height = first['width'], len(first['rows'])
    total_height = line_height * (len(lines) - 1) + glyph_height
    candidates = []
    for anchor_y in range(0, max(0, height - total_height) + 1):
        for anchor_x in range(0, width - glyph_width + 1):
            if not match_lines(shades, width, height, font, lines, anchor_x, anchor_y):
                continue
            extra = count_extra_ink(shades, width, lines, font, anchor_x, anchor_y,
                                    line_height)
            candidates.append((extra, anchor_y, anchor_x))
    if not candidates:
        return None
    candidates.sort()
    clean = [candidate for candidate in candidates if candidate[0] == 0]
    if not clean:
        # The page may draw a box/border through the glyph cells; report the
        # best candidate so the caller can classify it as manual.
        return None
    extra, anchor_y, anchor_x = clean[0]
    unique = clean
    return {'x': anchor_x, 'y': anchor_y, 'lines': len(lines),
            'width': line_width(font, lines[0]), 'height': glyph_height,
            'candidates': len(unique)}


_BASE_ROM = None


def page_shades(resource, manifest=None):
    if resource.get('page'):
        path = ROOT / resource['page']
        require(path.is_file(), 'missing page PNG ' + str(path))
        width, height, shades = graphics_png.png_to_shades(path.read_bytes())
        return path, width, height, list(shades)
    require(resource.get('edit'), 'resource has neither page nor edit: ' + resource['id'])
    global _BASE_ROM
    if _BASE_ROM is None:
        _BASE_ROM = (ROOT / 'baserom.gb').read_bytes()
    import page_edits
    edit = page_edits.load_edit(resource)
    png = page_edits.render_png(resource, edit, _BASE_ROM)
    width, height, shades = graphics_png.png_to_shades(png)
    return Path('build/pages') / (resource['id'] + '.png'), width, height, list(shades)


def extract(translations=None, fonts=None):
    translations = translations or load_translations()
    fonts = fonts or load_fonts()
    manifest = common.load_manifest()
    resources = {entry['id']: entry for entry in manifest['resources']}
    cache = {}
    layout = {}
    manual = []
    for entry_id, (page_id, font_name) in TEXT_PAGES.items():
        entry = translations.get(entry_id)
        if entry is None or entry.get('integration_status') != 'integrated':
            continue
        if page_id not in resources:
            manual.append((entry_id, page_id, 'missing page resource'))
            continue
        if page_id not in cache:
            cache[page_id] = page_shades(resources[page_id])
        path, width, height, shades = cache[page_id]
        resource_page = resources[page_id]
        text = entry['translation_zh_hans']
        font = fonts[font_name]
        line_height = FONT_SPECS[font_name]['height']
        anchor = find_anchor(shades, width, height, font, text, line_height)
        if anchor is None:
            manual.append((entry_id, page_id, 'not matched exactly'))
            continue
        layout[entry_id] = {
            'id': entry_id,
            'page': page_id,
            'page_png': str(path.relative_to(ROOT)),
            'font': font_name,
            'line_height': line_height,
            'page_png': str((ROOT / resource_page.get('page', '')).relative_to(ROOT))
            if resource_page.get('page') else None,
            'translation_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'anchor': anchor,
        }
    return {'layout': layout, 'manual': manual, 'pages': cache}


def render_text(shades, width, font, text, anchor, line_height):
    """Paint typeset text ink onto a shade buffer (returns a new list)."""
    out = list(shades)
    cursor_y = anchor['y']
    for line in text.split('\n'):
        cursor_x = anchor['x']
        for char in line:
            glyph = font.get(char)
            require(glyph is not None, 'font lacks %r' % char)
            glyph_width, glyph_height, ink = glyph_ink(glyph)
            for dx, dy in ink:
                out[(cursor_y + dy) * width + cursor_x + dx] = 3
            cursor_x += glyph_width
        cursor_y += line_height
    return out


def build_base(shades, width, height, font, text, anchor, line_height):
    """Remove text ink, filling it from the nearest non-ink pixel of the row."""
    out = list(shades)
    cursor_y = anchor['y']
    for line in text.split('\n'):
        cursor_x = anchor['x']
        for char in line:
            glyph = font[char]
            glyph_width, glyph_height, ink = glyph_ink(glyph)
            for dx, dy in ink:
                px, py = cursor_x + dx, cursor_y + dy
                replacement = 0
                for distance in range(1, 8):
                    for candidate_x in (px - distance, px + distance):
                        if 0 <= candidate_x < width:
                            value = out[py * width + candidate_x]
                            if value != 3:
                                replacement = value
                                break
                    if replacement != 3:
                        break
                out[py * width + px] = 0 if replacement == 3 else replacement
            cursor_x += glyph_width
        cursor_y += line_height
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('extract', 'check', 'render'))
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    translations = load_translations()
    fonts = load_fonts()
    if args.command == 'extract':
        result = extract(translations, fonts)
        layout = result['layout']
        print('TEXT_EXTRACT=PASS MATCHED=%d MANUAL=%d'
              % (len(layout), len(result['manual'])))
        for entry_id, page_id, reason in result['manual']:
            print('TEXT_MANUAL=%s (%s): %s' % (entry_id, page_id, reason))
        if args.write:
            BASE_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                'format_version': 1,
                'font_sources': {name: str(spec['path'].relative_to(ROOT))
                                 for name, spec in FONT_SPECS.items()},
                'pages': {},
                'entries': layout,
            }
            for page_id, (path, width, height, shades) in result['pages'].items():
                base_shades = list(shades)
                for entry_id, record in layout.items():
                    if record['page'] != page_id:
                        continue
                    text = translations[entry_id]['translation_zh_hans']
                    base_shades = build_base(base_shades, width, height,
                                             fonts[record['font']], text,
                                             record['anchor'], record['line_height'])
                base_path = BASE_DIR / (page_id + '.png')
                base_path.write_bytes(graphics_png.shades_to_png(width, height, base_shades))
                payload['pages'][page_id] = {
                    'base_png': str(base_path.relative_to(ROOT)),
                    'width': width,
                    'height': height,
                }
            LAYOUT_JSON.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            print('TEXT_LAYOUT=WROTE %s ENTRIES=%d PAGES=%d'
                  % (LAYOUT_JSON.relative_to(ROOT), len(layout), len(payload['pages'])))
        return 0
    require(LAYOUT_JSON.is_file(), 'no layout yet; run extract --write')
    payload = json.loads(LAYOUT_JSON.read_text(encoding='utf-8'))
    failures = []
    checked = 0
    rendered_pages = {}
    for page_id, page in payload['pages'].items():
        width, height, base_shades = graphics_png.png_to_shades(
            (ROOT / page['base_png']).read_bytes())
        shades = list(base_shades)
        for entry_id, record in payload['entries'].items():
            if record['page'] != page_id:
                continue
            text = translations[entry_id]['translation_zh_hans']
            shades = render_text(shades, width, fonts[record['font']], text,
                                 record['anchor'], record['line_height'])
            checked += 1
        rendered_pages[page_id] = shades
        # Find the committed page image (bundle or reconstructed edit page).
        manifest = common.load_manifest()
        resource = next(item for item in manifest['resources'] if item['id'] == page_id)
        expected_path, expected_width, expected_height, expected = page_shades(resource)
        if list(shades) != list(expected):
            differences = sum(1 for left, right in zip(shades, expected) if left != right)
            failures.append((page_id, differences))
    print('TEXT_RENDER=%s ENTRIES=%d PAGES=%d'
          % ('PASS' if not failures else 'FAIL', checked, len(payload['pages'])))
    for page_id, differences in failures:
        print('TEXT_DIFF=%s: %d pixels' % (page_id, differences), file=sys.stderr)
    if args.command == 'render' and args.write and not failures:
        for page_id, shades in rendered_pages.items():
            page = payload['pages'][page_id]
            width, height = page['width'], page['height']
            target = ROOT / page.get('page_png') if False else None
            resource = next(item for item in common.load_manifest()['resources']
                            if item['id'] == page_id)
            if resource.get('page'):
                (ROOT / resource['page']).write_bytes(
                    graphics_png.shades_to_png(width, height, shades))
            else:
                require(False, 'edit page rendering not wired for ' + page_id)
        print('TEXT_PAGES=WROTE %d' % len(rendered_pages))
    return 0 if not failures else 1
    return 0 if not failures else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('TEXT_LAYOUT=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
