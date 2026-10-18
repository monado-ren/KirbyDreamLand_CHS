# SPDX-License-Identifier: MIT
"""How much of the localized loader growth is redundant payload?

Loader cost grew because five bundle pages replaced the original map-only payload
with full tile blocks (see ``docs/LOADER_TIMING.md``).  This audit asks whether
that payload could shrink without changing what the screen looks like:

* ``unused``  - tiles the page's own BG map never references;
* ``dedupe``  - identical 16-byte blocks stored more than once;
* ``compact`` - remap the BG map onto only the tiles it references, which keeps
  the rendered page pixel-identical but renumbers VRAM tiles.

``compact`` is mechanically possible, but the BG map byte *is* the VRAM tile
index, so renumbering can break anything else that pokes those indices (OBJ
sprites, animated tiles, partial map updates).  This tool reports the size win
and proves page equivalence; it does not apply the change.

Usage:
    python 00_Tools/audit_loader_payload.py [--write]
"""
import argparse
import json
from pathlib import Path
import sys

import common
import graphics_png as gp
import hal_codec
import page_image

ROOT = common.ROOT
DOC = ROOT / 'docs' / 'LOADER_PAYLOAD.md'

# Bundle resources whose decoded payload grew versus the original loader operand.
GROWN = ('rom_070000', 'rom_05c000', 'rom_0438f6', 'rom_04454c', 'rom_044734')


def analyse(manifest):
    by_id = {entry['id']: entry for entry in manifest['resources']}
    rows = []
    for resource_id in GROWN:
        entry = by_id[resource_id]
        bundle = entry['bundle']
        tiles = gp.load_resource(Path(ROOT / entry['source']), dict(entry['png']))
        tile_count = len(tiles) // 16
        blocks = [tiles[16 * index:16 * (index + 1)] for index in range(tile_count)]
        tilemap = gp.load_resource(
            Path(ROOT / bundle['map_png']),
            {'mode': gp.TILEMAP_MODE, 'width': bundle['width'],
             'height': bundle['height'], 'addressing': bundle['addressing']})
        codes = sorted({code for code in tilemap if code < tile_count})
        used = set(codes)
        blank = sum(1 for index in range(tile_count)
                    if index not in used and blocks[index] == bytes(16))
        unique = len(set(blocks))
        # Compact: one tile per distinct referenced block, map renumbered.
        order = {}
        kept = []
        for code in codes:
            block = blocks[code]
            if block not in order:
                order[block] = len(kept)
                kept.append(block)
        remapped = bytes(order[blocks[code]] if code < tile_count else code
                         for code in tilemap)
        original_page = page_image.page_png(
            tiles, bytes(tilemap), bundle['width'], bundle['height'],
            bundle['addressing'], True)
        compact_page = page_image.page_png(
            b''.join(kept), remapped, bundle['width'], bundle['height'],
            bundle['addressing'], True)
        compact_decoded = len(kept) * 16 + len(tilemap)
        rows.append({
            'id': resource_id,
            'label': entry['label'],
            'tile_count': tile_count,
            'referenced_tiles': len(used),
            'unused_tiles': tile_count - len(used),
            'blank_unused': blank,
            'duplicate_tiles': tile_count - unique,
            'decoded': entry['decoded_size'],
            'packed': entry['packed_size'],
            'dedupe_decoded': (unique + len(tilemap) // 16 or unique) * 16 + len(tilemap),
            'compact_tiles': len(kept),
            'compact_decoded': compact_decoded,
            'compact_packed': len(hal_codec.pack(b''.join(kept) + remapped)),
            'page_identical': original_page == compact_page,
        })
    return rows


def summarize(rows):
    decoded = sum(row['decoded'] for row in rows)
    compact = sum(row['compact_decoded'] for row in rows)
    return {
        'pages': len(rows),
        'decoded': decoded,
        'compact_decoded': compact,
        'saving': decoded - compact,
        'saving_pct': 100.0 * (decoded - compact) / decoded if decoded else 0,
        'all_pages_identical': all(row['page_identical'] for row in rows),
        'unused_tiles': sum(row['unused_tiles'] for row in rows),
        'duplicate_tiles': sum(row['duplicate_tiles'] for row in rows),
    }


def render_markdown(rows):
    stats = summarize(rows)
    lines = ['# 装载载荷与可压缩空间', '',
             '由 `python 00_Tools/audit_loader_payload.py --write` 生成。配套阅读',
             '[装载器成本](LOADER_TIMING.md)（增长总量）与 [页面预算](PAGE_BUDGET.md)（VRAM 约束）。', '',
             '```text',
             'PAYLOAD=%d PAGES DECODED=%d COMPACT=%d SAVING=%d (%.0f%%) PAGE_IDENTICAL=%s'
             % (stats['pages'], stats['decoded'], stats['compact_decoded'],
                stats['saving'], stats['saving_pct'],
                'YES' if stats['all_pages_identical'] else 'NO'),
             '```', '',
             '## 逐页数据', '',
             '| 页面 | tile 数 | 地图引用 | 未引用 | 其中空白 | 重复块 | decoded | 去重后 | 紧凑后 | 节省 | 页面不变 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |']
    for row in rows:
        lines.append('| `%s` | %d | %d | %d | %d | %d | %d | %d | %d | **%d** | %s |'
                     % (row['id'], row['tile_count'], row['referenced_tiles'],
                        row['unused_tiles'], row['blank_unused'], row['duplicate_tiles'],
                        row['decoded'], row['dedupe_decoded'], row['compact_decoded'],
                        row['decoded'] - row['compact_decoded'],
                        '是' if row['page_identical'] else '否'))
    lines += ['', '## 结论', '',
              '- 增长几乎全部来自 tile 块：5 张整包页共 %d 个 tile，其中 %d 个地图从未引用。'
              % (sum(row['tile_count'] for row in rows), stats['unused_tiles']),
              '- 只做“相同块去重”几乎没有收益（HAL 压缩已经吸收了重复），'
              '真正有效的是**按地图引用重排 tile 索引**，可减 %d 字节（%.0f%%）。'
              % (stats['saving'], stats['saving_pct']),
              '- 重排后页面 PNG 逐像素不变（本表最后一列由工具实际渲染比对得出）。',
              '- **但地图字节就是 VRAM tile 编号**：重排会改变屏幕上每个图块在 VRAM 的绝对编号，',
              '  凡是“按固定编号写 VRAM”的地方都会受影响（OBJ 精灵、动画 tile、局部地图刷新、',
              '  原版代码里对特定 tile 的改写）。因此这笔优化不是纯数据层改动，',
              '  必须逐页做运行时验证（OAM/动画/局部刷新）后才能采用。', '']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', action='store_true', help='write docs/LOADER_PAYLOAD.md')
    args = parser.parse_args(argv)
    rows = analyse(common.load_manifest())
    stats = summarize(rows)
    print('PAYLOAD=%d PAGES DECODED=%d COMPACT=%d SAVING=%d (%.0f%%) PAGE_IDENTICAL=%s'
          % (stats['pages'], stats['decoded'], stats['compact_decoded'],
             stats['saving'], stats['saving_pct'],
             'YES' if stats['all_pages_identical'] else 'NO'))
    if args.write:
        DOC.write_text(render_markdown(rows), encoding='utf-8')
        print('LOADER_PAYLOAD=WROTE ' + str(DOC.relative_to(ROOT)))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('LOADER_PAYLOAD=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
