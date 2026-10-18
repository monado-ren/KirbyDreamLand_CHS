# SPDX-License-Identifier: MIT
"""Text layers: font typesetting derived from font subsets + translations.

Pages whose text was typeset during localization are stored as data:

* ``02_Text/layout.json``: every text entry's page, font, line height, anchors
  (per line where the original layout is not left-aligned), optional per-cell
  glyph overrides, and the characters actually rendered (``typeset``).
* ``03_Image/text-base/<page>.png`` for **page-backed** bundle pages: the same
  page with the text ink removed, so ``base + font(translation)`` regenerates it.

Two storage modes:

``page``
    Bundle pages stored as trackable PNGs. A text-free base PNG is committed, so
    the page can be regenerated and byte-compared end to end.

``edit``
    Baseline+overlay pages (gallery, HUD, hints): no base is committed because
    the page already derives from the user's Rev1 ROM.  ``check`` proves the
    page's text ink is exactly the pinned font, and ``render`` rewrites the page
    under ``build/pages/`` for ``pages.py retile`` to fold back into the overlay.

``extract`` rebuilds the layout from the authoritative anchors in
``02_Text/{gallery,hint,hud}-layout.json`` plus exact glyph matching, and
``--write`` regenerates ``layout.json`` and the bundle text-base PNGs.

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
GALLERY_JSON = ROOT / '02_Text' / 'gallery-layout.json'
HINT_JSON = ROOT / '02_Text' / 'hint-layout.json'
HUD_JSON = ROOT / '02_Text' / 'hud-layout.json'
FONT_12 = ROOT / '05_Font' / 'generated' / 'jpzh-bitmap-12.json'
FONT_8 = ROOT / '05_Font' / 'generated' / 'jpzh-bitmap-hud-8.json'
BASE_DIR = ROOT / '03_Image' / 'text-base'
BUILD_PAGES = ROOT / 'build' / 'pages'

FONT_SPECS = {
    '12px': {'path': FONT_12, 'height': 12, 'line_height': 12, 'ink': 3},
    '8px': {'path': FONT_8, 'height': 8, 'line_height': 8, 'ink': 3},
}

# Bundle pages: (entry ids, page, font, rendered text overrides)
BUNDLE_PAGES = (
    ('rom_06c000', (
        ('stage_1_name', '葛绿谷绿'),
        ('stage_1_number', '场景'),
    )),
    ('rom_06c70b', (
        ('stage_2_name', '箩箩箩的城堡'),
        ('stage_2_number', '场景'),
    )),
    ('rom_06cda8', (
        ('stage_3_name', '漂浮岛屿'),
        ('stage_3_number', '场景'),
    )),
    ('rom_06d490', (
        ('stage_4_name', '泡泡云层'),
        ('stage_4_number', '场景'),
    )),
    ('rom_06db85', (
        ('stage_5_name', '帝帝帝山'),
        ('stage_5_number', '场景'),
    )),
    ('rom_0438f6', (('sound_test', None), ('music', None), ('sound', None))),
    ('rom_04454c', (('game_over', None),)),
    ('rom_044734', (('continue', None), ('end', None))),
)


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


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def glyph_ink(glyph):
    rows = glyph['rows']
    return glyph['width'], len(rows), [(x, y) for y, row in enumerate(rows)
                                       for x, value in enumerate(row) if value == '1']


def line_width(font, line):
    return sum(font[char]['width'] for char in line)


def rendered_lines(record, translation):
    """Lines of *typeset* text (stage numbers render only their Chinese part)."""
    text = record.get('typeset') or translation
    return text.split('\n')


def line_anchors(record):
    if 'positions' in record:
        return [{'x': x, 'y': y} for x, y in record['positions']]
    return [{'x': record['anchor']['x'],
             'y': record['anchor']['y'] + index * record['line_height']}
            for index in range(len(record.get('typeset', '').split('\n')) or 1)]


def glyph_cells(record, translation, font):
    """Yield (line_index, column, x, y, char, glyph, override_rows)."""
    lines = rendered_lines(record, translation)
    anchors = line_anchors(record)
    require(len(anchors) >= len(lines), 'layout needs one anchor per line')
    overrides = record.get('overrides', {})
    for line_index, (line, anchor) in enumerate(zip(lines, anchors)):
        cursor_x = anchor['x']
        for column, char in enumerate(line):
            glyph = font.get(char)
            require(glyph is not None, 'font lacks %r' % char)
            glyph_width, glyph_height, ink = glyph_ink(glyph)
            rows = overrides.get('%d:%d' % (line_index, column))
            yield (line_index, column, cursor_x, anchor['y'], char, glyph, rows)
            cursor_x += glyph_width


def match_entry(shades, width, height, record, translation, font):
    """True when every typeset glyph cell equals the pinned font (or its override)."""
    for _line, _col, x, y, _char, glyph, override in glyph_cells(record, translation, font):
        glyph_width, glyph_height, ink = glyph_ink(glyph)
        if override:
            rows = [[1 if value == '1' else 0 for value in row] for row in override]
            for row_index, row in enumerate(rows):
                for column, value in enumerate(row):
                    if shades[(y + row_index) * width + x + column] != (3 if value else 0):
                        # Non-ink cells may hold background art on edit pages.
                        if value:
                            return False
            continue
        for dx, dy in ink:
            if not (0 <= x + dx < width and 0 <= y + dy < height):
                return False
            if shades[(y + dy) * width + x + dx] != 3:
                return False
    return True


def find_anchor(shades, width, height, font, text, line_height):
    """Locate a single-line text exactly in a page; returns (x, y) or None."""
    if '\n' in text or any(char not in font for char in text):
        return None
    first = font[text[0]]
    glyph_width, glyph_height, _ink = glyph_ink(first)
    hits = []
    for y in range(0, max(0, height - glyph_height) + 1):
        for x in range(0, width - glyph_width + 1):
            cursor = x
            ok = True
            for char in text:
                glyph = font[char]
                char_width, _char_height, ink = glyph_ink(glyph)
                for dx, dy in ink:
                    if shades[(y + dy) * width + cursor + dx] != 3:
                        ok = False
                        break
                if not ok:
                    break
                cursor += char_width
            if ok and not _extra_ink(shades, width, height, font, text, x, y):
                hits.append((x, y))
    return hits[0] if len(hits) == 1 else None


def _extra_ink(shades, width, height, font, text, anchor_x, anchor_y):
    """Reject anchors whose glyph cells contain ink outside the glyph raster."""
    cursor = anchor_x
    for char in text:
        glyph = font[char]
        char_width, char_height, ink = glyph_ink(glyph)
        for dy in range(char_height):
            for dx in range(char_width):
                if (dx, dy) in ink:
                    continue
                py, px = anchor_y + dy, cursor + dx
                if 0 <= px < width and 0 <= py < height:
                    if shades[py * width + px] == 3:
                        return True
        cursor += char_width
    return False


def page_shades(resource):
    if resource.get('page'):
        path = ROOT / resource['page']
        require(path.is_file(), 'missing page PNG ' + str(path))
        width, height, shades = graphics_png.png_to_shades(path.read_bytes())
        return path, width, height, list(shades)
    require(resource.get('edit'), 'resource has neither page nor edit: ' + resource['id'])
    import page_edits
    base = load_base_rom()
    edit = page_edits.load_edit(resource)
    png = page_edits.render_png(resource, edit, base)
    width, height, shades = graphics_png.png_to_shades(png)
    return BUILD_PAGES / (resource['id'] + '.png'), width, height, list(shades)


_BASE_ROM = None


def load_base_rom():
    global _BASE_ROM
    if _BASE_ROM is None:
        path = ROOT / 'baserom.gb'
        require(path.is_file(), 'baserom.gb is required to rebuild edit-backed pages')
        _BASE_ROM = path.read_bytes()
    return _BASE_ROM


def render_entry(shades, width, record, translation, font, ink=3):
    """Paint one entry's typeset text onto a shade buffer."""
    out = list(shades)
    for _line, _col, x, y, _char, glyph, override in glyph_cells(record, translation, font):
        if override:
            for row_index, row in enumerate(override):
                for column, value in enumerate(row):
                    if value == '1':
                        out[(y + row_index) * width + x + column] = ink
            continue
        for dx, dy in glyph_ink(glyph)[2]:
            out[(y + dy) * width + x + dx] = ink
    return out


