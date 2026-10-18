# SPDX-License-Identifier: MIT
"""Apply a release patch to checked Rev1 input; verify before writing output."""
import argparse
from pathlib import Path
import sys
import tempfile
import subprocess
import common
import xdelta_tools


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=common.ROOT/'baserom.gb')
    p.add_argument('--patch',type=Path,default=common.ROOT/'patches/KirbyDreamLand_CHS-Monado.xdelta3')
    p.add_argument('--output',type=Path,default=common.ROOT/'KirbyDreamLand_CHS-Monado.gb')
    p.add_argument('--manifest',type=Path,default=common.DEFAULT_MANIFEST)
    p.add_argument('--xdelta')
    a=p.parse_args();m=common.load_manifest(a.manifest)
    base=a.rom.read_bytes();common.validate_input(base,m)
    exe=xdelta_tools.executable(a.xdelta)
    with tempfile.TemporaryDirectory(prefix='kirby-apply-') as folder:
        d=Path(folder);b=d/'base.gb';patch=d/'patch.xdelta3';result=d/'result.gb'
        b.write_bytes(base);patch.write_bytes(a.patch.read_bytes())
        xdelta_tools.decode(exe,b,patch,result)
        out=result.read_bytes();common.verify_output(out,m)
    common.require(a.rom.read_bytes()==base,'Base ROM changed during patching')
    common.write_output(a.output,out,(a.rom,a.patch,a.manifest))
    print('APPLY=PASS SHA256='+common.fingerprints(out)['sha256'])
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
        print('APPLY=ERROR '+str(exc),file=sys.stderr);sys.exit(1)
