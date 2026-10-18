# SPDX-License-Identifier: MIT
"""Regenerate the editable font-subset JSON files from pinned upstream sources.

The repository does not commit derived glyph bitmaps.  This script downloads
the pinned upstream bitmap-font sources (byte SHA-256 pinned), extracts the
glyphs used by the project, and writes ``assets/fonts/*.json`` (gitignored).
The character sets below are project data: which characters need the 12px
headline font and the 8px HUD font.

Requirements:
    python -m pip install -r requirements-dev.txt   # kbitfont==0.0.4
    python tools/fetch_fonts.py [--check]
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import common

ROOT = common.ROOT
FONT_DIR = ROOT / 'assets' / 'fonts'
CACHE = ROOT / 'build' / 'fonts'

EXPECTED_GLYPHS_SHA256 = {
    'jpzh-bitmap-12.json':
        '5e14f4d8957e15fb7cabe2d1dd9284e6fc2ff7f31ab7f19c1719de52ab3a0af9',
    'jpzh-bitmap-hud-8.json':
        '6c1f78b9e605bd99c4c85d1b0a83a0390068836661e0ac2b5921cb7d4ff8b64f',
}

ZL_KBITX_URL = ('https://raw.githubusercontent.com/Astro-2539/ZLabs-Pixel-12px/'
                'main/data/ZLabsPixel_12px_M_CN.kbitx')
ZL_KBITX_SHA256 = '94df0996411155ff007afc363939391fcc6e3d325d70406ea4826864a29a11a5'
ZL_META = {
    'format_version': 1,
    'family': 'JPZH Bitmap 12',
    'description': '项目使用的 12px 位图子集；不是完整字体。由 tools/fetch_fonts.py 从上游 '
                   'ZLabs Pixel 12px M CN 源文件生成。',
    'license': 'OFL-1.1',
    'license_file': '../../LICENSES/ZLabs-Pixel-12px-OFL.txt',
    'upstream_project': 'https://github.com/Astro-2539/ZLabs-Pixel-12px',
    'upstream_font': 'Z Labs Pixel 12px M CN',
    'upstream_copyright': 'Copyright (c) 2023-2025, Astro_2539',
    'upstream_reserved_font_name': 'Z工坊/ZLabs',
    'upstream_font_sha256': ZL_KBITX_SHA256,
    'height': 12,
    'digits_included': False,
    'pixel_format': 'rows of 0=background and 1=ink; no antialiasing',
}

FUSION_ZIP_URL = ('https://github.com/TakWolf/fusion-pixel-font/releases/download/'
                  '2026.09.01/fusion-pixel-font-8px-monospaced-bdf-v2026.09.01.zip')
FUSION_ZIP_SHA256 = 'c2e1fca87eafb0f5dbae64378a8a73f85499479ce67616e6eaa618f85c55f626'
FUSION_BDF = 'fusion-pixel-8px-monospaced-zh_hans.bdf'
FUSION_META = {
    'format_version': 1,
    'family': 'JPZH Bitmap HUD 8',
    'description': 'HUD 的八个 8×8 位图字形（含空格）；由 tools/fetch_fonts.py 从上游 '
                   'Fusion Pixel 8px Monospaced zh_hans 生成，不是完整中文字体。',
    'license': 'OFL-1.1',
    'license_files': ['../../LICENSES/Fusion-Pixel-OFL.txt',
                      '../../LICENSES/Fusion-Pixel-upstream/BoutiqueBitmap7x7-OFL.txt',
                      '../../LICENSES/Fusion-Pixel-upstream/Galmuri-LICENSE.txt',
                      '../../LICENSES/Fusion-Pixel-upstream/Misaki-misaki.txt',
                      '../../LICENSES/Fusion-Pixel-upstream/MisekiBitmap-LICENSE.txt'],
    'upstream_project': 'https://github.com/TakWolf/fusion-pixel-font',
    'upstream_release': '2026.09.01',
    'upstream_font': 'Fusion Pixel 8px Monospaced zh_hans',
    'upstream_copyright': 'Copyright (c) 2022, TakWolf',
    'upstream_font_sha256': FUSION_ZIP_SHA256,
    'height': 8,
    'pixel_format': 'rows of 0=background and 1=ink; no antialiasing',
}

# Project character sets (which characters are drawn with each bitmap font).
CHARSET_12 = 'P两乌乐云体像兄先光冒出刀刺力卡吐吓喔喳圆场城堡士声外大头子寄射小尖尸尼层居山屿岛帝带帽幽式弟弯弹怪惊戏扫把拉振效晕景暴本束树模武比泡波派测浮海游漂灵炮熊狂独猫王球瓜瓦生疯的眼睡石章笃箩箱糕结继续绿置翅耳胀胡膨舌芒菇菈葛葵蘑蛋蛙蝙蝠蟹试语谷豆贝贼躁连迪退配钸锥镜面音须额风飞骑骷髅鬼魔鱼鲁鸟鸡鹈鹕黑：'
CHARSET_HUD8 = ' 分卡比积'  # HUD glyphs incl. space


def _sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _download(url, sha256, cache_path):
    if cache_path.is_file() and _sha256_bytes(cache_path.read_bytes()) == sha256:
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request
    with urllib.request.urlopen(url, timeout=180) as response:
        payload = response.read()
    digest = _sha256_bytes(payload)
    common.require(digest == sha256, 'upstream SHA-256 mismatch for %s: %s' % (url, digest))
    cache_path.write_bytes(payload)
    return cache_path


def generate_zlabs(path):
    try:
        from kbitfont import KbitFont
    except ImportError as exc:
        raise common.ProjectError(
            'kbitfont is required for font regeneration; '
            'python -m pip install -r requirements-dev.txt') from exc
    font = KbitFont.load_kbitx(str(path))
    em_ascent = font.props.em_ascent
    glyphs = {}
    for char in CHARSET_12:
        glyph = font.characters.get(ord(char))
        common.require(glyph is not None, 'upstream ZLabs font lacks %r' % char)
        width = glyph.advance
        rows = ['0' * width for _ in range(em_ascent - glyph.y)]
        for row in glyph.bitmap:
            ink = ''.join('1' if value == 255 else '0' for value in row)
            rows.append(('0' * glyph.x + ink)[:width].ljust(width, '0'))
        while len(rows) < 12:
            rows.append('0' * width)
        common.require(len(rows) == 12, 'glyph %r does not fit 12 rows' % char)
        glyphs[char] = {'width': width, 'rows': rows}
    meta = dict(ZL_META)
    meta['glyph_count'] = len(glyphs)
    return {'meta': meta, 'glyphs': glyphs}


def parse_bdf_glyph(lines, codepoint, height):
    for index, line in enumerate(lines):
        if line.strip() != 'ENCODING %d' % codepoint:
            continue
        block = []
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].startswith('STARTCHAR'):
            block.append(lines[cursor])
            cursor += 1
        bbx = next(item for item in block if item.startswith('BBX')).split()
        width, glyph_height = int(bbx[1]), int(bbx[2])
        advance = int(next(item for item in block if item.startswith('DWIDTH')).split()[1])
        bitmap = block.index('BITMAP')
        rows = []
        for item in block[bitmap + 1:]:
            if item.strip() == 'ENDCHAR':
                break
            bits = bin(int(item, 16))[2:].zfill(len(item) * 4)[:width]
            rows.append(bits.ljust(advance, '0'))
        rows = ['0' * advance for _ in range(height - glyph_height)] + rows
        while len(rows) < height:
            rows.append('0' * advance)
        return {'width': advance, 'rows': rows}
    return None


def generate_fusion(zip_path, check=False):
    with zipfile.ZipFile(zip_path) as bundle:
        bdf = bundle.read(FUSION_BDF).decode('utf-8').splitlines()
    glyphs = {}
    for char in CHARSET_HUD8:
        glyph = parse_bdf_glyph(bdf, ord(char), 8)
        common.require(glyph is not None, 'upstream Fusion font lacks %r' % char)
        glyphs[char] = glyph
    meta = dict(FUSION_META)
    meta['glyph_count'] = len(glyphs)
    return {'meta': meta, 'glyphs': glyphs}


def glyphs_digest(glyphs):
    payload = json.dumps(glyphs, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true',
                        help='only verify that regeneration reproduces the current files')
    args = parser.parse_args(argv)
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    zl = _download(ZL_KBITX_URL, ZL_KBITX_SHA256, CACHE / 'ZLabsPixel_12px_M_CN.kbitx')
    fusion = _download(FUSION_ZIP_URL, FUSION_ZIP_SHA256, CACHE / 'fusion8.zip')
    outputs = {
        'jpzh-bitmap-12.json': generate_zlabs(zl),
        'jpzh-bitmap-hud-8.json': generate_fusion(fusion),
    }
    for name, data in outputs.items():
        digest = glyphs_digest(data['glyphs'])
        if args.check:
            common.require(digest == EXPECTED_GLYPHS_SHA256[name],
                           'generated glyphs differ from the pinned %s' % name)
        else:
            (FONT_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
        print('FONT=%s GLYPHS=%d SHA256_GLYPHS=%s'
              % (name, len(data['glyphs']), digest[:16]))
    print('FONTS=PASS SOURCE=UPSTREAM GENERATED=%d' % len(outputs))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print('FONTS=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
