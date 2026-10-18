# SPDX-License-Identifier: MIT
"""Match recorded playthrough frames to localized pages.

Reads ``build/playthrough/index.json`` (written by tools/play_capture.py),
compares each frame's VRAM/BG map against the active page inventory, and
reports which pages were actually seen with exact tile/map bytes.

This is a local, PyBoy-based validation helper: it needs the recorded capture
directory (and the ROM/atlas bytes used to build the expected pages), but not
an emulator itself.  It does not run on the public CI.

Usage:
    PYTHONPATH=build/pylibs python tools/analyze_playthrough.py [--write]
"""
import argparse
import json
from pathlib import Path
import sys

import audit_pages
import common
import graphics_png

DEFAULT_DIR = common.ROOT / 'build' / 'playthrough'
DEFAULT_REPORT = common.ROOT / 'docs' / 'PLAYTHROUGH_AUDIT.md'
MAP_BASES = (0x9800, 0x9C00)


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def page_models(manifest, spec):
    """Expected bytes and match rules for every active page."""
    loaders = audit_pages.loader_sites(spec)
    roles = {r['id']: r.get('role', 'active') for r in spec['resources']}
    models = {}
    for entry in manifest['resources']:
        if not entry['referenced_by_current_localized_loaders']:
            continue
        if entry.get('bundle'):
            tiles = graphics_png.load_resource(common.ROOT / entry['source'],
                                               dict(entry['png']))
            width, height = entry['bundle']['width'], entry['bundle']['height']
            map_codes = graphics_png.png_to_tilemap(
                (common.ROOT / entry['bundle']['map_png']).read_bytes(), width, height)
            models[entry['id']] = {
                'kind': 'bundle',
                'label': entry['label'],
                'tiles': tiles,
                'map': list(map_codes),
                'width': width,
                'height': height,
                'destinations': sorted(set(loaders.get(entry['id'], {}).get('destinations', []))),
            }
        elif entry.get('edit') and entry['png'].get('mode') == graphics_png.TILEMAP_MODE:
            width, height = entry['png']['width'], entry['png']['height']
            map_codes = graphics_png.png_to_tilemap(
                (common.ROOT / entry['source']).read_bytes(), width, height)
            tileset = next(r for r in manifest['resources']
                           if r['id'] == entry['png']['tileset'])
            tiles = graphics_png.load_resource(common.ROOT / tileset['source'],
                                               dict(tileset['png']))
            models[entry['id']] = {
                'kind': 'tilemap',
                'label': entry['label'],
                'map': list(map_codes),
                'width': width,
                'height': height,
                'tiles': tiles,
            }
        elif entry.get('edit') and entry['png'].get('mode') == graphics_png.TILES_MODE:
            tiles = graphics_png.load_resource(common.ROOT / entry['source'],
                                               dict(entry['png']))
            models[entry['id']] = {
                'kind': 'sheet',
                'label': entry['label'],
                'tiles': tiles,
            }
    return models, roles


def map_ratio(captured, expected, width, height):
    same = total = 0
    for row in range(height):
        for column in range(width):
            same += captured[row * 32 + column] == expected[row * width + column]
            total += 1
    return same / total if total else 0.0


def title_row_shift(captured, expected, width, height):
    """Title content is placed at a vertical offset in the 32x32 map."""
    best = (0.0, 0)
    for shift in range(-32, 33):
        same = total = 0
        for row in range(height):
            target = row + shift
            if not 0 <= target < 32:
                continue
            for column in range(width):
                same += captured[target * 32 + column] == expected[row * width + column]
                total += 1
        if total and same / total > best[0]:
            best = (same / total, shift)
    return best


