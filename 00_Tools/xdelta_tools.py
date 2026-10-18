# SPDX-License-Identifier: MIT
"""Invoke an external xdelta3 without embedded filenames or ambient options."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import common


def executable(value):
    value = value or os.environ.get('XDELTA3', 'xdelta3')
    found = shutil.which(value)
    common.require(found is not None, 'xdelta3 not found; install it or use --xdelta PATH')
    return str(Path(found).resolve())


def run(exe, arguments):
    env = dict(os.environ)
    env.pop('XDELTA', None)
    result = subprocess.run([exe, *map(str, arguments)], capture_output=True,
                            env=env, timeout=120)
    text = (result.stdout + result.stderr).decode('utf-8', errors='replace').strip()
    common.require(result.returncode == 0, 'xdelta3 failed: '+text)
    return text


def version(exe):
    text = run(exe, ['-V'])
    match = re.search(r'Xdelta version (\d+)\.(\d+)\.(\d+)', text)
    common.require(match is not None, 'Unrecognized xdelta3 version')
    parts = tuple(map(int, match.groups()))
    common.require(parts >= (3, 0, 0), 'xdelta3 version 3 or newer is required')
    return parts


def encode(exe, base, rom, patch):
    ver = version(exe)
    # Xdelta 3.2 enables armor by default. Disable it for legacy VCDIFF readers.
    args = ['-a'] if ver >= (3, 2, 0) else []
    run(exe, args+['-e', '-9', '-S', 'none', '-A', '-D', '-s', base, rom, patch])
    data = Path(patch).read_bytes()
    common.require(data[:5] == bytes.fromhex('d6c3c40000'),
                   'Expected classic VCDIFF without secondary codec or application header')
    return '.'.join(map(str,ver))


def decode(exe, base, patch, output):
    run(exe, ['-d', '-D', '-R', '-s', base, patch, output])
