# SPDX-License-Identifier: MIT
"""Reverse audit: prove each page's PNG is the thing actually stored in the ROM.

`build.py` constructs the ROM from sources, so a passing `verify.py` only shows
that one particular build is reproducible.  It does not show that the bytes
sitting in the shipped ROM still decode back into the page sources under
`03_Image/`, which is what "the PNG is the source of truth" claims.

This tool walks the other direction for every active resource: take the packed
stream at the resource's ROM offset, HAL-decode it, and compare it with the bytes
re-derived from the page/graphic sources.  A mismatch means the ROM and the
editable sources have drifted apart.

The check needs no emulator, so it is fast and runs in CI.

Usage:
    python 00_Tools/audit_rom_pages.py [--rom ROM] [--write]
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import common
import graphics_png
import hal_codec

ROOT = common.ROOT
DOC = ROOT / 'docs' / 'ROM_PAGES.md'


def expected_raw(entry):
    """Bytes this resource should decode to, derived from its editable sources."""
    raw = graphics_png.load_resource(common.resource_path(entry['source']),
                                     dict(entry['png']))
    bundle = entry.get('bundle')
    if bundle is not None:
        raw = raw + graphics_png.png_to_tilemap(
            common.resource_path(bundle['map_png']).read_bytes(),
            bundle['width'], bundle['height'])
    return raw


def collect(rom_path=None):
    rom_path = Path(rom_path) if rom_path else (ROOT / 'KirbyDreamLand_CHS-Monado.gb')
    rom = rom_path.read_bytes()
    manifest = common.load_manifest()
    rows = []
    for entry in manifest['resources']:
        at = entry['offset']
        expected = expected_raw(entry)
        packed = bytes(rom[at:at + entry['packed_size']])
        row = {
            'id': entry['id'],
            'label': entry['label'],
            'group': group_of(entry['label']),
            'offset': at,
            'decoded_expected': len(expected),
            'declared_decoded': entry['decoded_size'],
            'packed_size': entry['packed_size'],
        }
        try:
            decoded, consumed = hal_codec.decode(packed)
        except Exception as exc:                     # noqa: BLE001 - report as row data
            row.update(ok=False, reason='decode failed: %s' % exc)
            rows.append(row)
            continue
        row['packed_consumed'] = consumed
        row['decoded_actual'] = len(decoded)
        problems = []
        if decoded != expected:
            first = next((i for i, (a, b) in enumerate(zip(decoded, expected)) if a != b),
                         min(len(decoded), len(expected)))
            problems.append('decoded bytes differ from page source at offset %d' % first)
        if len(decoded) != entry['decoded_size']:
            problems.append('decoded %d bytes, manifest declares %d'
                            % (len(decoded), entry['decoded_size']))
        if consumed != entry['packed_size']:
            problems.append('HAL stream consumed %d bytes, manifest declares %d'
                            % (consumed, entry['packed_size']))
        digest = hashlib.sha256(decoded).hexdigest()
        if digest != entry['decoded_sha256']:
            problems.append('decoded SHA-256 differs from manifest')
        if hashlib.sha256(expected).hexdigest() != entry['decoded_sha256']:
            problems.append('page source SHA-256 differs from manifest')
        row.update(decoded_sha256=digest, ok=not problems, problems=problems)
        rows.append(row)
    return rows, hashlib.sha256(rom).hexdigest()


# Gallery pages are a tileset + tilemap pair per character group.  The hint
# pages reuse the same loader shape but belong to the ending flow, so they are
# reported separately.
GALLERY_LABELS = {
    'ending_034000', 'ending_0345c0', 'ending_0346fb', 'ending_034cb4',
    'ending_034dc0', 'ending_03535c', 'ending_03543e', 'ending_035987',
    'ending_035a89', 'ending_035fd2', 'ending_036063', 'ending_036553',
    'ending_036658', 'ending_036b80', 'ending_036c7c', 'ending_03717d',
    'ending_03729b', 'ending_03779c', 'ending_038000', 'ending_0378cc',
    'ending_038582', 'ending_038ac6', 'ending_038bf3', 'ending_03911e',
    'ending_039206', 'ending_039707', 'ending_039820', 'ending_039be1',
}
HINT_LABELS = {'ending_03adda', 'ending_03be31', 'ending_039cbf', 'ending_03acec'}


def group_of(label):
    """Feature bucket for one resource, used by the per-feature report."""
    if label in GALLERY_LABELS:
        return 'gallery'
    if label in HINT_LABELS:
        return 'ending_hint'
    if label == 'ending_sprites':
        return 'ending_sprites'
    if label.startswith('stage_'):
        return 'stage_intro'
    return 'other'


def summarize(rows):
    bad = [row for row in rows if not row['ok']]
    return {
        'resources': len(rows),
        'passed': len(rows) - len(bad),
        'failed': len(bad),
        'decoded_bytes': sum(row.get('decoded_actual') or 0 for row in rows),
        'packed_bytes': sum(row['packed_size'] for row in rows),
    }


def verify_gallery_pairs(rows):
    """Check the 14 gallery pages pair a tileset with its tilemap correctly.

    The gallery loader points at a tileset for the character art and a tilemap
    for the caption/layout.  Both halves must decode back into their sources, and
    the tilemap must actually reference the paired tileset's tile numbers, so a
    swapped or misdirected pointer would be caught here.
    """
    manifest = common.load_manifest()
    by_id = {entry['id']: entry for entry in manifest['resources']}
    by_offset = {row['offset']: row for row in rows}
    problems = []
    pairs = []
    for entry in manifest['resources']:
        tileset = entry.get('png', {}).get('tileset')
        if not tileset or group_of(entry['label']) != 'gallery':
            continue
        tilemap_row = by_offset.get(entry['offset'])
        tileset_entry = by_id.get(tileset)
        tileset_row = by_offset.get(tileset_entry['offset']) if tileset_entry else None
        label = '%s + %s' % (tileset, entry['id'])
        if tilemap_row is None or tileset_row is None:
            problems.append('%s: missing ROM row for one half' % label)
            continue
        if not tilemap_row['ok'] or not tileset_row['ok']:
            problems.append('%s: one half failed the byte check' % label)
            continue
        codes = graphics_png.png_to_tilemap(
            common.resource_path(entry['source']).read_bytes(),
            entry['png']['width'], entry['png']['height'])
        tile_count = tileset_entry['png']['tile_count']
        referenced = sorted({code for code in codes})
        outside = [code for code in referenced if code >= tile_count]
        pairs.append({
            'tileset': tileset, 'tilemap': entry['id'], 'label': entry['label'],
            'tileset_tiles': tile_count, 'map_cells': len(codes),
            'distinct_codes': len(referenced),
            'external_codes': len(outside),
        })
        if outside:
            problems.append('%s: %d map codes reference tiles outside the paired '
                            'tileset (>= %d)' % (label, len(outside), tile_count))
    return pairs, problems


def render_markdown(rows, rom_sha):
    stats = summarize(rows)
    lines = ['# ROM → 页面反向解包验证', '',
             '由 `python 00_Tools/audit_rom_pages.py --write` 生成。', '',
             '构建方向是「页面源 PNG → ROM」，这里验证反方向：**从 ROM 取出压缩流，',
             '解包后必须与页面源重新导出的字节完全一致**。任一处不一致都说明 ROM 与',
             '可编辑源已经脱节，而单纯核对 ROM 哈希发现不了这种问题。', '',
             '```text',
             'ROM_PAGES=%s RESOURCES=%d PASS=%d FAIL=%d DECODED=%d PACKED=%d'
             % ('PASS' if stats['failed'] == 0 else 'FAIL', stats['resources'],
                stats['passed'], stats['failed'], stats['decoded_bytes'],
                stats['packed_bytes']),
             '```', '',
             '- ROM SHA-256：`%s`' % rom_sha, '',
             '| 资源 | 说明 | ROM 偏移 | decoded | packed | 结果 |',
             '| --- | --- | --- | ---: | ---: | --- |']
    for row in rows:
        status = '✅' if row['ok'] else '❌ ' + '；'.join(row.get('problems', []))
        lines.append('| `%s` | %s | `0x%05X` | %d | %d | %s |'
                     % (row['id'], row['label'], row['offset'],
                        row.get('decoded_actual') or 0, row['packed_size'], status))
    pairs, pair_problems = verify_gallery_pairs(rows)
    lines += ['', '## 图鉴 14 页配对', '',
              '图鉴每页由一个图块集（角色美术）加一个地图（文字排版）组成；',
              '两半都必须能反解，且地图只能引用本页图块集里的编号，',
              '所以指针错位或两半互换都会在这里暴露。', '',
              '| 图块集 | 地图 | 说明 | 图块数 | 地图格数 | 不同码 | 越界码 |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for pair in pairs:
        lines.append('| `%s` | `%s` | %s | %d | %d | %d | %d |'
                     % (pair['tileset'], pair['tilemap'], pair['label'],
                        pair['tileset_tiles'], pair['map_cells'],
                        pair['distinct_codes'], pair['external_codes']))
    groups = {}
    for row in rows:
        bucket = groups.setdefault(row['group'], [0, 0])
        bucket[0] += 1
        bucket[1] += 1 if row['ok'] else 0
    lines += ['', '## 按功能分组', '', '| 分组 | 资源 | 通过 |', '| --- | ---: | ---: |']
    for name in sorted(groups):
        total, passed = groups[name]
        lines.append('| %s | %d | %d |' % (name, total, passed))
    issues = [row for row in rows if not row['ok']] + [
        {'id': 'pair', 'problems': [problem]} for problem in pair_problems]
    lines += ['', '## 问题', '']
    if issues:
        for row in issues:
            lines.append('- `%s`：%s' % (row['id'], '；'.join(row.get('problems', []))))
    else:
        lines.append('- 无。')
    lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--write', action='store_true',
                        help='rewrite docs/ROM_PAGES.md')
    parser.add_argument('--write-check', action='store_true',
                        help='fail if docs/ROM_PAGES.md is stale')
    args = parser.parse_args(argv)
    rows, sha = collect(args.rom)
    stats = summarize(rows)
    print('ROM_PAGES=%s RESOURCES=%d PASS=%d FAIL=%d DECODED=%d PACKED=%d'
          % ('PASS' if stats['failed'] == 0 else 'FAIL', stats['resources'],
             stats['passed'], stats['failed'], stats['decoded_bytes'],
             stats['packed_bytes']))
    for row in rows:
        if not row['ok']:
            print('  FAIL %s: %s' % (row['id'], '；'.join(row.get('problems', []))),
                  file=sys.stderr)
    markdown = render_markdown(rows, sha)
    if args.write:
        DOC.write_text(markdown, encoding='utf-8')
        print('ROM_PAGES=WROTE ' + str(DOC.relative_to(ROOT)))
    if args.write_check:
        current = DOC.read_text(encoding='utf-8') if DOC.is_file() else None
        if current != markdown:
            print('ROM_PAGES=STALE ' + str(DOC.relative_to(ROOT)), file=sys.stderr)
            return 1
        print('ROM_PAGES=DOC_CURRENT ' + str(DOC.relative_to(ROOT)), file=sys.stderr)
    return 0 if stats['failed'] == 0 else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('ROM_PAGES=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