def erase_entry(shades, width, height, record, translation, font):
    """Remove one entry's ink, sampling the nearest background pixel per row."""
    out = list(shades)
    for _line, _col, x, y, _char, glyph, override in glyph_cells(record, translation, font):
        cells = ([(column, row) for row, values in enumerate(override)
                  for column, value in enumerate(values) if value == '1']
                 if override else glyph_ink(glyph)[2])
        for dx, dy in cells:
            px, py = x + dx, y + dy
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
    return out


def authoritative_entries():
    """Gallery/hint/HUD entries from the approved dev-workspace layout files."""
    entries = []
    gallery = read_json(GALLERY_JSON)
    for entry_id, record in gallery['entries'].items():
        entries.append({'id': entry_id, 'page': record['page'], 'mode': 'edit',
                        'font': gallery['font'], 'line_height': gallery['line_height'],
                        'anchor': record['anchor']})
    hints = read_json(HINT_JSON)
    for entry_id, record in hints['entries'].items():
        entry = {'id': entry_id, 'page': record['page'], 'mode': 'edit',
                 'font': hints['font'], 'line_height': hints['line_height'],
                 'positions': record['positions']}
        if record.get('overrides'):
            entry['overrides'] = record['overrides']
        entries.append(entry)
    hud = read_json(HUD_JSON)
    for page_id, entry_ids in hud['pages'].items():
        for entry_id in entry_ids:
            record = hud['entries'][entry_id]
            entries.append({'id': entry_id, 'page': page_id, 'mode': 'edit',
                            'font': hud['font'], 'line_height': hud['line_height'],
                            'anchor': record['anchor'], 'same_id_multiple_pages': True})
    return entries


