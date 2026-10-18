# SPDX-License-Identifier: MIT
"""Symbolic view of the localization change surface.

`source/change_surface.json` names every patch and resource: what screen it
belongs to, which loader site it rewrites, the old/new values in human terms,
whether a resource is active or a legacy copy, and which code regions are
assembled from RGBDS sources under `source/patches/`.

The release manifest stays the build authority for v0.5.1.  This tool proves
that the symbolic layer derives the manifest exactly.  Code regions are
pinned as bytes for the offline build, and are re-assembled from their
`.asm` source when RGBDS is available.

Usage:
    python tools/change_surface.py check [--base baserom.gb] [--rgbds DIR]
    python tools/change_surface.py explain [--site NAME]
    python tools/change_surface.py resources
    python tools/change_surface.py dump
    python tools/change_surface.py assemble [--write] [--rgbds DIR]
"""
import argparse
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
    """CPU address of a bank-relative resource, derived from its ROM offset."""
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
    if kind == 'code':
        return bytes.fromhex(patch['old']), bytes.fromhex(patch['new'])
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


def region_bytes(region, assembled=None):
    old = bytes.fromhex(region['old_hex'])
    new = bytes.fromhex(region['new_hex']) if assembled is None else assembled
    require(len(old) == region['length'], 'code region old_hex length mismatch')
    require(len(new) == region['length'], 'code region new_hex length mismatch')
    return old, new


def derive_region(site, assembled=None):
    region = site['region']
    old, new = region_bytes(region, assembled)
    base = int(region['offset'], 16)
    runs = []
    start = None
    for i in range(len(old) + 1):
        differs = i < len(old) and old[i] != new[i]
        if differs and start is None:
            start = i
        elif not differs and start is not None:
            runs.append((start, i))
            start = None
    require(runs, site['site'] + ': assembled region is identical to Rev1')
    patches = []
    for start, end in runs:
        patches.append({'offset': base + start,
                        'expected_hex': old[start:end].hex(),
                        'replacement_hex': new[start:end].hex(),
                        'field': site['site']})
    return patches


def derive_patches(spec, assembled=None):
    resources = {r['id']: r for r in spec['resources']}
    out = []
    for site in spec['sites']:
        if site.get('region'):
            out.extend(derive_region(site, (assembled or {}).get(site['site'])))
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


def verify(spec, manifest):
    resources = {r['id']: r for r in spec['resources']}
    derived = derive_patches(spec)
    authoritative = manifest['patches']
    require(len(derived) == len(authoritative),
            'symbolic surface derives %d patches, manifest has %d' % (len(derived), len(authoritative)))
    for index, (got, want) in enumerate(zip(derived, authoritative)):
        for key in ('offset', 'expected_hex', 'replacement_hex', 'field'):
            require(got[key] == want[key],
                    'patch %d %s mismatch: %r != %r' % (index, key, got[key], want[key]))
    require([p['offset'] for p in authoritative] == sorted(p['offset'] for p in authoritative),
            'manifest patches are not ordered by offset')

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
            path = common.ROOT / site['region']['asm']
            require(path.exists(), 'missing code source ' + str(path))
            old, new = region_bytes(site['region'])
            require(sum(1 for a, b in zip(old, new) if a != b) > 0,
                    site['site'] + ': code region has no difference from Rev1')
    require(not (referenced & {r['id'] for r in spec['resources'] if r['role'] == 'legacy'}),
            'legacy resources must not be referenced by any loader site')
    missing = {r['id'] for r in spec['resources'] if r['role'] == 'active'} - referenced
    require(not missing, 'active resources without a loader site: ' + repr(sorted(missing)))

    total = sum(len(bytes.fromhex(p['replacement_hex'])) for p in derived)
    require(total == 198, 'replacement byte count changed: %d' % total)
    header = spec['header']
    require(header['rom_size_code']['new'] == 4, 'target ROM size code must be 4')
    require('recompute' == header['checksums']['policy'], 'checksums must be recomputed')
    return {'patches': len(derived), 'bytes': total,
            'sites': len(spec['sites']), 'resources': len(resources),
            'active': sum(1 for r in spec['resources'] if r['role'] == 'active'),
            'legacy': sum(1 for r in spec['resources'] if r['role'] == 'legacy'),
            'code_regions': sum(1 for s in spec['sites'] if s.get('region'))}


