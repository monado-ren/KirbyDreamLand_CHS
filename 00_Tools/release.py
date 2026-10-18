# SPDX-License-Identifier: MIT
"""Build the ROM and tracked xdelta3 patch, then verify exact patch replay."""
import argparse
from pathlib import Path
import sys
import tempfile
import subprocess
import common
import xdelta_tools


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, default=common.ROOT/'baserom.gb')
    p.add_argument('--output', type=Path, default=common.ROOT/'KirbyDreamLand_CHS-Monado.gb')
    p.add_argument('--patch', type=Path, default=common.ROOT/'patches/KirbyDreamLand_CHS-Monado.xdelta3')
    p.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    p.add_argument('--xdelta')
    a = p.parse_args()
    m = common.load_manifest(a.manifest)
    base = a.rom.read_bytes()
    common.validate_input(base,m)
    protected = {a.rom.resolve(), a.manifest.resolve()}
    common.require(a.output.resolve() != a.patch.resolve(), 'ROM and patch paths must differ')
    for path in (a.output, a.patch):
        common.require(path.resolve() not in protected, 'Output would overwrite an input file')
        common.require(not path.resolve().is_relative_to((common.ROOT/'03_Image').resolve()),
                       'Output must not overwrite source')
    exe = xdelta_tools.executable(a.xdelta)
    out = common.construct(base,m)
    with tempfile.TemporaryDirectory(prefix='kirby-patch-') as directory:
        d = Path(directory)
        b, r, patch, replay = (d/n for n in ('base.gb','out.gb','delta.xdelta3','replay.gb'))
        b.write_bytes(base); r.write_bytes(out)
        ver = xdelta_tools.encode(exe,b,r,patch)
        xdelta_tools.decode(exe,b,patch,replay)
        common.require(replay.read_bytes() == out, 'xdelta3 replay differs from source build')
        common.verify_output(replay.read_bytes(),m)
        patch_data = patch.read_bytes()
    common.require(a.rom.read_bytes() == base, 'Base ROM changed during build')
    common.write_output(a.output,out,protected)
    common.write_output(a.patch,patch_data,protected)
    print('RELEASE=PASS VERSION='+m['release']+' XDELTA='+ver)
    print('ROM_SHA256='+common.fingerprints(out)['sha256'])
    print('PATCH_SHA256='+common.fingerprints(patch_data)['sha256'])
    print('XDELTA_REPLAY=PASS BASE_UNCHANGED=PASS')
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print('RELEASE=ERROR '+str(exc),file=sys.stderr); sys.exit(1)