def match_capture(state, vram, models):
    best = None
    for page_id, model in models.items():
        if model['kind'] == 'bundle':
            if not model['destinations']:
                continue
            tile_ratio = 0.0
            tile_dest = None
            for dest in model['destinations']:
                offset = dest - 0x8000
                expected = model['tiles'][:min(len(model['tiles']), 0x1000)]
                live = vram[offset:offset + len(expected)]
                if not expected:
                    continue
                ratio = sum(1 for left, right in zip(expected, live) if left == right) / len(expected)
                if ratio > tile_ratio:
                    tile_ratio, tile_dest = ratio, dest
            ratio = 0.0
            shift = 0
            for base in MAP_BASES:
                captured = bytes(vram[base - 0x8000:base - 0x8000 + 1024])
                if page_id == 'rom_070000':
                    candidate_ratio, candidate_shift = title_row_shift(
                        captured, model['map'], model['width'], model['height'])
                else:
                    candidate_ratio, candidate_shift = (
                        map_ratio(captured, model['map'], model['width'], model['height']), 0)
                if candidate_ratio > ratio:
                    ratio, shift = candidate_ratio, candidate_shift
            score = 0.5 * tile_ratio + 0.5 * ratio
            candidate = {
                'page': page_id, 'kind': 'bundle', 'score': score,
                'tile_ratio': tile_ratio, 'map_ratio': ratio,
                'tile_dest': tile_dest, 'row_shift': shift,
                'identified': tile_ratio >= 0.999 and ratio >= 0.999,
            }
        elif model['kind'] == 'tilemap':
            ratio = 0.0
            for base in MAP_BASES:
                captured = bytes(vram[base - 0x8000:base - 0x8000 + 1024])
                ratio = max(ratio, map_ratio(captured, model['map'],
                                             model['width'], model['height']))
            prefix = model['tiles'][:min(len(model['tiles']), 512)]
            found = vram.find(prefix) if prefix else -1
            score = 0.8 * ratio + (0.2 if found >= 0 else 0.0)
            candidate = {
                'page': page_id, 'kind': 'tilemap', 'score': score,
                'tile_ratio': 1.0 if found >= 0 else 0.0, 'map_ratio': ratio,
                'tile_offset': None if found < 0 else 0x8000 + found,
                'identified': ratio >= 0.995 and found >= 0,
            }
        else:
            found = vram.find(model['tiles']) if model['tiles'] else -1
            score = 0.5 if found >= 0 else 0.0
            candidate = {
                'page': page_id, 'kind': 'sheet', 'score': score,
                'tile_ratio': 1.0 if found >= 0 else 0.0, 'map_ratio': 0.0,
                'tile_offset': None if found < 0 else 0x8000 + found,
                'identified': found >= 0,
            }
        if best is None or candidate['score'] > best['score']:
            best = candidate
    return best


def analyze(capture_dir):
    index_path = capture_dir / 'index.json'
    common.require(index_path.is_file(), 'missing capture index: ' + str(index_path))
    index = _load(index_path)
    manifest = common.load_manifest()
    spec = _load(common.ROOT / 'source' / 'change_surface.json')
    models, roles = page_models(manifest, spec)
    results = []
    seen = {}
    for meta in index['captures']:
        vram = (capture_dir / meta['vram']).read_bytes()
        candidate = match_capture(meta, vram, models)
        if candidate is None:
            continue
        candidate['frame'] = meta['frame']
        candidate['screen'] = meta['screen']
        results.append(candidate)
        if candidate['identified']:
            seen.setdefault(candidate['page'], []).append(candidate)
    active_pages = [page_id for page_id in models]
    coverage = []
    for page_id in active_pages:
        hits = seen.get(page_id, [])
        best = max(hits, key=lambda item: item['score']) if hits else None
        coverage.append({
            'page': page_id,
            'label': models[page_id]['label'],
            'kind': models[page_id]['kind'],
            'seen': bool(hits),
            'hits': len(hits),
            'first_frame': hits[0]['frame'] if hits else None,
            'last_frame': hits[-1]['frame'] if hits else None,
            'best_score': None if best is None else best['score'],
            'best_map_ratio': None if best is None else best['map_ratio'],
            'best_tile_ratio': None if best is None else best['tile_ratio'],
        })
    unknown = [r for r in results if not r['identified']]
    return {
        'index': index,
        'results': results,
        'coverage': coverage,
        'unknown_count': len(unknown),
        'capture_count': len(index['captures']),
    }


