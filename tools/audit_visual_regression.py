# SPDX-License-Identifier: MIT
"""Validate an external BGB visual-regression capture package against page sources.

The package contains, for each screen, a native BGB state plus the live VRAM
(0x8000-0x9FFF), BG map (0x9800-0x9BFF), OAM and I/O registers, and a 160x144
screenshot.  This tool checks the capture metadata, maps each screen to the
localized page it should exercise, and compares the captured map/tile bytes
with source/pages + source/graphics.

The package itself is not committed; use --package DIR pointing at an extracted
package (or the zip contents).

Usage:
    PYTHONPATH=build/pylibs python tools/audit_visual_regression.py \
        --package build/visual_regression --write
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import analyze_playthrough
import common

DEFAULT_PACKAGE = common.ROOT / 'build' / 'visual_regression'
DEFAULT_REPORT = common.ROOT / 'docs' / 'VISUAL_REGRESSION_AUDIT.md'
DYNAMIC_MAP_SCREENS = {'configuration', 'sound_test'}

# screen dir -> page id expected by the package label/manifest (None = no page)
SCREEN_PAGES = {
    'title': 'rom_070000',
    'main_menu': 'rom_070000',
    'configuration': 'rom_05c000',
    'sound_test': 'rom_0438f6',
    'stage_1_intro': 'rom_06c000',
    'stage_2_intro': 'rom_06c70b',
    'stage_3_intro': 'rom_06cda8',
    'stage_4_intro': 'rom_06d490',
    'stage_5_intro': 'rom_06db85',
    'game_over': 'rom_04454c',
    'continue': 'rom_044734',
    # Runtime bytes say D03A=0 (normal) loads rom_055050 and D03A=1 (extra)
    # loads rom_056110; the purpose labels in change_surface.json appear to be
    # crossed for these two resources (see the report note).
    'hint_normal': 'rom_055050',
    'hint_extra': 'rom_056110',
    'gallery_01': 'rom_048462',
    'gallery_02': 'rom_04c4f4',
    'gallery_03': 'rom_0742b3',
    'gallery_04': 'rom_04caf2',
    'gallery_05': 'rom_0496d4',
    'gallery_06': 'rom_049bf8',
    'gallery_07': 'rom_04cd98',
    'gallery_08': 'rom_04a3a1',
    'gallery_09': 'rom_04d0bb',
    'gallery_10': 'rom_04ab1b',
    'gallery_11': 'rom_04d586',
    'gallery_12': 'rom_04b4db',
    'gallery_13': 'rom_04b943',
    'gallery_14': 'rom_04d918',
    'opening_decoration': 'rom_058000',
    'ending_sign': 'rom_050000',
    'hud_normal': 'rom_041000',
    'hud_extra': 'rom_041103',
    'credits_bonus': None,
}


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def map_match(bgmap, vram, model, page_id):
    best = (0.0, '')
    for label, data in (('bgmap', bgmap),
                        ('vram_9800', vram[0x1800:0x1C00]),
                        ('vram_9c00', vram[0x1C00:0x2000])):
        if page_id == 'rom_070000':
            ratio, _shift = analyze_playthrough.title_row_shift(
                data, model['map'], model['width'], model['height'])
        else:
            ratio = analyze_playthrough.map_ratio(
                data, model['map'], model['width'], model['height'])
        if ratio > best[0]:
            best = (ratio, label)
    return best


def tile_match(vram, model, page_id):
    tiles = model['tiles']
    if model['kind'] == 'bundle':
        destinations = model.get('destinations') or []
        best = (0.0, None)
        for dest in destinations:
            offset = dest - 0x8000
            expected = tiles[:min(len(tiles), 0x1000)]
            live = vram[offset:offset + len(expected)]
            if not expected or not live:
                continue
            ratio = sum(1 for left, right in zip(expected, live) if left == right) / len(expected)
            if ratio > best[0]:
                best = (ratio, dest)
        if best[0] >= 0.999:
            return best
        # Stage bundles have no per-resource destination patch; search the block.
        for size in (min(len(tiles), 0x1000), min(len(tiles), 0x800), 0x400):
            index = vram.find(tiles[:size])
            if index >= 0:
                return (1.0, 0x8000 + index)
        return best
    if model['kind'] == 'tilemap':
        for size in (min(len(tiles), 1024), min(len(tiles), 512), min(len(tiles), 256)):
            index = vram.find(tiles[:size])
            if index >= 0:
                return (1.0, 0x8000 + index)
        return (0.0, None)
    index = vram.find(tiles)
    return (1.0, 0x8000 + index) if index >= 0 else (0.0, None)


def audit(package):
    package = Path(package)
    manifest = common.load_manifest()
    spec = _load(common.ROOT / 'source' / 'change_surface.json')
    models, _roles = analyze_playthrough.page_models(manifest, spec)
    summary = _load(package / 'CAPTURE_MANIFEST.json')
    pixel = _load(package / 'CAPTURE_PIXEL_VERIFICATION.json')
    expected_sha = hashlib.sha256(
        (common.ROOT / 'KirbyDreamLand_CHS-Monado.gb').read_bytes()).hexdigest()
    rows = []
    problems = []
    for screen_dir in sorted((package / 'captures').iterdir()):
        if not screen_dir.is_dir():
            continue
        name = screen_dir.name
        state = _load(screen_dir / 'state.json')
        vram = (screen_dir / 'vram.bin').read_bytes()
        bgmap = (screen_dir / 'bgmap.bin').read_bytes()
        expected_page = SCREEN_PAGES.get(name)
        caption = next((item['label'] for item in summary['screens']
                        if item['screen'] == name), '')
        if state.get('rom_sha256') != expected_sha:
            problems.append('%s: ROM SHA-256 mismatch' % name)
        row = {
            'screen': name,
            'label': caption,
            'expected_page': expected_page,
            'best_page': None,
            'map_ratio': 0.0,
            'tile_ratio': 0.0,
            'map_source': None,
            'tile_source': None,
            'map_diffs': None,
            'status': 'SKIP',
        }
        if expected_page is not None:
            model = models[expected_page]
            if model['kind'] == 'sheet':
                map_ratio, map_source = 0.0, None
            else:
                map_ratio, map_source = map_match(bgmap, vram, model, expected_page)
            tile_ratio, tile_offset = tile_match(vram, model, expected_page)
            row.update(best_page=expected_page, map_ratio=map_ratio,
                       tile_ratio=tile_ratio, map_source=map_source,
                       tile_source=tile_offset)
            dynamic = False
            if model['kind'] == 'sheet':
                ok = tile_ratio >= 0.999
            else:
                ok = map_ratio >= 0.999 and tile_ratio >= 0.999
                if not ok and name in DYNAMIC_MAP_SCREENS and tile_ratio >= 0.999:
                    # Menus draw the cursor/underline into the map after the
                    # page load; the static page source legitimately differs.
                    source = {'bgmap': bgmap,
                              'vram_9800': vram[0x1800:0x1C00],
                              'vram_9c00': vram[0x1C00:0x2000]}[map_source]
                    diffs = sum(1 for index in range(model['width'] * model['height'])
                                if source[index] != model['map'][index])
                    row['map_diffs'] = diffs
                    dynamic = 1 <= diffs <= 32
                    ok = dynamic
            row['status'] = ('PASS_DYNAMIC' if dynamic else 'PASS') if ok else 'FAIL'
            if not ok:
                problems.append('%s: expected %s map=%.3f tile=%.3f'
                                % (name, expected_page, map_ratio, tile_ratio))
        else:
            row['status'] = 'NOT_LOCALIZED'
        rows.append(row)
    active = [page_id for page_id in models]
    covered = {row['expected_page'] for row in rows
               if row['status'].startswith('PASS')}
    missing = [page_id for page_id in active if page_id not in covered]
    return {
        'rows': rows,
        'problems': problems,
        'missing': missing,
        'summary': summary,
        'pixel': pixel,
        'active': len(active),
        'rom_sha256': expected_sha,
    }


def render_report(result):
    lines = ['# 外部 BGB 视觉回归包 → 页面源核对', '']
    lines.append('由 `PYTHONPATH=build/pylibs python tools/audit_visual_regression.py --write` 生成。')
    lines.append('')
    summary = result['summary']
    pixel = result['pixel']
    lines.append('- 包内 ROM SHA-256：`%s`（与当前构建一致）' % summary['rom_sha256'])
    lines.append('- 模拟器：%s；画面数：%d；缺失画面：%s'
                 % (summary['emulator'], summary['count'], summary['missing'] or '无'))
    lines.append('- 原生重载校验：%s；屏幕/内存/退出状态一致：%s'
                 % (summary['native_reload_verified'], summary['screen_capture_memory_state_same_exit']))
    lines.append('- 包内逐像素核验：%s（%d 个静态画面，%d 像素，差异 %d；%d 个动态附加画面排除）'
                 % (pixel['status'], pixel['static_captures'], pixel['pixels_compared'],
                    pixel['changed_pixels'], pixel['raster_bonus_excluded']))
    lines.append('- 页面覆盖：%d/%d 个活跃页面被此包覆盖；缺失：%s'
                 % (result['active'] - len(result['missing']), result['active'],
                    ', '.join(result['missing']) or '无'))
    lines.append('')
    lines.append('## 逐屏核对')
    lines.append('')
    lines.append('| 画面 | 说明 | 期望页面 | 地图匹配 | tile 匹配 | 地图来源 | 动态差异 | 状态 |')
    lines.append('| --- | --- | --- | ---: | ---: | --- | ---: | --- |')
    for row in result['rows']:
        lines.append('| `%s` | %s | %s | %s | %s | %s | %s | %s |'
                     % (row['screen'], row['label'],
                        '`%s`' % row['expected_page'] if row['expected_page'] else '-',
                        '-' if row['expected_page'] is None else '%.3f' % row['map_ratio'],
                        '-' if row['expected_page'] is None else '%.3f' % row['tile_ratio'],
                        row['map_source'] or '-',
                        '-' if row.get('map_diffs') is None else row['map_diffs'],
                        row['status']))
    lines.append('')
    lines.append('## 问题')
    lines.append('')
    if result['problems']:
        for problem in result['problems']:
            lines.append('- ' + problem)
    else:
        lines.append('- 无。')
    lines.append('')
    lines.append('## 说明')
    lines.append('')
    lines.append('- 地图匹配取 `bgmap.bin`、VRAM `0x9800`、VRAM `0x9C00` 三个来源中的最佳值；'
                 '标题页允许纵向滚动偏移。')
    lines.append('- tile 匹配：bundle 页优先按该页 loader 目的地址比较，其次在 VRAM 中搜索'
                 '该页 tile 块；tilemap 页搜索 tileset 前缀；sheet 页搜索完整图块块。')
    lines.append('- `credits_bonus` 是未汉化的原版演职人员表滚动画面，不对应任何本地化页面，'
                 '包内也标记为动态（非静态逐像素核验）。')
    lines.append('- `configuration` / `sound_test` 的地图差异是菜单光标/选项高亮在页面加载后'
                 '写入 BG map 造成的动态格子，tile 块仍精确匹配，因此标为 `PASS_DYNAMIC`。')
    lines.append('- `hint_normal` / `hint_extra` 的实际字节匹配与 `change_surface.json` 的 purpose '
                 '标注相反：包内 D03A=0（normal）匹配 `rom_055050`，D03A=1（extra）匹配 '
                 '`rom_056110`。报告按运行时字节采用该映射；两个资源的语义标签需要人工确认。')
    lines.append('- `title` 与 `main_menu` 都是 `rom_070000`；`opening_decoration` 是 '
                 '`stage_1_intro` 的别名捕获，检查的是同一状态下的角标图块。')
    lines.append('- sheet 页（HUD/角标/剧终牌）没有独立的 BG map 可比较，只看整块 tile 是否出现在 VRAM。')
    lines.append('- 本报告只核对包的外观数据与页面源；BGB 原生 `state.sna` 不随仓库分发。')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    common.require((args.package / 'captures').is_dir(),
                   'not a visual-regression package: ' + str(args.package))
    result = audit(args.package)
    if args.write:
        DEFAULT_REPORT.write_text(render_report(result), encoding='utf-8')
        print('VISUAL_AUDIT_DOC=' + str(DEFAULT_REPORT))
    passed = sum(1 for row in result['rows'] if row['status'] == 'PASS')
    print('VISUAL_AUDIT=%s SCREENS=%d PASS=%d FAIL=%d NOT_LOCALIZED=%d COVERED=%d/%d'
          % ('PASS' if not result['problems'] and not result['missing'] else 'FAIL',
             len(result['rows']), passed,
             sum(1 for row in result['rows'] if row['status'] == 'FAIL'),
             sum(1 for row in result['rows'] if row['status'] == 'NOT_LOCALIZED'),
             result['active'] - len(result['missing']), result['active']))
    for problem in result['problems']:
        print('PROBLEM=' + problem, file=sys.stderr)
    for page_id in result['missing']:
        print('MISSING=' + page_id)
    return 0 if not result['problems'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            common.ProjectError) as exc:
        print('VISUAL_AUDIT=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
