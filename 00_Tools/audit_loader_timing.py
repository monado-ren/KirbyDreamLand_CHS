# SPDX-License-Identifier: MIT
"""Static loader-cost audit: how much more data the localized loaders move.

Every localized loader site redirects a copy/decompress call to a new resource.
This tool decodes the *original* payload named by the unpatched loader operand
and compares its size with the localized resource, so the frame-cost change of a
loader can be reasoned about without an emulator.

The game's copy routine costs roughly one frame per ~28 tiles (16-byte units),
so a payload growth predicts a longer load — which is why frame-number-based
alignment (TAS, fixed frame offsets) is invalid for the localized ROM.

Usage:
    python 00_Tools/audit_loader_timing.py [--base baserom.gb] [--write]
"""
import argparse
import json
from pathlib import Path
import sys

import change_surface
import common
import hal_codec

ROOT = common.ROOT
DOC = ROOT / 'docs' / 'LOADER_TIMING.md'
TILE_BYTES = 16


def decoded_size(base, bank, cpu_address):
    """Decoded byte length of the original payload at (bank, cpu_address)."""
    offset = bank * 0x4000 + (cpu_address - 0x4000)
    if not 0 <= offset < len(base):
        return None
    try:
        data, _packed = hal_codec.decode(base[offset:])
    except Exception:
        return None
    return len(data)


def collect(base=None):
    base = base if base is not None else (ROOT / 'baserom.gb').read_bytes()
    spec = change_surface.load_spec()
    manifest = common.load_manifest()
    by_id = {entry['id']: entry for entry in manifest['resources']}
    rows = []
    for site in spec['sites']:
        if not site.get('kind', '').startswith('loader.'):
            continue
        resource_id = site.get('resource')
        if not resource_id or resource_id not in by_id:
            continue
        old_bank = None
        old_address = None
        for patch in site.get('patches', []):
            if patch['kind'] == 'loader.bank':
                old_bank = patch['old']
            elif patch['kind'] == 'loader.source_addr':
                old_address = (int(patch['old'], 16) if isinstance(patch['old'], str)
                               else patch['old'])
        if old_bank is None:
            continue
        if old_address is None:
            # The loader's source operand is unchanged; use the resource's CPU
            # address (title bundle keeps $4000, gallery tileset keeps $4000).
            old_address = by_id[resource_id]['cpu_address']
        old_size = decoded_size(base, old_bank, old_address)
        new_size = by_id[resource_id]['decoded_size']
        rows.append({
            'site': site['site'],
            'resource': resource_id,
            'label': by_id[resource_id]['label'],
            'old_bank': old_bank,
            'old_cpu_address': old_address,
            'old_decoded': old_size,
            'new_decoded': new_size,
            'delta': (new_size - old_size) if old_size is not None else None,
        })
    rows.sort(key=lambda row: (-(abs(row['delta']) if row['delta'] else 0), row['site']))
    return rows


def summarize(rows):
    known = [row for row in rows if row['old_decoded'] is not None]
    old_total = sum(row['old_decoded'] for row in known)
    new_total = sum(row['new_decoded'] for row in known)
    grown = [row for row in known if row['new_decoded'] > row['old_decoded']]
    return {
        'loaders': len(rows),
        'compared': len(known),
        'unresolved': len(rows) - len(known),
        'original_bytes': old_total,
        'localized_bytes': new_total,
        'delta_bytes': new_total - old_total,
        'grown_loaders': len(grown),
    }


def render_markdown(rows):
    stats = summarize(rows)
    lines = ['# 装载器成本（静态审计）', '',
             '由 `python 00_Tools/audit_loader_timing.py --write` 从 `baserom.gb` + 符号层生成。',
             '数字是 HAL 解压后的字节数；游戏每帧约搬 28 个图块（16 字节），因此字节增长',
             '可换算为装载帧数增长。**这不是模拟器实测**，但足以说明为什么汉化版的',
             '帧号不能按固定偏移对齐（TAS/逐帧截图）。', '',
             '```text',
             'LOADERS=%d COMPARED=%d ORIGINAL=%d LOCALIZED=%d DELTA=%+d (%.0f%%) GROWN=%d'
             % (stats['loaders'], stats['compared'], stats['original_bytes'],
                stats['localized_bytes'], stats['delta_bytes'],
                100.0 * stats['delta_bytes'] / stats['original_bytes']
                if stats['original_bytes'] else 0, stats['grown_loaders']),
             '```', '',
             '## 变大的装载器', '',
             '| site | 资源 | 原版 bank:地址 | 原版 decoded | 汉化 decoded | 增量 |',
             '| --- | --- | --- | ---: | ---: | ---: |']
    for row in rows:
        if not row['delta'] or row['delta'] <= 0:
            continue
        lines.append('| `%s` | `%s` | %d:`0x%04X` | %d | %d | **+%d** |'
                     % (row['site'], row['resource'], row['old_bank'],
                        row['old_cpu_address'], row['old_decoded'],
                        row['new_decoded'], row['delta']))
    lines += ['', '## 未变的装载器', '',
              '| site | 资源 | decoded |', '| --- | --- | ---: |']
    for row in rows:
        if row['delta'] == 0:
            lines.append('| `%s` | `%s` | %d |'
                         % (row['site'], row['resource'], row['new_decoded']))
    lines += ['', '## 说明', '',
              '- 原版载荷位置由未打补丁的 loader 操作数（bank + 源地址）确定；',
              '- 汉化载荷大小取 `04_Data/manifest.json` 的 `decoded_size`；',
              '- 标题/配置/失败页从 0x9800 改到 0x8800/0x9000 后，整包携带了更多图块，',
              '  这是字节增长的来源；代码本身没有变慢（VBlank 补丁与装载循环无关）。',
              '']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base', type=Path, help='Rev1 ROM (default: baserom.gb)')
    parser.add_argument('--write', action='store_true', help='write docs/LOADER_TIMING.md')
    args = parser.parse_args(argv)
    base = args.base.read_bytes() if args.base else (ROOT / 'baserom.gb').read_bytes()
    rows = collect(base)
    stats = summarize(rows)
    print('LOADERS=%d COMPARED=%d ORIGINAL=%d LOCALIZED=%d DELTA=%+d GROWN=%d'
          % (stats['loaders'], stats['compared'], stats['original_bytes'],
             stats['localized_bytes'], stats['delta_bytes'], stats['grown_loaders']))
    if args.write:
        DOC.write_text(render_markdown(rows), encoding='utf-8')
        print('LOADER_TIMING=WROTE ' + str(DOC.relative_to(ROOT)))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('LOADER_TIMING=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
