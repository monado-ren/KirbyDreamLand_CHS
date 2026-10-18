# SPDX-License-Identifier: MIT
"""Static VRAM / tile / map budget audit for the 48 localized pages.

The audit never runs the ROM.  It derives the page inventory from
``source/manifest.json`` and the loader destinations from
``source/change_surface.json``, then reports:

* tile block size vs. the 256-tile BG block (8 KiB VRAM / 384 tiles total);
* whether a bundle's map lands at 0x9800 after its tile block;
* map tile codes that fall outside the page's own tile block (baseline VRAM
  tiles that must already be loaded by the original code);
* packed-resource headroom (capacity - packed_size) and zero-slack resources;
* the loader sites and declared VRAM destinations for every page.

Hard failures are limited to things the build itself promises (capacity
overflow, corrupted resource metadata).  Layout/timing points that depend on
code outside the manifest are reported as warnings for manual/emulator review.

Usage:
    python tools/audit_pages.py [--check] [--write]
"""
import argparse
import json
from pathlib import Path
import sys

import common
import graphics_png

DEFAULT_SPEC = common.ROOT / 'source/change_surface.json'
DEFAULT_REPORT = common.ROOT / 'docs' / 'PAGE_BUDGET.md'
VRAM_START, VRAM_END = 0x8000, 0xA000
BG_MAP_START = 0x9800
BG_TILE_SLOTS = 256


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def loader_sites(spec):
    out = {}
    for site in spec['sites']:
        resource = site.get('resource')
        if not resource:
            continue
        entry = out.setdefault(resource, {'destinations': [], 'sites': []})
        entry['sites'].append(site['site'])
        for patch in site.get('patches', []):
            if patch['kind'] == 'loader.vram_base':
                entry['destinations'].append(patch['new'] << 8)
    return out


def _map_codes(entry):
    """Return the map tile codes for a bundle or tilemap resource, if any."""
    if entry.get('bundle'):
        width, height = entry['bundle']['width'], entry['bundle']['height']
        data = graphics_png.png_to_tilemap(
            (common.ROOT / entry['bundle']['map_png']).read_bytes(), width, height)
        return list(data), entry['bundle'].get('addressing', 'linear')
    if entry.get('png', {}).get('mode') == graphics_png.TILEMAP_MODE:
        width, height = entry['png']['width'], entry['png']['height']
        data = graphics_png.png_to_tilemap(
            (common.ROOT / entry['source']).read_bytes(), width, height)
        return list(data), entry['png'].get('addressing', 'linear')
    return None, None


def _tile_count(entry, manifest):
    png = entry.get('png', {})
    if entry.get('bundle'):
        return png.get('tile_count')
    if png.get('tile_count') is not None:
        return png['tile_count']
    tileset_id = png.get('tileset')
    if tileset_id:
        tileset = next((r for r in manifest['resources'] if r['id'] == tileset_id), None)
        if tileset:
            return tileset['png'].get('tile_count')
    return None