def extract(translations=None, fonts=None):
    translations = translations or load_translations()
    fonts = fonts or load_fonts()
    manifest = common.load_manifest()
    resources = {entry['id']: entry for entry in manifest['resources']}
    cache = {}
    layout = {}
    manual = []

    def shades_for(page_id):
        if page_id not in cache:
            cache[page_id] = page_shades(resources[page_id])
        return cache[page_id]

    for page_id, entries in BUNDLE_PAGES:
        _path, width, height, shades = shades_for(page_id)
        for entry_id, typeset in entries:
            translation = translations[entry_id]['translation_zh_hans']
            record = {'id': entry_id, 'page': page_id, 'mode': 'page',
                      'font': '12px', 'line_height': 12}
            if typeset is not None:
                record['typeset'] = typeset
            anchor = find_anchor(shades, width, height, fonts['12px'],
                                 record.get('typeset', translation), 12)
            if anchor is None:
                manual.append((entry_id, page_id, 'not matched exactly'))
                continue
            record['anchor'] = {'x': anchor[0], 'y': anchor[1]}
            record['translation_sha256'] = hashlib.sha256(
                translation.encode('utf-8')).hexdigest()
            layout['%s:%s' % (page_id, entry_id)] = record

    for entry in authoritative_entries():
        entry_id = entry['id']
        translation = translations[entry_id]['translation_zh_hans']
        _path, width, height, shades = shades_for(entry['page'])
        if not match_entry(shades, width, height, entry, translation, fonts[entry['font']]):
            manual.append((entry_id, entry['page'], 'ink does not match pinned font'))
            continue
        entry['translation_sha256'] = hashlib.sha256(
            translation.encode('utf-8')).hexdigest()
        layout['%s:%s' % (entry['page'], entry_id)] = entry

    return {'layout': layout, 'manual': manual, 'pages': cache}


def write_layout(result, translations, fonts):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'format_version': 2,
        'font_sources': {name: str(spec['path'].relative_to(ROOT))
                         for name, spec in FONT_SPECS.items()},
        'pages': {},
        'entries': result['layout'],
    }
    # A page's base must remove *all* text on that page before it is stored.
    entries_by_page = {}
    for key, record in result['layout'].items():
        entries_by_page.setdefault(record['page'], []).append((key, record))
    for page_id, records in entries_by_page.items():
        if any(record['mode'] != 'page' for _key, record in records):
            continue
        _path, width, height, shades = result['pages'][page_id]
        base = list(shades)
        for _key, record in records:
            translation = translations[record['id']]['translation_zh_hans']
            base = erase_entry(base, width, height, record, translation,
                               fonts[record['font']])
        base_path = BASE_DIR / (page_id + '.png')
        base_path.write_bytes(graphics_png.shades_to_png(width, height, base))
        payload['pages'][page_id] = {
            'base_png': str(base_path.relative_to(ROOT)),
            'width': width,
            'height': height,
        }
    LAYOUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n',
                           encoding='utf-8')
    print('TEXT_LAYOUT=WROTE %s ENTRIES=%d PAGES=%d BASE_PAGES=%d'
          % (LAYOUT_JSON.relative_to(ROOT), len(result['layout']),
             len(entries_by_page), len(payload['pages'])))


