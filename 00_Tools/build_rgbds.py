# SPDX-License-Identifier: MIT
"""Build the pinned RGBDS toolchain from source into build/rgbds.

RGBDS is only needed to (re)assemble the instruction-level patch in
``06_ProgramFix/patches/`` and to verify the pinned bytes.  The script downloads the
pinned upstream source tarball, checks its SHA-256, compiles it with ``make``
and installs ``rgbasm``/``rgblink`` (plus ``rgbfix``/``rgbgfx`` when built)
into ``build/rgbds`` (gitignored).

Requirements: a C++ toolchain and ``make``.  Nothing is committed to the repo.

Usage:
    python 00_Tools/build_rgbds.py [--force] [--jobs N] [--prefix DIR]
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

import common

VERSION = '1.0.4'
URL = ('https://github.com/gbdev/rgbds/releases/download/'
       'v%s/rgbds-source.tar.gz' % VERSION)
SHA256 = '17a92be6ef6b3c15b90ef01808359d981c5399b19d7ba17aa36e676aa0911e04'
TOOLS = ('rgbasm', 'rgblink', 'rgbfix', 'rgbgfx')


def _download(cache):
    archive = cache / ('rgbds-%s-source.tar.gz' % VERSION)
    if archive.is_file() and _sha256(archive) == SHA256:
        print('RGBDS_CACHE=HIT FILE=' + str(archive))
        return archive
    cache.mkdir(parents=True, exist_ok=True)
    print('RGBDS_DOWNLOAD=' + URL)
    with urllib.request.urlopen(URL, timeout=120) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    common.require(digest == SHA256,
                   'RGBDS source SHA-256 mismatch: ' + digest)
    archive.write_bytes(payload)
    print('RGBDS_CACHE=WROTE SHA256=' + digest)
    return archive


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _versions(prefix):
    versions = {}
    for tool in ('rgbasm', 'rgblink'):
        exe = prefix / tool
        if not exe.is_file():
            return None
        try:
            text = subprocess.run([str(exe), '--version'], capture_output=True,
                                  text=True, check=True).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        versions[tool] = text.strip()
    return versions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--prefix', type=Path, default=common.ROOT / 'build' / 'rgbds')
    parser.add_argument('--cache', type=Path, default=common.ROOT / 'build' / 'cache')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--force', action='store_true', help='rebuild even if cached')
    args = parser.parse_args(argv)
    prefix = args.prefix.resolve()
    expected = {'rgbasm': 'v' + VERSION, 'rgblink': 'v' + VERSION}
    versions = None if args.force else _versions(prefix)
    if versions is not None and all(expected[tool] in versions[tool] for tool in expected):
        print('RGBDS=PASS VERSION=%s PREFIX=%s CACHED=YES' % (VERSION, prefix))
        return 0

    source_root = common.ROOT / 'build' / 'rgbds-src'
    if args.force and source_root.exists():
        shutil.rmtree(source_root)
    archive = _download(args.cache)
    source_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as bundle:
        bundle.extractall(source_root, filter='data')
    entries = [entry for entry in source_root.iterdir() if entry.is_dir()]
    start = entries[0] if len(entries) == 1 else source_root
    common.require((start / 'Makefile').is_file(),
                   'RGBDS source archive has no Makefile')
    print('RGBDS_BUILD=START JOBS=%d' % args.jobs)
    subprocess.run(['make', '-j%d' % max(1, args.jobs)], cwd=start, check=True)
    prefix.mkdir(parents=True, exist_ok=True)
    installed = []
    for tool in TOOLS:
        exe = start / tool
        if exe.is_file():
            shutil.copy2(exe, prefix / tool)
            installed.append(tool)
    common.require({'rgbasm', 'rgblink'} <= set(installed),
                   'RGBDS build did not produce rgbasm/rgblink')
    versions = _versions(prefix)
    common.require(versions is not None, 'built RGBDS cannot run')
    print('RGBDS=PASS VERSION=%s PREFIX=%s TOOLS=%s BUILT=YES'
          % (VERSION, prefix, ','.join(installed)))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError,
            urllib.error.URLError) as exc:
        print('RGBDS=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