def audit(manifest=None, spec=None):
    manifest = manifest or common.load_manifest()
    spec = spec or _load(DEFAULT_SPEC)
    loaders = loader_sites(spec)
    by_id = {r['id']: r for r in manifest['resources']}
    roles = {r['id']: r.get('role', 'active') for r in spec['resources']}
    all_pages = [r for r in manifest['resources'] if r.get('bundle') or r.get('edit')]
    active = [r for r in manifest['resources']
              if r['referenced_by_current_localized_loaders']]
    pages = []
    warnings = []
    hard_errors = []

    for entry in all_pages:
        if entry.get('capacity', 0) < entry.get('packed_size', 0):
            hard_errors.append('%s: packed_size exceeds capacity' % entry['id'])
        decoded, packed = entry['decoded_size'], entry['packed_size']
        capacity = entry['capacity']
        slack = capacity - packed
        kind = 'resource'
        if entry.get('bundle'):
            kind = 'bundle'
        elif entry.get('edit'):
            kind = 'edit'
        elif entry.get('png', {}).get('mode') == graphics_png.TILEMAP_MODE:
            kind = 'tilemap'
        elif entry.get('png', {}).get('mode') == graphics_png.TILES_MODE:
            kind = 'tileset'
        tile_count = _tile_count(entry, manifest)
        map_codes, addressing = _map_codes(entry)
        external = None
        max_code = None
        unique_codes = None
        if map_codes is not None:
            max_code, unique_codes = max(map_codes), len(set(map_codes))
            if addressing == 'linear' and tile_count:
                external = sum(1 for code in map_codes if code >= tile_count)
        is_active = bool(entry['referenced_by_current_localized_loaders'])
        destinations = sorted(set(loaders.get(entry['id'], {}).get('destinations', [])))
        sites = loaders.get(entry['id'], {}).get('sites', [])
        tile_bytes = tile_count * 16 if tile_count else None
        map_span = None
        map_lot = None
        if destinations:
            dest = destinations[0]
            span = dest + decoded
            map_span = span
            if is_active:
                if span > VRAM_END:
                    warnings.append('%s: dest 0x%04X + %d B exceeds VRAM 0x%04X'
                                    % (entry['id'], dest, decoded, VRAM_END))
                if tile_bytes is not None:
                    map_lot = dest + tile_bytes
                    if map_lot != BG_MAP_START:
                        warnings.append('%s: tile block ends at 0x%04X, not BG map 0x%04X'
                                        % (entry['id'], map_lot, BG_MAP_START))
                if tile_count and tile_count > BG_TILE_SLOTS:
                    warnings.append('%s: %d tiles exceed one 256-tile BG block'
                                    % (entry['id'], tile_count))
        if external and is_active:
            warnings.append('%s: %d map cells reference baseline VRAM tiles (code >= %d)'
                            % (entry['id'], external, tile_count))
        pages.append({
            'id': entry['id'],
            'label': entry['label'],
            'kind': kind,
            'active': bool(entry['referenced_by_current_localized_loaders']),
            'role': roles.get(entry['id'], 'active'),
            'decoded': decoded,
            'packed': packed,
            'capacity': capacity,
            'slack': slack,
            'tile_count': tile_count,
            'map_codes': len(map_codes) if map_codes is not None else None,
            'unique_codes': unique_codes,
            'max_code': max_code,
            'addressing': addressing,
            'external': external,
            'destinations': destinations,
            'map_lot': map_lot,
            'map_span': map_span,
            'sites': sites,
        })
    pages.sort(key=lambda p: (not p['active'], p['kind'], p['id']))
    bundles = [p for p in pages if p['kind'] == 'bundle']
    edits = [p for p in pages if p['kind'] == 'edit']
    zero_slack = [p for p in pages if p['slack'] == 0 and p['active']]
    return {
        'pages': pages,
        'bundles': bundles,
        'edits': edits,
        'warnings': warnings,
        'hard_errors': hard_errors,
        'zero_slack': zero_slack,
        'active': len(active),
        'active_pages': sum(1 for p in pages if p['active']),
        'legacy_pages': sum(1 for p in pages if not p['active']),
    }


def _fmt_addr(value):
    return '-' if value is None else '0x%04X' % value