def check(translations=None, fonts=None):
    translations = translations or load_translations()
    fonts = fonts or load_fonts()
    require(LAYOUT_JSON.is_file(), 'no layout yet; run extract --write')
    payload = read_json(LAYOUT_JSON)
    entries_by_page = {}
    for key, record in payload['entries'].items():
        entries_by_page.setdefault(record['page'], []).append((key, record))
    failures = []
    checked = 0
    for page_id, records in sorted(entries_by_page.items()):
        resource = next(item for item in common.load_manifest()['resources']
                        if item['id'] == page_id)
        _path, width, height, expected = page_shades(resource)
        if page_id in payload['pages']:
            base_shades = graphics_png.png_to_shades(
                (ROOT / payload['pages'][page_id]['base_png']).read_bytes())[2]
        else:
            base_shades = list(expected)
            for _key, record in records:
                base_shades = erase_entry(base_shades, width, height, record,
                                          translations[record['id']]['translation_zh_hans'],
                                          fonts[record['font']])
        rendered = list(base_shades)
        for _key, record in records:
            rendered = render_entry(rendered, width, record,
                                    translations[record['id']]['translation_zh_hans'],
                                    fonts[record['font']])
            checked += 1
        if list(rendered) != list(expected):
            differences = sum(1 for left, right in zip(rendered, expected)
                              if left != right)
            failures.append((page_id, differences))
    print('TEXT_RENDER=%s ENTRIES=%d PAGES=%d BASE_PAGES=%d'
          % ('PASS' if not failures else 'FAIL', checked, len(entries_by_page),
             len(payload['pages'])))
    for page_id, differences in failures:
        print('TEXT_DIFF=%s: %d pixels' % (page_id, differences), file=sys.stderr)
    return not failures


def render(translations=None, fonts=None, write=False):
    translations = translations or load_translations()
    fonts = fonts or load_fonts()
    payload = read_json(LAYOUT_JSON)
    entries_by_page = {}
    for key, record in payload['entries'].items():
        entries_by_page.setdefault(record['page'], []).append((key, record))
    BUILD_PAGES.mkdir(parents=True, exist_ok=True)
    written = []
    for page_id, records in sorted(entries_by_page.items()):
        resource = next(item for item in common.load_manifest()['resources']
                        if item['id'] == page_id)
        _path, width, height, expected = page_shades(resource)
        if page_id in payload['pages']:
            base_shades = graphics_png.png_to_shades(
                (ROOT / payload['pages'][page_id]['base_png']).read_bytes())[2]
        else:
            base_shades = list(expected)
            for _key, record in records:
                base_shades = erase_entry(base_shades, width, height, record,
                                          translations[record['id']]['translation_zh_hans'],
                                          fonts[record['font']])
        shades = list(base_shades)
        for _key, record in records:
            shades = render_entry(shades, width, record,
                                  translations[record['id']]['translation_zh_hans'],
                                  fonts[record['font']])
        if write:
            target = (ROOT / resource['page']) if resource.get('page') else (
                BUILD_PAGES / (page_id + '.png'))
            target.write_bytes(graphics_png.shades_to_png(width, height, shades))
            written.append((page_id, str(target.relative_to(ROOT))))
    print('TEXT_RENDERED=%d' % len(written) if write else 'TEXT_RENDER=CHECK_ONLY')
    for page_id, target in written:
        print('TEXT_PAGE=%s -> %s' % (page_id, target))
        if target.startswith('build/pages/'):
            print('NEXT=python 00_Tools/pages.py retile %s' % target)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('extract', 'check', 'render'))
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    translations = load_translations()
    fonts = load_fonts()
    try:
        if args.command == 'extract':
            result = extract(translations, fonts)
            print('TEXT_EXTRACT=PASS MATCHED=%d MANUAL=%d'
                  % (len(result['layout']), len(result['manual'])))
            for entry_id, page_id, reason in result['manual']:
                print('TEXT_MANUAL=%s (%s): %s' % (entry_id, page_id, reason))
            if args.write:
                write_layout(result, translations, fonts)
            return 0
        if args.command == 'check':
            return 0 if check(translations, fonts) else 1
        render(translations, fonts, write=args.write)
        return 0
    except (OSError, KeyError, ValueError, TextLayoutError) as exc:
        print('TEXT_LAYOUT=ERROR ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
