# SPDX-License-Identifier: MIT
"""Portable release-snapshot compiler. Only the user's Rev1 base ROM is input.

The graphics resources are lossless PNG sources that derive exact 2bpp Game Boy
tile/map bytes; they are not executable code.  Changing translation JSON or the
assets/ reference artwork does not automatically rerasterize these resources.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from hal_codec import decode, pack
import graphics_png

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / 'source/manifest.json'


class ProjectError(ValueError):
    """A checked input or build invariant was violated."""


def require(condition, message):
    if not condition:
        raise ProjectError(message)


def fingerprints(data):
    return dict(size=len(data), md5=hashlib.md5(data).hexdigest(),
                sha1=hashlib.sha1(data).hexdigest(), sha256=hashlib.sha256(data).hexdigest())


def resource_path(value):
    require(isinstance(value, str), 'Resource path must be a string')
    require(not PureWindowsPath(value).is_absolute() and not PureWindowsPath(value).drive,
            'Absolute resource paths are not accepted')
    relative = PurePosixPath(value)
    require(not relative.is_absolute() and '..' not in relative.parts,
            'Resource path must remain inside this project')
    require(relative.parts[:2] == ('source', 'graphics'), 'Resources must be PNG files in source/graphics')
    require(relative.suffix.lower() == '.png', 'Graphics resources must be PNG files')
    result = (ROOT / value).resolve()
    require(result.is_relative_to((ROOT / 'source/graphics').resolve()), 'Resource path escapes graphics directory')
    return result


def page_path(value):
    require(isinstance(value, str), 'Page path must be a string')
    require(not PureWindowsPath(value).is_absolute() and not PureWindowsPath(value).drive,
            'Absolute page paths are not accepted')
    relative = PurePosixPath(value)
    require(not relative.is_absolute() and '..' not in relative.parts,
            'Page path must remain inside this project')
    require(relative.parts[:2] == ('source', 'pages'), 'Pages must be PNG files in source/pages')
    require(relative.suffix.lower() == '.png', 'Pages must be PNG files')
    result = (ROOT / value).resolve()
    require(result.is_relative_to((ROOT / 'source/pages').resolve()),
            'Page path escapes the page directory')
    return result


def validate_page_path(value):
    page_path(value)


def edit_path(value):
    require(isinstance(value, str), 'Edit path must be a string')
    require(not PureWindowsPath(value).is_absolute() and not PureWindowsPath(value).drive,
            'Absolute edit paths are not accepted')
    relative = PurePosixPath(value)
    require(not relative.is_absolute() and '..' not in relative.parts,
            'Edit path must remain inside this project')
    require(relative.parts[:2] == ('source', 'edits'),
            'Edits must be JSON files in source/edits')
    require(relative.suffix.lower() == '.json', 'Edits must be JSON files')
    result = (ROOT / value).resolve()
    require(result.is_relative_to((ROOT / 'source/edits').resolve()),
            'Edit path escapes the edit directory')
    return result


def validate_edit_path(value):
    edit_path(value)


def validate_build_page_path(value):
    require(isinstance(value, str), 'Build page path must be a string')
    relative = PurePosixPath(value)
    require(not PureWindowsPath(value).is_absolute() and not PureWindowsPath(value).drive,
            'Absolute page paths are not accepted')
    require(relative.parts[:2] == ('build', 'pages'), 'Build pages live in build/pages')
    require(relative.suffix.lower() == '.png', 'Pages must be PNG files')
    result = (ROOT / value).resolve()
    require(result.is_relative_to((ROOT / 'build/pages').resolve()),
            'Build page path escapes build/pages')
    return result


def validate_manifest(manifest):
    require(manifest.get('schema_version') == 1, 'Unsupported manifest schema')
    require(manifest.get('fill_byte') == 255, 'Expansion padding must be FF')
    for key in ('baseline', 'target'):
        spec = manifest[key]
        require(isinstance(spec.get('size'), int) and spec['size'] > 0, 'Invalid size')
        require(re.fullmatch('[0-9a-f]{64}', spec.get('sha256', '')) is not None,
                'Invalid '+key+' SHA-256 fingerprint')
    require(manifest['baseline']['size'] == 0x40000 and manifest['target']['size'] == 0x80000,
            'Expected 256 KiB input and 512 KiB output')
    used = set()
    for p in manifest['patches']:
        at = p['offset']; before = bytes.fromhex(p['expected_hex']); after = bytes.fromhex(p['replacement_hex'])
        require(isinstance(at, int) and 0 <= at < 0x40000, 'Patch offset outside original ROM')
        require(len(before) == len(after) and len(before) > 0 and at+len(before) <= 0x40000,
                'Patch preimage/replacement sizes differ')
        cells = set(range(at, at+len(before)))
        require(not cells & ({0x14C, 0x14D, 0x14E, 0x14F} | used), 'Overlapping or reserved header patch')
        used |= cells
    resource_ids = set()
    for r in manifest['resources']:
        require(r['id'] not in resource_ids, 'Duplicate resource id')
        resource_ids.add(r['id'])
    reserved = []
    for r in manifest['resources']:
        resource_path(r['source'])
        at, capacity = r['offset'], r['capacity']
        require(r['format'] == 'hal-greedy-v1', 'Unknown resource codec')
        png = r.get('png')
        require(isinstance(png, dict), 'Resource is missing its PNG description')
        mode = png.get('mode')
        require(mode in (graphics_png.TILES_MODE, graphics_png.TILEMAP_MODE),
                'Unknown PNG resource mode')
        if mode == graphics_png.TILES_MODE:
            require(isinstance(png.get('tiles_per_row'), int) and png['tiles_per_row'] > 0,
                    'Tileset PNG needs a positive tiles_per_row')
            require(isinstance(png.get('tile_count'), int) and png['tile_count'] > 0,
                    'Tileset PNG needs a positive tile_count')
            if r.get('bundle') is None:
                require(r['decoded_size'] == png['tile_count'] * 16,
                        'Tileset decoded size must equal tile_count * 16')
        else:
            require(isinstance(png.get('width'), int) and isinstance(png.get('height'), int)
                    and png['width'] > 0 and png['height'] > 0,
                    'Tilemap PNG needs positive width and height')
            require(png['width'] * png['height'] == r['decoded_size'],
                    'Tilemap PNG dimensions must match the decoded size')
            require(png.get('addressing') in graphics_png.TILEMAP_ADDRESSING,
                    'Tilemap PNG needs a supported addressing mode')
            require(png.get('tileset') in resource_ids,
                    'Tilemap PNG must reference an existing tileset resource')
            if r.get('edit') is not None:
                require(r.get('page') is None, 'Edit-backed pages must not also carry a page path')
                require(r['edit'] == 'source/edits/' + r['id'] + '.json',
                        'Tilemap edit path must be source/edits/<id>.json')
                validate_edit_path(r['edit'])
            else:
                require(r.get('page') == 'source/pages/' + r['id'] + '.png',
                        'Tilemap page path must be source/pages/<id>.png')
                validate_page_path(r['page'])
        bundle = r.get('bundle')
        if bundle is not None:
            require(mode == graphics_png.TILES_MODE, 'Bundles must use the tileset PNG mode')
            require(isinstance(bundle, dict), 'Invalid bundle description')
            require(bundle.get('addressing') in graphics_png.TILEMAP_ADDRESSING,
                    'Bundle needs a supported addressing mode')
            require(isinstance(bundle.get('width'), int) and isinstance(bundle.get('height'), int)
                    and bundle['width'] > 0 and bundle['height'] > 0,
                    'Bundle needs positive map dimensions')
            require(r['decoded_size'] == png['tile_count'] * 16
                    + bundle['width'] * bundle['height'],
                    'Bundle decoded size must equal tiles + map bytes')
            resource_path(bundle.get('map_png'))
            require(r.get('edit') is None, 'Bundle pages stay as full PNG pages')
            require(r.get('page') == 'source/pages/' + r['id'] + '.png',
                    'Bundle page path must be source/pages/<id>.png')
            validate_page_path(r['page'])
        if r.get('page_kind') == 'sheet':
            if r.get('edit') is not None:
                require(r.get('page') is None, 'Edit-backed pages must not also carry a page path')
                require(r['edit'] == 'source/edits/' + r['id'] + '.json',
                        'Sheet edit path must be source/edits/<id>.json')
                validate_edit_path(r['edit'])
            else:
                require(r.get('page') == 'source/pages/' + r['id'] + '.png',
                        'Sheet page path must be source/pages/<id>.png')
                validate_page_path(r['page'])
        require(isinstance(at,int) and isinstance(capacity,int) and capacity > 0,
                'Invalid resource allocation')
        require(0x40000 <= at < at+capacity <= 0x80000, 'Resource outside expanded ROM')
        require(at//0x4000 == (at+capacity-1)//0x4000, 'Resource capacity crosses bank')
        require(r['bank'] == at//0x4000 and r['cpu_address'] == 0x4000+at%0x4000,
                'Resource bank/CPU address mismatch')
        require(0 < r['packed_size'] <= capacity and r['decoded_size'] > 0, 'Invalid resource length')
        require(all(at >= end or start >= at+capacity for start,end in reserved), 'Overlapping resource capacity')
        reserved.append((at,at+capacity))


def load_manifest(path=None):
    manifest = json.loads(Path(path or DEFAULT_MANIFEST).read_text(encoding='utf-8'))
    if 'patches' not in manifest:
        # v0.5.2+: the change surface is symbolic.  Derive the 110 patches from
        # source/change_surface.json (assembling source/patches/*.asm) and pin
        # the result with one digest instead of storing hex pairs.
        require(isinstance(manifest.get('change_surface'), dict),
                'Manifest has neither patches nor a change_surface digest')
        import change_surface
        spec = change_surface.load_spec()
        rgbds = change_surface.find_rgbds()
        require(rgbds is not None,
                'RGBDS not found; build it from source first: python tools/build_rgbds.py')
        derived = change_surface.derive_patches(spec, rgbds)
        digest = change_surface.patches_digest(derived)
        require(digest == manifest['change_surface'].get('sha256'),
                'Change-surface digest mismatch; review source/change_surface.json and run '
                'tools/change_surface.py sync-manifest --write')
        manifest['patches'] = derived
    validate_manifest(manifest)
    return manifest


def manifest_storage(manifest):
    """Manifest as written to disk: derived patches are not serialized."""
    stored = {key: value for key, value in manifest.items() if key != 'patches'}
    return stored


def validate_input(data, manifest):
    actual = fingerprints(data)
    for key in ('size','sha256'):
        require(actual[key] == manifest['baseline'][key], 'Wrong base ROM: '+key+' mismatch; use Japanese Rev1')
    require(data[0x14C] == 1, 'Expected cartridge revision 1')
    return actual


def prepare_resources(manifest, strict=True):
    results = []
    for r in manifest['resources']:
        spec = dict(r['png'])
        try:
            raw = graphics_png.load_resource(resource_path(r['source']), spec)
            bundle = r.get('bundle')
            if bundle is not None:
                map_spec = {'mode': graphics_png.TILEMAP_MODE,
                            'width': bundle['width'], 'height': bundle['height']}
                raw = raw + graphics_png.png_to_tilemap(
                    resource_path(bundle['map_png']).read_bytes(),
                    bundle['width'], bundle['height'])
        except graphics_png.GraphicsError as exc:
            raise ProjectError(f"Graphics PNG rejected for {r['id']}: {exc}") from exc
        require(len(raw) == r['decoded_size'], 'Resource raw size changed: '+r['id'])
        packed = pack(raw)
        require(len(packed) <= r['capacity'], 'Resource exceeds fixed capacity: '+r['id'])
        require(decode(packed) == (raw,len(packed)), 'Resource codec roundtrip failed: '+r['id'])
        if strict:
            require(hashlib.sha256(raw).hexdigest() == r['decoded_sha256'],
                    'Resource changed; run repack.py explicitly: '+r['id'])
            require(len(packed) == r['packed_size'],
                    'Packed resource size differs; run repack.py explicitly: '+r['id'])
        results.append((r, raw, packed))
    return results


def checksums(data):
    out = bytearray(data)
    out[0x14D] = (-sum(out[0x134:0x14D])-25)&255
    out[0x14E:0x150] = ((sum(out[:0x14E])+sum(out[0x150:]))&65535).to_bytes(2,'big')
    return bytes(out)


def verify_output(data, manifest):
    actual = fingerprints(data)
    for key in ('size','sha256'):
        require(actual[key] == manifest['target'][key], 'Output '+key+' does not match selected manifest')
    require(checksums(data) == data, 'Output header/global checksum mismatch')
    require(data[0x14C] == 1 and data[0x148] == 4, 'Revision/ROM size header mismatch')
    for at, value in ((0x37B1,'fa14d4a7c0'),(0x434B,'ea14d4'),(0x1418C,'3807')):
        expected = bytes.fromhex(value)
        require(data[at:at+len(expected)] == expected, 'Native Rev1 fix was changed')
    require(data[0x3DA1D:0x3DA27] == bytes.fromhex('0302eff8195308402534'),
            'Gallery bat descriptor/Rev1 animation pointer mismatch')
    return actual


def construct(base, manifest, strict_resources=True, verify_target=True):
    validate_manifest(manifest); validate_input(base, manifest)
    out = bytearray(base)
    out.extend(bytes([manifest['fill_byte']])*(manifest['target']['size']-len(out)))
    for p in manifest['patches']:
        at = p['offset']; old = bytes.fromhex(p['expected_hex']); new = bytes.fromhex(p['replacement_hex'])
        require(out[at:at+len(old)] == old, 'Patch preimage mismatch at '+hex(at))
        out[at:at+len(new)] = new
    for r,raw,packed in prepare_resources(manifest, strict_resources):
        at=r['offset']
        require(out[at:at+len(packed)] == b'\xff'*len(packed), 'Resource allocation is not empty')
        out[at:at+len(packed)] = packed
    result = checksums(out)
    if verify_target: verify_output(result, manifest)
    return result


def refreshed_manifest(base, manifest, version):
    require(version and version != manifest['release'], 'Choose a new edited release name')
    updated = copy.deepcopy(manifest); changes=[]
    for r,raw,packed in prepare_resources(updated, strict=False):
        new_raw = hashlib.sha256(raw).hexdigest()
        if new_raw != r['decoded_sha256']:
            changes.append(dict(id=r['id'],source=r['source'],
                                old_decoded_sha256=r['decoded_sha256'],
                                new_decoded_sha256=new_raw,
                                old_packed_size=r['packed_size'],
                                new_packed_size=len(packed)))
        r.update(decoded_size=len(raw),decoded_sha256=new_raw,packed_size=len(packed))
    require(changes, 'No raw resources changed; no edited manifest was created')
    updated['parent_release'] = manifest['release']; updated['release'] = version
    updated['resource_edits'] = changes
    result = construct(base, updated, verify_target=False)
    updated['target'] = fingerprints(result)
    verify_output(result, updated)
    return updated,result


def create_ips(before, after):
    out=bytearray(b'PATCH');i=0
    while i<len(after):
        if i<len(before) and before[i]==after[i]:i+=1;continue
        start=i;run=1
        while i+run<len(after) and run<65535 and after[i+run]==after[i]:run+=1
        if run>=4:
            out.extend(i.to_bytes(3,'big')+b'\0\0'+run.to_bytes(2,'big')+after[i:i+1]);i+=run;continue
        i+=1
        while i<len(after) and i-start<65535 and (i>=len(before) or before[i]!=after[i]):
            if after[i:i+4]==after[i:i+1]*4:break
            i+=1
        block=after[start:i];out.extend(start.to_bytes(3,'big')+len(block).to_bytes(2,'big')+block)
    out.extend(b'EOF');return bytes(out)


def apply_ips(before, patch):
    require(patch[:5]==b'PATCH','Invalid IPS header')
    out=bytearray(before);p=5
    while True:
        require(p+3<=len(patch),'Truncated IPS record')
        if patch[p:p+3]==b'EOF':p+=3;break
        require(p+5<=len(patch),'Truncated IPS record header')
        at=int.from_bytes(patch[p:p+3],'big');n=int.from_bytes(patch[p+3:p+5],'big');p+=5
        if n:
            require(p+n<=len(patch),'Truncated IPS literal');block=patch[p:p+n];p+=n
        else:
            require(p+3<=len(patch),'Truncated IPS RLE')
            n=int.from_bytes(patch[p:p+2],'big');require(n>0,'Empty IPS RLE');block=patch[p+2:p+3]*n;p+=3
        require(at+n<=0x80000,'IPS writes beyond supported ROM size')
        if len(out)<at+n:out.extend(b'\0'*(at+n-len(out)))
        out[at:at+n]=block
    if len(patch)-p==3:
        size=int.from_bytes(patch[p:p+3],'big');require(size<=len(out),'IPS truncation exceeds output');out=out[:size];p+=3
    require(p==len(patch),'Unexpected IPS trailing data')
    return bytes(out)


def write_output(path, data, protected=()):
    path=Path(path).resolve()
    require(path not in {Path(p).resolve() for p in protected}, 'Output would overwrite an input file')
    require(not path.is_relative_to((ROOT/'source').resolve()), 'Build outputs do not belong in source/')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    require(not temporary.exists(),'Temporary output already exists: '+temporary.name)
    try:
        temporary.write_bytes(data);temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()
    require(path.read_bytes()==data,'Output verification failed after write')


def dump_json(path, value, protected=()):
    write_output(path,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),protected)


def dump_manifest(path, manifest, protected=()):
    dump_json(path, manifest_storage(manifest), protected)