def render_report(analysis):
    lines = ['# 全程游玩运行时抽检', '']
    lines.append('由 `PYTHONPATH=build/pylibs python tools/analyze_playthrough.py --write` 生成。')
    lines.append('')
    index = analysis['index']
    lines.append('- ROM SHA-256：`%s`；帧数：%d；捕获：%d（每 %d 帧）'
                 % (index.get('rom_sha256', '?'), index.get('frames', 0),
                    analysis['capture_count'], index.get('interval_frames', 0)))
    active = [row for row in analysis['coverage']]
    seen = [row for row in active if row['seen']]
    missing = [row for row in active if not row['seen']]
    lines.append('- 活跃页面：%d；精确命中：%d；未命中：%d；未识别捕获：%d'
                 % (len(active), len(seen), len(missing), analysis['unknown_count']))
    lines.append('')
    lines.append('## 页面覆盖')
    lines.append('')
    lines.append('| 页面 | 类型 | 命中 | 首次帧 | 最后帧 | 最佳地图 | 最佳 tile |')
    lines.append('| --- | --- | ---: | ---: | ---: | ---: | ---: |')
    for row in active:
        lines.append('| `%s` | %s | %s | %s | %s | %s | %s |'
                     % (row['page'], row['kind'],
                        'YES' if row['seen'] else 'NO',
                        '-' if row['first_frame'] is None else row['first_frame'],
                        '-' if row['last_frame'] is None else row['last_frame'],
                        '-' if row['best_map_ratio'] is None else '%.3f' % row['best_map_ratio'],
                        '-' if row['best_tile_ratio'] is None else '%.3f' % row['best_tile_ratio']))
    lines.append('')
    lines.append('## 未命中页面')
    lines.append('')
    if missing:
        for row in missing:
            lines.append('- `%s`：%s' % (row['page'], row['label']))
    else:
        lines.append('- 无；所有活跃页面均被精确命中。')
    lines.append('')
    lines.append('## 未识别捕获')
    lines.append('')
    lines.append('- 共 %d 帧未达到精确阈值（通常是标题动画、转场、游戏过程、'
                 '精灵覆盖或页面动画帧），不据此判定失败。' % analysis['unknown_count'])
    lines.append('')
    lines.append('## 说明')
    lines.append('')
    lines.append('- bundle 页要求地图与 tile 块都 ≥0.999；tilemap 页要求地图 ≥0.995 且'
                 ' tileset 前缀在 VRAM 中出现；sheet 页要求整块图块在 VRAM 中出现。')
    lines.append('- 标题页允许纵向偏移匹配；其余页面按 BG map 基址 `0x9800` 的 32×32 网格比较。')
    lines.append('- 这是模拟器运行时抽检，不替代实机验证；未覆盖页面需检查是否真的没玩到，'
                 '还是采帧间隔/动画导致未命中。')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--capture-dir', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    analysis = analyze(args.capture_dir)
    if args.write:
        DEFAULT_REPORT.write_text(render_report(analysis), encoding='utf-8')
        print('PLAYTHROUGH_AUDIT_DOC=' + str(DEFAULT_REPORT))
    seen = sum(1 for row in analysis['coverage'] if row['seen'])
    print('PLAYTHROUGH_AUDIT=PASS PAGES=%d SEEN=%d MISSING=%d CAPTURES=%d UNKNOWN=%d'
          % (len(analysis['coverage']), seen,
             len(analysis['coverage']) - seen,
             analysis['capture_count'], analysis['unknown_count']))
    for row in analysis['coverage']:
        if not row['seen']:
            print('MISSING=%s (%s)' % (row['page'], row['label']))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            common.ProjectError) as exc:
        print('PLAYTHROUGH_AUDIT=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
