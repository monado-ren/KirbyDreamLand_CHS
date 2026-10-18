# SPDX-License-Identifier: MIT
"""Symbolic source of truth for the localization change surface.

`source/change_surface.json` names every loader site, resource, old/new value
and code region.  The release manifest no longer stores 110 hex patch pairs:
patches are derived from this file (assembling the RGBDS sources under
`source/patches/`) whenever a manifest is loaded.  A single digest pins the
derived patch list so drift is still detected.

Usage:
    python tools/change_surface.py check [--base baserom.gb] [--rgbds DIR]
    python tools/change_surface.py explain [--site NAME]
    python tools/change_surface.py resources
    python tools/change_surface.py dump
    python tools/change_surface.py sync-manifest [--write]
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

DEFAULT_SPEC = common.ROOT / 'source/change_surface.json'
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
            'RGBDS not found; build it from source with: python tools/build_rgbds.py')
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
    p.add_argument('command', choices=('check', 'explain', 'resources', 'dump', 'sync-manifest'))
    p.add_argument('--spec', type=Path, default=DEFAULT_SPEC)
    p.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    p.add_argument('--base', type=Path, help='Also verify preimages against this Rev1 ROM')
    p.add_argument('--site', help='Only explain one site')
    p.add_argument('--rgbds', type=Path, help='Directory containing rgbasm and rgblink')
    p.add_argument('--write', action='store_true', help='With sync-manifest: rewrite the manifest')
    a = p.parse_args(argv)
    spec = load_spec(a.spec)
    rgbds = find_rgbds(a.rgbds)
    if rgbds is None:
        rgbds = _require_rgbds(a.rgbds)
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