def verify_base(spec, base, manifest):
    require(len(base) == spec['target']['size'] // 2, 'base ROM size does not match spec')
    for patch in derive_patches(spec):
        at = patch['offset']
        old = bytes.fromhex(patch['expected_hex'])
        require(base[at:at + len(old)] == old,
                'base ROM does not match preimage at 0x%05X' % at)
    import hashlib
    require(hashlib.sha256(base).hexdigest() == spec['baseline']['sha256'],
            'base ROM SHA-256 does not match spec baseline')
    require(manifest['baseline']['sha256'] == spec['baseline']['sha256'],
            'spec and manifest baselines differ')


def find_rgbds(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if Path('/usr/bin/rgbasm').exists():
        candidates.append(Path('/usr/bin'))
    if shutil.which('rgbasm'):
        candidates.append(Path(shutil.which('rgbasm')).parent)
    candidates.append(common.ROOT / 'build' / 'rgbds')
    for directory in candidates:
        if all((directory / tool).exists() for tool in RGBDS_TOOLS):
            return directory
    return None


def assemble_region(region, rgbds):
    rgbds = Path(rgbds)
    source = common.ROOT / region['asm']
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / 'region.o'
        out = Path(tmp) / 'region.gb'
        subprocess.run([str(rgbds / 'rgbasm'), '-o', str(obj), str(source)],
                       check=True, capture_output=True, text=True)
        subprocess.run([str(rgbds / 'rgblink'), '-o', str(out), str(obj)],
                       check=True, capture_output=True, text=True)
        data = out.read_bytes()
    # rgblink lays ROMX bank b out at b*0x4000 + (address-$4000), i.e. the same
    # file offset the section already uses in the cartridge.
    file_offset = int(region['offset'], 16)
    require(file_offset + region['length'] <= len(data),
            'assembled image too short (%d bytes)' % len(data))
    return data[file_offset:file_offset + region['length']]


def assemble_all(spec, rgbds, write=False):
    assembled = {}
    for site in spec['sites']:
        region = site.get('region')
        if not region:
            continue
        blob = assemble_region(region, rgbds)
        old = bytes.fromhex(region['old_hex'])
        require(len(blob) == region['length'], site['site'] + ': assembled length mismatch')
        require(blob != old, site['site'] + ': assembly equals Rev1; no patch would be emitted')
        assembled[site['site']] = blob
        if write:
            region['new_hex'] = blob.hex()
    if write:
        save_spec(spec)
    return assembled


def verify_assembler(spec, manifest, rgbds):
    if rgbds is None:
        return 'MISSING'
    assembled = assemble_all(spec, rgbds)
    derived = derive_patches(spec, assembled)
    authoritative = derive_patches(spec)
    require(derived == authoritative, 'assembled code regions differ from pinned new_hex')
    return 'PASS'


def sync_manifest(spec, manifest, path=None, write=False):
    """Replace manifest['patches'] with the patches derived from the symbols.

    Returns the number of patches.  With write=True the manifest file is
    rewritten (indent=2, matching the tracked manifest).  Without write the
    caller should compare the result itself; `check` already proves equality.
    """
    derived = derive_patches(spec)
    if manifest.get('patches') != derived:
        if not write:
            raise ValueError('manifest patches differ from the symbolic surface; '
                             'run `sync-manifest --write` after reviewing the spec')
    manifest['patches'] = derived
    if write:
        target = Path(path or common.DEFAULT_MANIFEST)
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return len(derived)


def _old_text(patch):
    if patch['kind'] == 'code':
        return patch['old']
    if patch['kind'] == 'stage.pointer_table':
        return ', '.join('%s 6:%s' % (e['stage'], e['old']['addr']) for e in patch['entries'])
    if patch['kind'] == 'loader.source_addr':
        return patch['old'] if isinstance(patch['old'], str) else '0x%04X' % patch['old']
    return '0x%02X' % patch['old']


def _new_text(patch, resources):
    if patch['kind'] == 'code':
        return patch['new']
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


def explain(spec, only_site=None):
    resources = {r['id']: r for r in spec['resources']}
    lines = []
    for site in spec['sites']:
        if only_site and site['site'] != only_site:
            continue
        name = site['site']
        target = resources.get(site.get('resource'))
        head = '[%s]' % name
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
            region = site['region']
            old, new = region_bytes(region)
            runs = derive_region(site)
            for index, patch in enumerate(runs):
                note = region.get('notes', [''] * len(runs))[index] if index < len(region.get('notes', [])) else ''
                lines.append('    +0x%05X  code run %2d B  %s  ->  %s%s' % (
                    patch['offset'], len(bytes.fromhex(patch['replacement_hex'])),
                    patch['expected_hex'], patch['replacement_hex'],
                    ('  # ' + note) if note else ''))
            lines.append('    assembled source: ' + region['asm'] + '  (edit + `assemble --write`)')
            continue
        for patch in site['patches']:
            lines.append('    %s  %-18s %s  ->  %s%s' % (
                patch['offset'], patch['kind'], _old_text(patch),
                _new_text(patch, resources),
                ('  # ' + patch['note']) if patch.get('note') else ''))
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=('check', 'explain', 'resources', 'dump', 'assemble', 'sync-manifest'))
    p.add_argument('--spec', type=Path, default=DEFAULT_SPEC)
    p.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    p.add_argument('--base', type=Path, help='Also verify preimages against this Rev1 ROM')
    p.add_argument('--site', help='Only explain one site')
    p.add_argument('--rgbds', type=Path, help='Directory containing rgbasm and rgblink')
    p.add_argument('--require-asm', action='store_true', help='Fail when RGBDS is unavailable')
    p.add_argument('--write', action='store_true', help='With assemble: rewrite pinned new_hex')
    a = p.parse_args(argv)
    spec = load_spec(a.spec)
    manifest = common.load_manifest(a.manifest)
    if a.command == 'dump':
        print(json.dumps(derive_patches(spec), ensure_ascii=False, indent=1))
        return 0
    if a.command == 'resources':
        for r in spec['resources']:
            print('%-12s %-8s bank %-2d %-8s cap %-5d %s' % (
                r['id'], r['role'], r['bank'], r['offset'], r['capacity'], r['purpose']))
        return 0
    if a.command == 'explain':
        print(explain(spec, a.site))
        return 0
    rgbds = find_rgbds(a.rgbds)
    if a.command == 'sync-manifest':
        count = sync_manifest(spec, manifest, path=a.manifest, write=a.write)
        print('SYNC=%s PATCHES=%d%s' % ('WROTE' if a.write else 'PASS', count,
                                       '' if a.write else ' (use --write to update)'))
        return 0
    if a.command == 'assemble':
        require(rgbds is not None, 'RGBDS not found; pass --rgbds DIR')
        assembled = assemble_all(spec, rgbds, write=a.write)
        for name, blob in assembled.items():
            print('ASM=%s BYTES=%d SHA256=%s' % (name, len(blob),
                                                  __import__('hashlib').sha256(blob).hexdigest()[:16]))
        if a.write:
            print('SPEC=UPDATED ' + str(a.spec))
        return 0
    stats = verify(spec, manifest)
    if a.base:
        verify_base(spec, a.base.read_bytes(), manifest)
    asm = verify_assembler(spec, manifest, rgbds)
    if asm == 'MISSING' and a.require_asm:
        raise ValueError('RGBDS not found; pass --rgbds DIR')
    print('CHANGE_SURFACE=PASS RELEASE=%s SITES=%d PATCHES=%d BYTES=%d RESOURCES=%d ACTIVE=%d LEGACY=%d REGIONS=%d ASM=%s'
          % (spec['release'], stats['sites'], stats['patches'], stats['bytes'],
             stats['resources'], stats['active'], stats['legacy'], stats['code_regions'], asm))
    if a.base:
        print('BASE=PASS SHA256=' + spec['baseline']['sha256'])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print('CHANGE_SURFACE=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
