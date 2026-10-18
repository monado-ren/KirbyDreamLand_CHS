# SPDX-License-Identifier: MIT
"""Symbolic source of truth for the localization change surface.

`06_ProgramFix/change_surface.json` names every loader site, resource, old/new value
and code region.  The release manifest no longer stores 110 hex patch pairs:
patches are derived from this file (assembling the RGBDS sources under
`06_ProgramFix/patches/`) whenever a manifest is loaded.  A single digest pins the
derived patch list so drift is still detected.

Usage:
    python 00_Tools/change_surface.py check [--base baserom.gb] [--rgbds DIR]
    python 00_Tools/change_surface.py explain [--site NAME]
    python 00_Tools/change_surface.py resources
    python 00_Tools/change_surface.py dump
    python 00_Tools/change_surface.py sync-manifest [--write]
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import common

DEFAULT_SPEC = common.ROOT / '06_ProgramFix/change_surface.json'
RGBDS_TOOLS = ('rgbasm', 'rgblink')


def require(cond, message):
    if not cond:
        raise ValueError(message)


def load_spec(path=DEFAULT_SPEC):
    spec = json.loads(Path(path).read_text())
    require(spec.get('schema') == 1, 'Unsupported change-surface schema')
    return spec


def save_spec(spec, path=DEFAULT_SPEC):
    Path(path).write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n')


def resource_cpu(res):
    return 0x4000 + (int(res['offset'], 16) - res['bank'] * 0x4000)


def _u8(value, what):
    require(isinstance(value, int) and 0 <= value <= 0xFF, what + ' does not fit in one byte')
    return bytes([value])


def _le16(value, what):
    require(isinstance(value, int) and 0 <= value <= 0xFFFF, what + ' does not fit in two bytes')
    return value.to_bytes(2, 'little')


def _resolve(value, resources, what):
    if isinstance(value, dict):
        res = resources.get(value.get('resource'))
        require(res is not None, what + ': unknown resource ' + repr(value.get('resource')))
        if value.get('field') == 'bank':
            return res['bank']
        if value.get('field') == 'cpu_address':
            return resource_cpu(res)
        raise ValueError(what + ': unsupported resource field ' + repr(value.get('field')))
    return value


def encode_patch(patch, resources):
    kind = patch['kind']
    if kind in ('rom.size', 'hud.label_tile', 'loader.vram_base', 'sprite.x'):
        return _u8(patch['old'], kind), _u8(patch['new'], kind)
    if kind == 'loader.source_addr':
        old = _le16(patch['old'], kind) if isinstance(patch['old'], int) else _le16(int(patch['old'], 16), kind)
        new = _le16(_resolve(patch['new'], resources, kind), kind)
        return old, new
    if kind == 'loader.bank':
        return _u8(patch['old'], kind), _u8(_resolve(patch['new'], resources, kind), kind)
    if kind == 'stage.pointer_table':
        old = b''.join(bytes([e['old']['bank'], int(e['old']['addr'], 16) >> 8,
                              int(e['old']['addr'], 16) & 0xFF]) for e in patch['entries'])
        new = b''.join(bytes([e['new']['bank'],
                              int(e['new']['addr'], 16) >> 8,
                              int(e['new']['addr'], 16) & 0xFF]) for e in patch['entries'])
        return old, new
    raise ValueError('Unknown patch kind ' + repr(kind))


def find_rgbds(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if Path('/usr/bin/rgbasm').exists():
        candidates.append(Path('/usr/bin'))
    found = shutil.which('rgbasm')
    if found:
        candidates.append(Path(found).parent)
    candidates.append(common.ROOT / 'build' / 'rgbds')
    for directory in candidates:
        if all((Path(directory) / tool).exists() for tool in RGBDS_TOOLS):
            return Path(directory)
    return None


def _require_rgbds(explicit=None):
    rgbds = find_rgbds(explicit)
    require(rgbds is not None,
            'RGBDS not found; build it from source with: python 00_Tools/build_rgbds.py')
    return rgbds


def assemble_region(region, asm_rel, rgbds):
    """Assemble one region source and return the *region* bytes."""
    source = common.ROOT / asm_rel
    require(source.is_file(), 'missing code source ' + str(source))
    rgbds = Path(rgbds)
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / 'region.o'
        out = Path(tmp) / 'region.gb'
        subprocess.run([str(rgbds / 'rgbasm'), '-o', str(obj), str(source)],
                       check=True, capture_output=True, text=True)
        subprocess.run([str(rgbds / 'rgblink'), '-o', str(out), str(obj)],
                       check=True, capture_output=True, text=True)
        data = out.read_bytes()
    file_offset = int(region['offset'], 16)
    require(file_offset + region['length'] <= len(data),
            'assembled image too short (%d bytes)' % len(data))
    return data[file_offset:file_offset + region['length']]


def derive_region(site, rgbds):
    region = site['region']
    old = assemble_region(region, region['asm_rev1'], rgbds)
    new = assemble_region(region, region['asm'], rgbds)
    base = int(region['offset'], 16)
    runs = []
    start = None
    for index in range(len(old) + 1):
        differs = index < len(old) and old[index] != new[index]
        if differs and start is None:
            start = index
        elif not differs and start is not None:
            runs.append((start, index))
            start = None
    require(runs, site['site'] + ': patched assembly is identical to Rev1')
    patches = []
    for start, end in runs:
        patches.append({'offset': base + start,
                        'expected_hex': old[start:end].hex(),
                        'replacement_hex': new[start:end].hex(),
                        'field': site['site']})
    return patches, old, new


def derive_patches(spec, rgbds=None):
    rgbds = rgbds or _require_rgbds()
    resources = {r['id']: r for r in spec['resources']}
    out = []
    for site in spec['sites']:
        if site.get('region'):
            patches, _old, _new = derive_region(site, rgbds)
            out.extend(patches)
            continue
        field = ';'.join([site['site']] + site.get('aliases', []))
        for patch in site['patches']:
            old, new = encode_patch(patch, resources)
            out.append({'offset': int(patch['offset'], 16),
                        'expected_hex': old.hex(),
                        'replacement_hex': new.hex(),
                        'field': field})
    out.sort(key=lambda p: p['offset'])
    return out


def patches_digest(patches):
    payload = json.dumps(patches, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()


def verify(spec, manifest=None, rgbds=None, base=None):
    rgbds = rgbds or _require_rgbds()
    resources = {r['id']: r for r in spec['resources']}
    derived = derive_patches(spec, rgbds)
    total = sum(len(bytes.fromhex(p['replacement_hex'])) for p in derived)

    if manifest is not None:
        manifest_patches = manifest.get('patches')
        if manifest_patches is not None:
            require(len(derived) == len(manifest_patches),
                    'derived %d patches, manifest has %d' % (len(derived), len(manifest_patches)))
            for index, (got, want) in enumerate(zip(derived, manifest_patches)):
                for key in ('offset', 'expected_hex', 'replacement_hex', 'field'):
                    require(got[key] == want[key],
                            'patch %d %s mismatch: %r != %r' % (index, key, got[key], want[key]))
        expected_digest = (manifest.get('change_surface') or {}).get('sha256')
        if expected_digest is not None:
            require(expected_digest == patches_digest(derived),
                    'change-surface digest mismatch (run sync-manifest --write after reviewing)')
        manifest_resources = {r['id']: r for r in manifest['resources']}
        require(set(resources) == set(manifest_resources),
                'symbolic resources and manifest resources differ: '
                + repr(set(resources) ^ set(manifest_resources)))
        for rid, res in resources.items():
            source = manifest_resources[rid]
            require(res['label'] == source['label'], rid + ': label mismatch')
            require(res['bank'] == source['bank'], rid + ': bank mismatch')
            require(int(res['offset'], 16) == source['offset'], rid + ': offset mismatch')
            require(res['capacity'] == source['capacity'], rid + ': capacity mismatch')
            role = 'active' if source['referenced_by_current_localized_loaders'] else 'legacy'
            require(res['role'] == role, rid + ': role mismatch')

    referenced = set()
    for site in spec['sites']:
        if site.get('resource'):
            referenced.add(site['resource'])
        for patch in site['patches']:
            if patch['kind'] == 'stage.pointer_table':
                for entry in patch['entries']:
                    if entry.get('resource'):
                        referenced.add(entry['resource'])
        if site.get('region'):
            for key in ('asm_rev1', 'asm'):
                require((common.ROOT / site['region'][key]).is_file(),
                        'missing code source ' + site['region'][key])
    require(not (referenced & {r['id'] for r in spec['resources'] if r['role'] == 'legacy'}),
            'legacy resources must not be referenced by any loader site')
    missing = {r['id'] for r in spec['resources'] if r['role'] == 'active'} - referenced
    require(not missing, 'active resources without a loader site: ' + repr(sorted(missing)))
    require(total == 198, 'replacement byte count changed: %d' % total)
    header = spec['header']
    require(header['rom_size_code']['new'] == 4, 'target ROM size code must be 4')
    require(header['checksums']['policy'] == 'recompute', 'checksums must be recomputed')

    if base is not None:
        for patch in derived:
            at = patch['offset']
            old = bytes.fromhex(patch['expected_hex'])
            require(base[at:at + len(old)] == old,
                    'base ROM does not match preimage at 0x%05X' % at)
        require(hashlib.sha256(base).hexdigest() == spec['baseline']['sha256'],
                'base ROM SHA-256 does not match spec baseline')

    return {'patches': len(derived), 'bytes': total, 'digest': patches_digest(derived),
            'sites': len(spec['sites']), 'resources': len(resources),
            'active': sum(1 for r in spec['resources'] if r['role'] == 'active'),
            'legacy': sum(1 for r in spec['resources'] if r['role'] == 'legacy'),
            'code_regions': sum(1 for s in spec['sites'] if s.get('region'))}


def sync_manifest(spec, manifest, path=None, write=False):
    """Replace manifest patch storage with a derived digest; keep resources."""
    rgbds = _require_rgbds()
    derived = derive_patches(spec, rgbds)
    digest = patches_digest(derived)
    total = sum(len(bytes.fromhex(p['replacement_hex'])) for p in derived)
    manifest = dict(manifest)
    manifest.pop('patches', None)
    manifest['change_surface'] = {'sha256': digest, 'patches': len(derived), 'bytes': total}
    if write:
        target = Path(path or common.DEFAULT_MANIFEST)
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return len(derived), digest


STAGES = (
    ('01', '容器扩容', '把 256 KiB 卡带扩成 512 KiB，并让头部声明正确。',
     ('rom.size',)),
    ('02', '代码区域', '唯一改游戏逻辑的补丁：VBlank 里“每帧写一行 BG map”改成“每帧写两行”。',
     ('code.region',)),
    ('03', '图块/整包装载器', '把 HUD、开场装饰、结局精灵、整包页、图鉴页的装载源改到扩展 bank 的新资源。',
     ('loader.sheet', 'loader.tileset', 'loader.tilemap', 'loader.bundle')),
    ('04', '装载目的地址', '改装载到 VRAM 的高字节，让新图块集/地图落在正确的 0x8000/0x8800/0x9000。',
     ('loader.vram_base',)),
    ('05', '指针表与目的基址', '五关介绍整包的三字节指针表，以及关卡整包的 VRAM 基址。',
     ('stage.pointer_table',)),
    ('06', 'UI/精灵微调', 'HUD 标签图块号重排、图鉴蝙蝠精灵 X 坐标 -9px。',
     ('hud.label_tile', 'sprite.x')),
    ('07', '资源内容', '新增/替换的压缩图块集、地图、整包页（构建输入是 PNG，不是 hex）。',
     ()),
    ('08', '文本层', '可由“字体 + 译文 + 布局”重排的文本（当前 11 条 / 8 页）。',
     ()),
    ('09', '构建与发布', '构建→校验→xdelta3 增量→发布校验和。', ()),
)


def _patch_table(spec, manifest, rgbds, kinds):
    """Patches for sites whose site.kind or patch.kind is in *kinds*."""
    resources = {r['id']: r for r in spec['resources']}
    derived = derive_patches(spec, rgbds)
    by_offset = {patch['offset']: patch for patch in derived}
    rows = []
    for site in spec['sites']:
        site_matches = bool(kinds) and site.get('kind') in kinds
        target = site.get('resource') or '-'
        fields = []
        if site.get('region'):
            if kinds and 'code.region' not in kinds and not site_matches:
                continue
            runs, _old, _new = derive_region(site, rgbds)
            notes = site['region'].get('notes', [])
            for index, run in enumerate(runs):
                fields.append((run['offset'], 'code.region', run, None,
                               notes[index] if index < len(notes) else ''))
        else:
            for patch in site.get('patches', []):
                if kinds and not site_matches and patch['kind'] not in kinds:
                    continue
                fields.append((int(patch['offset'], 16), patch['kind'], None, patch, ''))
        for offset, kind, run, original, note in fields:
            derived_patch = by_offset[offset]
            size = len(bytes.fromhex(derived_patch['replacement_hex']))
            if original is None:
                old = '0x' + derived_patch['expected_hex']
                new = '0x' + derived_patch['replacement_hex']
            else:
                old = _old_text(original)
                new = _new_text(original, resources)
                note = original.get('note', '')
            rows.append({'site': site['site'], 'kind': kind, 'offset': offset, 'bytes': size,
                         'target': target, 'note': note,
                         'purpose': site.get('purpose') or '', 'old': old, 'new': new})
    rows.sort(key=lambda row: row['offset'])
    return rows


def report(spec, manifest=None, rgbds=None):
    manifest = manifest or common.load_manifest()
    rgbds = rgbds or _require_rgbds()
    resources = {r['id']: r for r in spec['resources']}
    manifest_resources = {r['id']: r for r in manifest['resources']}
    derived = derive_patches(spec, rgbds)
    lines = ['# 工序与修改内容（细粒度）', '',
             '由 `python 00_Tools/change_surface.py report --write` 生成；补丁由符号层派生并核对，',
             '不要手改本文件。总览见 `CHANGE_SURFACE_COMPOSITION.md`。', '',
             '## 00 操作工序（从素材到发布）', '',
             '| # | 动作 | 命令/工具 | 输入 | 输出 | 校验 |',
             '| ---: | --- | --- | --- | --- | --- |',
             '| 1 | 改译文 | 编辑 `02_Text/zh-Hans.json` | 审稿文本 | 译文条目 | `text_layout.py check` 前会显示差异 |',
             '| 2 | 重排文本页 | `00_Tools/text_layout.py render --write` | `02_Text/layout.json` + 字体 + 译文 + `03_Image/text-base/` | `03_Image/pages/<page>.png` | `text_layout.py check` |',
             '| 3 | 改整页图 | 编辑 `03_Image/pages/*.png` | 页面 PNG | 页面 PNG | `pages.py render --check` |',
             '| 4 | 回写图块/地图 | `00_Tools/pages.py retile <page>.png` | 页面 PNG | `03_Image/graphics/*.png` | `pages.py render --check` |',
             '| 5 | 改覆盖层页 | 编辑 `build/pages/<page>.png` 后 `page_edits.py extract` | 基线+覆盖层 | `03_Image/edits/*` | `page_edits.py check` |',
             '| 6 | 刷清单 | `00_Tools/repack.py --version vX.Y.Z` | `03_Image/graphics` | `04_Data/manifest.json` | `verify.py` |',
             '| 7 | 改补丁语义 | 编辑 `06_ProgramFix/change_surface.json` / `patches/*.asm` | 符号层 | 派生补丁 | `change_surface.py check --base baserom.gb` |',
             '| 8 | 同步摘要 | `change_surface.py sync-manifest --write` | 派生补丁 | manifest `change_surface.sha256` | `change_surface.py check` |',
             '| 9 | 构建 | `00_Tools/build.py` | `baserom.gb` + manifest + 资源 | `KirbyDreamLand_CHS-Monado.gb` | `verify.py` |',
             '| 10 | 发布 | `00_Tools/release.py` | 构建 ROM + `baserom.gb` | `patches/*.xdelta3` | `SHA256SUMS.txt` |',
             '']
    for number, title, blurb, kinds in STAGES:
        lines += ['## %s %s' % (number, title), '', blurb, '']
        if number == '01':
            lines += ['| 偏移 | kind | 旧 → 新 | 说明 |', '| --- | --- | --- | --- |']
            for site in spec['sites']:
                for patch in site.get('patches', []):
                    if patch['kind'] == 'rom.size':
                        lines.append('| `%s` | `rom.size` | `%s` → `%s` | 256 KiB→512 KiB，MBC1 size code 3→4 |'
                                     % (patch['offset'], patch['old'], patch['new']))
            lines.append('')
        elif kinds:
            rows = _patch_table(spec, manifest, rgbds, kinds)
            lines += ['| 偏移 | site | kind | 字节 | 资源 | 旧 → 新 | 说明 |',
                      '| --- | --- | --- | ---: | --- | --- | --- |']
            for row in rows:
                lines.append('| `0x%05X` | `%s` | `%s` | %d | `%s` | `%s` → `%s` | %s |'
                             % (row['offset'], row['site'], row['kind'], row['bytes'],
                                row['target'], row['old'], row['new'],
                                (row['note'] or row['purpose']).replace('|', '/')))
            lines.append('')
        if number == '07':
            lines += ['| id | label | format | role | bank | offset | capacity | packed | 页面 | 用途 |',
                      '| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |']
            for resource in spec['resources']:
                entry = manifest_resources[resource['id']]
                page = entry.get('page') or entry.get('edit') or '-'
                lines.append('| `%s` | `%s` | %s | %s | %d | `%s` | %d | %d | `%s` | %s |'
                             % (resource['id'], resource['label'], resource['format'],
                                resource['role'], resource['bank'], resource['offset'],
                                resource['capacity'], entry['packed_size'], page,
                                resource['purpose'].replace('|', '/')))
            lines.append('')
        if number == '08':
            layout_path = common.ROOT / '02_Text' / 'layout.json'
            if layout_path.is_file():
                layout = json.loads(layout_path.read_text(encoding='utf-8'))
                translations = {e['id']: e for e in json.loads(
                    (common.ROOT / '02_Text' / 'zh-Hans.json').read_text(encoding='utf-8'))['entries']}
                lines += ['| 页面 | 文本 id | 译文 | 字体 | 锚点 |',
                          '| --- | --- | --- | --- | --- |']
                for entry_id, record in sorted(layout['entries'].items(),
                                               key=lambda item: (item[1]['page'], item[0])):
                    text = translations[entry_id]['translation_zh_hans'].replace('\n', '⏎')
                    lines.append('| `%s` | `%s` | %s | %s | (%d, %d) |'
                                 % (record['page'], entry_id, text, record['font'],
                                    record['anchor']['x'], record['anchor']['y']))
                lines.append('')
        if number == '09':
            lines += ['- `python 00_Tools/build.py`：按清单装载 71 个资源、写入 110 处补丁、重算校验和；',
                      '- `python 00_Tools/verify.py`：核对 524288 字节与目标 SHA-256；',
                      '- `python 00_Tools/release.py`：生成相对 `baserom.gb` 的 xdelta3；',
                      '- `SHA256SUMS.txt`：固定 ROM / 补丁 / baserom 三个哈希。', '']
    # Appendix: all patches
    lines += ['## 附录 A：全部 %d 处补丁' % len(derived), '',
              '| # | 偏移 | kind | 字节 | 旧字节 → 新字节 |', '| ---: | --- | --- | ---: | --- |']
    offset_to_kind = {}
    for site in spec['sites']:
        for patch in site.get('patches', []):
            offset_to_kind[int(patch['offset'], 16)] = patch['kind']
    for index, patch in enumerate(derived, 1):
        kind = offset_to_kind.get(patch['offset'], 'code.region')
        old = '0x' + patch['expected_hex'] if 'expected_hex' in patch else ''
        new = '0x' + patch['replacement_hex'] if 'replacement_hex' in patch else ''
        lines.append('| %d | `0x%05X` | `%s` | %d | `%s` → `%s` |'
                     % (index, patch['offset'], kind,
                        len(bytes.fromhex(patch['replacement_hex'])), old, new))
    lines += ['', '## 附录 B：文本条目（%d 条）' % len(json.loads(
        (common.ROOT / '02_Text' / 'zh-Hans.json').read_text(encoding='utf-8'))['entries']), '',
              '| id | section | 状态 | 译文 |', '| --- | --- | --- | --- |']
    for entry in json.loads((common.ROOT / '02_Text' / 'zh-Hans.json')
                            .read_text(encoding='utf-8'))['entries']:
        lines.append('| `%s` | %s | %s | %s |'
                     % (entry['id'], entry['section'], entry.get('integration_status', ''),
                        entry['translation_zh_hans'].replace('\n', '⏎').replace('|', '/')))
    lines += ['', '## 附录 C：页面层（%d 页）' % sum(
        1 for r in manifest_resources.values() if r.get('page') or r.get('edit')),
              '', '| id | 存储 | 角色 | 文件 | 用途 |', '| --- | --- | --- | --- | --- |']
    for resource_id, entry in manifest_resources.items():
        if not (entry.get('page') or entry.get('edit')):
            continue
        storage = 'page' if entry.get('page') else 'edit'
        file_path = entry.get('page') or entry.get('edit')
        purpose = resources.get(resource_id, {}).get('purpose', '')
        role = 'active' if entry['referenced_by_current_localized_loaders'] else 'legacy'
        lines.append('| `%s` | %s | %s | `%s` | %s |'
                     % (resource_id, storage, role, file_path, purpose.replace('|', '/')))
    return '\n'.join(lines) + '\n'


def summarize(spec, manifest=None, rgbds=None):
    """Layered composition of the change surface (for docs and CI output)."""
    resources = {r['id']: r for r in spec['resources']}
    patches = derive_patches(spec, rgbds)
    kind_by_offset = {}
    for site in spec['sites']:
        for patch in site.get('patches', []):
            kind_by_offset[int(patch['offset'], 16)] = patch['kind']
    patch_counts = {}
    patch_bytes = {}
    for patch in patches:
        kind = kind_by_offset.get(patch['offset'], 'code.region')
        patch_counts[kind] = patch_counts.get(kind, 0) + 1
        patch_bytes[kind] = patch_bytes.get(kind, 0) + len(bytes.fromhex(patch['replacement_hex']))
    site_counts = {}
    for site in spec['sites']:
        kind = site.get('kind') or 'special.' + site['site']
        site_counts[kind] = site_counts.get(kind, 0) + 1
    resource_formats = {}
    resource_roles = {}
    for resource in spec['resources']:
        resource_formats[resource['format']] = resource_formats.get(resource['format'], 0) + 1
        resource_roles[resource['role']] = resource_roles.get(resource['role'], 0) + 1
    manifest = manifest or common.load_manifest()
    resources_by_id = {r['id']: r for r in manifest['resources']}
    page_bundles = sum(1 for r in resources_by_id.values() if r.get('page'))
    page_edits = sum(1 for r in resources_by_id.values() if r.get('edit'))
    active_pages = sum(1 for r in resources_by_id.values()
                       if r['referenced_by_current_localized_loaders']
                       and (r.get('page') or r.get('edit')))
    legacy_pages = page_bundles + page_edits - active_pages
    graphics = len(list((common.ROOT / '03_Image' / 'graphics').glob('*.png')))
    text_entries = text_layer = text_pages = 0
    text_path = common.ROOT / '02_Text' / 'zh-Hans.json'
    layout_path = common.ROOT / '02_Text' / 'layout.json'
    if text_path.is_file():
        text_entries = len(json.loads(text_path.read_text(encoding='utf-8'))['entries'])
    if layout_path.is_file():
        layout = json.loads(layout_path.read_text(encoding='utf-8'))
        text_layer = len(layout['entries'])
        text_pages = len(layout['pages'])
    return {
        'patches': len(patches),
        'bytes': sum(patch_bytes.values()),
        'patch_kinds': patch_counts,
        'patch_bytes': patch_bytes,
        'sites': len(spec['sites']),
        'site_kinds': site_counts,
        'resources': len(spec['resources']),
        'resource_formats': resource_formats,
        'resource_roles': resource_roles,
        'page_bundles': page_bundles,
        'page_edits': page_edits,
        'active_pages': active_pages,
        'legacy_pages': legacy_pages,
        'graphics': graphics,
        'text_entries': text_entries,
        'text_layer_entries': text_layer,
        'text_layer_pages': text_pages,
    }


def _old_text(patch):
    if patch['kind'] == 'stage.pointer_table':
        return ', '.join('%s 6:%s' % (e['stage'], e['old']['addr']) for e in patch['entries'])
    if patch['kind'] == 'loader.source_addr':
        return patch['old'] if isinstance(patch['old'], str) else '0x%04X' % patch['old']
    return '0x%02X' % patch['old']


def _new_text(patch, resources):
    if patch['kind'] == 'stage.pointer_table':
        return ', '.join('%s %d:%s' % (e['stage'], e['new']['bank'], e['new']['addr'])
                         for e in patch['entries'])
    if isinstance(patch['new'], dict):
        res = resources.get(patch['new']['resource'])
        value = res['bank'] if patch['new']['field'] == 'bank' else resource_cpu(res)
        return '%s.%s=0x%X' % (patch['new']['resource'], patch['new']['field'], value)
    if patch['kind'] == 'loader.source_addr':
        return '0x%04X' % patch['new']
    return '0x%02X' % patch['new']


def explain(spec, only_site=None, rgbds=None):
    resources = {r['id']: r for r in spec['resources']}
    lines = []
    for site in spec['sites']:
        if only_site and site['site'] != only_site:
            continue
        target = resources.get(site.get('resource'))
        head = '[%s]' % site['site']
        if target:
            head += '  ->  %s  (%s)' % (target['id'], target['purpose'])
        elif site.get('region'):
            region = site['region']
            head += '  --  %s  (%d bytes at 0x%s, %s)' % (
                site.get('purpose') or '', region['length'], region['offset'][2:], region['asm'])
        else:
            head += '  --  ' + (site.get('purpose') or '')
        if site.get('purpose') and target:
            head += '\n    ' + site['purpose']
        lines.append(head)
        if site.get('region'):
            rgbds = rgbds or _require_rgbds()
            region = site['region']
            runs, _old, _new = derive_region(site, rgbds)
            for index, patch in enumerate(runs):
                note = region.get('notes', [''] * len(runs))[index] if index < len(region.get('notes', [])) else ''
                lines.append('    +0x%05X  code run %2d B  %s  ->  %s%s' % (
                    patch['offset'], len(bytes.fromhex(patch['replacement_hex'])),
                    patch['expected_hex'], patch['replacement_hex'],
                    ('  # ' + note) if note else ''))
            lines.append('    sources: %s  |  %s' % (region['asm_rev1'], region['asm']))
            continue
        for patch in site['patches']:
            lines.append('    %s  %-18s %s  ->  %s%s' % (
                patch['offset'], patch['kind'], _old_text(patch),
                _new_text(patch, resources),
                ('  # ' + patch['note']) if patch.get('note') else ''))
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=('check', 'explain', 'resources', 'dump', 'summary', 'report', 'sync-manifest'))
    p.add_argument('--spec', type=Path, default=DEFAULT_SPEC)
    p.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    p.add_argument('--base', type=Path, help='Also verify preimages against this Rev1 ROM')
    p.add_argument('--site', help='Only explain one site')
    p.add_argument('--rgbds', type=Path, help='Directory containing rgbasm and rgblink')
    p.add_argument('--write', action='store_true', help='With sync-manifest: rewrite the manifest; with report: write docs/WORK_ITEMS.md')
    p.add_argument('--check', action='store_true', help='With report: verify docs/WORK_ITEMS.md is current')
    a = p.parse_args(argv)
    spec = load_spec(a.spec)
    rgbds = find_rgbds(a.rgbds)
    if rgbds is None:
        rgbds = _require_rgbds(a.rgbds)
    if a.command == 'summary':
        stats = summarize(spec, common.load_manifest(), rgbds)
        print('SURFACE=PASS PATCHES=%d BYTES=%d SITES=%d RESOURCES=%d '
              'PAGES=%d ACTIVE_PAGES=%d TEXT_LAYER=%d/%d'
              % (stats['patches'], stats['bytes'], stats['sites'], stats['resources'],
                 stats['page_bundles'] + stats['page_edits'], stats['active_pages'],
                 stats['text_layer_entries'], stats['text_layer_pages']))
        print('PATCH_KINDS=' + ','.join('%s:%d/%dB' % (kind, count,
              stats['patch_bytes'][kind]) for kind, count in sorted(stats['patch_kinds'].items())))
        print('SITE_KINDS=' + ','.join('%s:%d' % item for item in sorted(stats['site_kinds'].items())))
        print('RESOURCE_FORMATS=' + ','.join('%s:%d' % item for item in sorted(stats['resource_formats'].items())))
        print('RESOURCE_ROLES=' + ','.join('%s:%d' % item for item in sorted(stats['resource_roles'].items())))
        print('PAGES=BUNDLE:%d EDIT:%d ACTIVE:%d LEGACY:%d GRAPHICS:%d TEXT_ENTRIES:%d'
              % (stats['page_bundles'], stats['page_edits'], stats['active_pages'],
                 stats['legacy_pages'], stats['graphics'], stats['text_entries']))
        return 0
    if a.command == 'report':
        text = report(spec, common.load_manifest(), rgbds)
        target = common.ROOT / 'docs' / 'WORK_ITEMS.md'
        if a.write:
            target.write_text(text, encoding='utf-8')
            print('REPORT=WROTE %s' % target.relative_to(common.ROOT))
            return 0
        if a.check:
            current = target.read_text(encoding='utf-8') if target.is_file() else ''
            if current != text:
                print('REPORT=FAIL stale %s; run: python 00_Tools/change_surface.py report --write'
                      % target.relative_to(common.ROOT), file=sys.stderr)
                return 1
            print('REPORT=PASS %s' % target.relative_to(common.ROOT))
            return 0
        print(text, end='')
        return 0
    if a.command == 'dump':
        print(json.dumps(derive_patches(spec, rgbds), ensure_ascii=False, indent=1))
        return 0
    if a.command == 'resources':
        for r in spec['resources']:
            print('%-12s %-8s bank %-2d %-8s cap %-5d %s' % (
                r['id'], r['role'], r['bank'], r['offset'], r['capacity'], r['purpose']))
        return 0
    if a.command == 'explain':
        print(explain(spec, a.site, rgbds))
        return 0
    manifest = json.loads(Path(a.manifest).read_text())
    if a.command == 'sync-manifest':
        count, digest = sync_manifest(spec, manifest, path=a.manifest, write=a.write)
        print('SYNC=%s PATCHES=%d DIGEST=%s%s'
              % ('WROTE' if a.write else 'PASS', count, digest,
                 '' if a.write else ' (use --write to update)'))
        return 0
    base = a.base.read_bytes() if a.base else None
    stats = verify(spec, manifest, rgbds=rgbds, base=base)
    print('CHANGE_SURFACE=PASS RELEASE=%s SITES=%d PATCHES=%d BYTES=%d RESOURCES=%d '
          'ACTIVE=%d LEGACY=%d REGIONS=%d DIGEST=%s'
          % (spec['release'], stats['sites'], stats['patches'], stats['bytes'],
             stats['resources'], stats['active'], stats['legacy'],
             stats['code_regions'], stats['digest'][:16]))
    if base is not None:
        print('BASE=PASS SHA256=' + spec['baseline']['sha256'])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print('CHANGE_SURFACE=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
