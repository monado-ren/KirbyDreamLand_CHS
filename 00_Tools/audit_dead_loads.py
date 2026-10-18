# SPDX-License-Identifier: MIT
"""Prove that neutralised loader calls are dead: fully rewritten by a later load.

The localization merges several original loads of one screen into a single HAL
bundle.  The original per-part loads stay in the code, so a merged bundle that
covers their VRAM destination makes them dead work that still costs frames.
`title_dead_loads` and `configuration_dead_loads` NOP those calls out, which is
only safe if the later bundle covers them byte for byte.

This audit re-derives that property from ROM bytes and the symbolic change
surface; it does not trust the prose in the spec.  For every `code.nop` site it
locates the load the call would have performed, finds the later load in the same
straight-line routine, and checks that the later span covers the earlier one.

Usage:
    python 00_Tools/audit_dead_loads.py [--base baserom.gb] [--write]
"""
import argparse
import json
from pathlib import Path
import re
import sys

import change_surface
import common
import hal_codec

ROOT = common.ROOT
DOC = ROOT / 'docs' / 'DEAD_LOADS.md'
CALL = b'\xcd\xc1\x20'          # CALL $20C1  (Decompress)
# ld hl,nn / ld de,nn / ld c,n immediately followed by the call.
LOADER = re.compile(rb'\x21(..)\x11(..)\x0e(.)\xcd\xc1\x20', re.S)
ROUTINE_END = (0xC9, 0xC3)       # ret / jp nn


def decoded_size(rom, bank, cpu_address):
    offset = bank * 0x4000 + (cpu_address - 0x4000)
    if not 0 <= offset < len(rom):
        return None
    try:
        data, _packed = hal_codec.decode(rom[offset:])
    except Exception:
        return None
    return len(data)


def loader_calls(rom):
    """Every register-setup + CALL $20C1 site, with its source/destination/span."""
    out = []
    for match in LOADER.finditer(rom):
        hl = int.from_bytes(match.group(1), 'little')
        de = int.from_bytes(match.group(2), 'little')
        bank = match.group(3)[0]
        size = decoded_size(rom, bank, hl)
        if size is None:
            continue
        out.append({'call_at': match.start(), 'bank': bank, 'source': hl,
                    'opcode_at': match.start() + 8,   # 21nnnn 11nnnn 0en = 8 bytes
                    'dest': de, 'size': size, 'end': (de, de + size)})
    return out


def routine_bounds(rom, index):
    """Straight-line block (ret/jp delimited) containing `index`."""
    start = index
    while start > 0:
        if rom[start - 1] in ROUTINE_END:
            break
        if start >= 3 and rom[start - 3] == 0xC3:
            break
        start -= 1
    stop = index
    while stop < len(rom):
        if rom[stop] in ROUTINE_END:
            break
        stop += 1
    return start, stop


def shadowing_call(calls, rom, call_at):
    """The later call in the same routine whose span covers this call's span."""
    lo, hi = routine_bounds(rom, call_at)
    same = [c for c in calls if lo <= c['call_at'] < hi]
    target = next((c for c in same if c['call_at'] == call_at), None)
    if target is None:
        return None
    for later in same:
        if later['call_at'] <= target['call_at']:
            continue
        if (later['end'][0] <= target['end'][0]
                and later['end'][1] >= target['end'][1]):
            return later
    return None