def render_report(result, manifest, spec):
    lines = []
    lines.append('# 页面 VRAM / tile / 地图预算审计')
    lines.append('')
    lines.append('由 `python tools/audit_pages.py --write` 生成；静态审计，不运行 ROM。')
    lines.append('')
    lines.append('## 汇总')
    lines.append('')
    lines.append('- 页面：%d（当前装载 %d，历史副本 %d）；整页 bundle：%d；基线+覆盖层页：%d'
                 % (len(result['pages']), result['active_pages'], result['legacy_pages'],
                    len(result['bundles']), len(result['edits'])))
    lines.append('- 当前装载的活跃资源：%d' % result['active'])
    lines.append('- 零 packed 余量资源：%d（`capacity == packed_size`）'
                 % len(result['zero_slack']))
    lines.append('- 硬错误：%d；警告：%d' % (len(result['hard_errors']), len(result['warnings'])))
    lines.append('- 全机 VRAM 8 KiB = 384 个 8×8 tile；BG 地图 32×32、每格 8 bit（最多 256 种 tile 编号）')
    lines.append('')
    lines.append('## 页面表')
    lines.append('')
    lines.append('| 页面 | 状态 | 类型 | tile 数 | 地图格/唯一码/最大码 | 外部基线码 | 装载目的 | tile块后地图落点 | decoded | packed/cap | 余量 |')
    lines.append('| --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | --- | ---: |')
    for page in result['pages']:
        map_text = '-'
        if page['map_codes'] is not None:
            map_text = '%d/%d/%s' % (page['map_codes'], page['unique_codes'],
                                     '0x%02X' % page['max_code'])
        lines.append('| `%s` | %s | %s | %s | %s | %s | %s | %s | %d | %d/%d | %d |'
                     % (page['id'], 'active' if page['active'] else 'legacy', page['kind'],
                        '-' if page['tile_count'] is None else page['tile_count'],
                        map_text,
                        '-' if page['external'] is None else page['external'],
                        ', '.join(_fmt_addr(d) for d in page['destinations']) or '-',
                        _fmt_addr(page['map_lot']),
                        page['decoded'], page['packed'], page['capacity'], page['slack']))
    lines.append('')
    lines.append('## 装载点')
    lines.append('')
    lines.append('| 页面 | 装载点 | 声明 VRAM 目的 | 说明 |')
    lines.append('| --- | --- | --- | --- |')
    for site in spec['sites']:
        resource = site.get('resource')
        if not resource:
            continue
        dests = []
        for patch in site.get('patches', []):
            if patch['kind'] == 'loader.vram_base':
                dests.append('0x%04X' % (patch['new'] << 8))
        lines.append('| `%s` | `%s` | %s | %s |'
                     % (resource, site['site'], ', '.join(dests) or '-',
                        site.get('purpose', '')))
    lines.append('')
    lines.append('## 警告与限制')
    lines.append('')
    if result['warnings']:
        for warning in result['warnings']:
            lines.append('- ' + warning)
    else:
        lines.append('- 无静态警告。')
    lines.append('')
    lines.append('说明：')
    lines.append('')
    lines.append('- “外部基线码”表示地图引用了本页 tile 块之外的 VRAM 图块（通常是原版关卡/图鉴共用图块），'
                 '不算错误，但换页/扩页时要保证这些基线图块确实已被装载。')
    lines.append('- “tile块后地图落点”按 `VRAM目的 + tile数×16` 估算；不等于 0x9800 的页面（如标题页）'
                 '使用自己的分段装载方式，必须逐页人工/模拟器确认，不能按单一连续块理解。')
    lines.append('- 加载时序（LCD off / VBlank）无法仅从 manifest 静态证明；扩页或改 loader 长度后必须重新验证。')
    lines.append('- 本审计不做实机验证；字节级构建 PASS 只保证 ROM 与既有发布一致。')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='exit 1 on hard errors')
    parser.add_argument('--write', action='store_true', help='write docs/PAGE_BUDGET.md')
    args = parser.parse_args(argv)
    manifest = common.load_manifest()
    spec = _load(DEFAULT_SPEC)
    result = audit(manifest, spec)
    if args.write:
        DEFAULT_REPORT.write_text(render_report(result, manifest, spec), encoding='utf-8')
        print('PAGE_AUDIT_DOC=' + str(DEFAULT_REPORT))
    print('PAGE_AUDIT=%s PAGES=%d BUNDLES=%d EDITS=%d ACTIVE=%d ZERO_SLACK=%d WARN=%d HARD=%d'
          % ('PASS' if not result['hard_errors'] else 'FAIL',
             len(result['pages']), len(result['bundles']), len(result['edits']),
             result['active'], len(result['zero_slack']),
             len(result['warnings']), len(result['hard_errors'])))
    for error in result['hard_errors']:
        print('HARD_ERROR=' + error, file=sys.stderr)
    if args.check and result['hard_errors']:
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('PAGE_AUDIT=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