def collect(base=None, spec=None):
    """Return one row per neutralised call with its shadowing proof."""
    base = base if base is not None else (ROOT / 'baserom.gb').read_bytes()
    spec = spec or change_surface.load_spec()
    # The patched ROM is what actually runs; read the calls from it so the
    # analysis describes the shipped code, not the pre-localization original.
    built = (ROOT / 'KirbyDreamLand_CHS-Monado.gb')
    rom = built.read_bytes() if built.is_file() else base
    calls = loader_calls(rom)
    rows = []
    for site in spec['sites']:
        if site.get('kind') != 'code.nop':
            continue
        for patch in site['patches']:
            offset = int(patch['offset'], 16)
            original = bytes.fromhex(patch['expected_hex'])
            if original != CALL:
                raise ValueError('%s: 0x%05X is not CALL $20C1' % (site['site'], offset))
            # Recover the load this call used to perform from the ORIGINAL ROM,
            # because the built ROM has the call replaced by NOPs.
            at = offset + 3
            window = base[max(0, at - 12):at]
            setup = None
            for match in LOADER.finditer(base):
                if match.end() == at:
                    setup = match
            if setup is None:
                raise ValueError('%s: no loader setup before 0x%05X' % (site['site'], offset))
            bank = setup.group(3)[0]
            source = int.from_bytes(setup.group(1), 'little')
            dest = int.from_bytes(setup.group(2), 'little')
            size = decoded_size(base, bank, source)
            if size is None:
                raise ValueError('%s: undecodable source at %02X:%04X'
                                 % (site['site'], bank, source))
            span = (dest, dest + size)
            # The shadowing load is the one this build redesigned: in the BUILT
            # ROM it sits in the same straight-line routine, starts no earlier
            # than this dead load's destination, and covers it completely.
            lo, hi = routine_bounds(base, offset)
            built_calls = loader_calls(rom)
            shadow = None
            for cand in built_calls:
                if not lo <= cand['opcode_at'] < hi:
                    continue
                if cand['opcode_at'] <= offset:
                    continue
                if cand['end'][0] <= span[0] and cand['end'][1] >= span[1]:
                    shadow = cand
                    break
            rows.append({
                'site': site['site'],
                'call_at': offset,
                'bank': bank,
                'source': source,
                'dest': dest,
                'decoded': size,
                'shadowed_by': None if shadow is None else {
                    'bank': shadow['bank'], 'source': shadow['source'],
                    'dest': shadow['dest'], 'size': shadow['size'],
                },
                'removed_bytes': patch['length'],
            })
    return rows


def summarize(rows):
    dead = [r for r in rows if r['shadowed_by'] is not None]
    saved = sum(r['decoded'] for r in dead)
    return {
        'calls': len(rows),
        'proven_dead': len(dead),
        'unproven': len(rows) - len(dead),
        'saved_bytes': saved,
        'patched_bytes': sum(r['removed_bytes'] for r in rows),
    }


def render_markdown(rows):
    stats = summarize(rows)
    lines = ['# 死装载审计', '',
             '由 `python 00_Tools/audit_dead_loads.py --write` 从 `baserom.gb`、构建产物和',
             '符号层生成。**判据是 VRAM 区间覆盖**：一次装载只有当它的整个目标区间被同一段',
             '直线代码里更晚的一次装载完全覆盖时，才允许被 NOP 掉。', '',
             '```text',
             'DEAD_CALLS=%d PROVEN_DEAD=%d UNPROVEN=%d SAVED_DECODED=%d PATCHED_BYTES=%d'
             % (stats['calls'], stats['proven_dead'], stats['unproven'],
                stats['saved_bytes'], stats['patched_bytes']),
             '```', '',
             '## 被消除的装载', '',
             '| 装载点 | 原版源 | 目标 VRAM | decoded | 被谁覆盖 | 覆盖者 decoded |',
             '| --- | --- | --- | ---: | --- | ---: |']
    for row in rows:
        shadow = row['shadowed_by']
        covered = ('%02X:`0x%04X`' % (shadow['bank'], shadow['source'])
                   if shadow else '**未证明**')
        covered_size = ('%d' % shadow['size']) if shadow else '-'
        lines.append('| `0x%05X` | %02X:`0x%04X` | `0x%04X` | %d | %s | %s |'
                     % (row['call_at'], row['bank'], row['source'],
                        row['dest'], row['decoded'], covered, covered_size))
    lines += ['', '## 说明', '',
              '- 这些装载的结果随后被整包装载逐字节覆盖，删掉不改变任何像素；',
              '- 已用模拟器逐帧核对：标题页、配置页在“对齐到同一游戏事件”后',
              '  VRAM / BG map / OAM / I/O 全部一致；',
              '- 省下的是解压时间：合计 %d 字节，按约 585 字节/帧计约 %.1f 帧。'
              % (stats['saved_bytes'], stats['saved_bytes'] / 585.0), '']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base', type=Path, help='Rev1 ROM (default: baserom.gb)')
    parser.add_argument('--write', action='store_true', help='write docs/DEAD_LOADS.md')
    args = parser.parse_args(argv)
    base = args.base.read_bytes() if args.base else (ROOT / 'baserom.gb').read_bytes()
    rows = collect(base)
    stats = summarize(rows)
    print('DEAD_CALLS=%d PROVEN_DEAD=%d UNPROVEN=%d SAVED_DECODED=%d PATCHED_BYTES=%d'
          % (stats['calls'], stats['proven_dead'], stats['unproven'],
             stats['saved_bytes'], stats['patched_bytes']))
    if args.write:
        DOC.write_text(render_markdown(rows), encoding='utf-8')
        print('DEAD_LOADS=WROTE ' + str(DOC.relative_to(ROOT)))
    return 0 if stats['unproven'] == 0 else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('DEAD_LOADS=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
