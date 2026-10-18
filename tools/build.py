# SPDX-License-Identifier: MIT
"""Compile the reproducible Rev1 localization snapshot using Python 3.10+."""
import argparse
from pathlib import Path
import sys
import change_surface
import common


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,default=common.ROOT/'baserom.gb')
    parser.add_argument('--output',type=Path,default=common.ROOT/'KirbyDreamLand_CHS-Monado.gb')
    parser.add_argument('--manifest',type=Path,default=common.DEFAULT_MANIFEST)
    parser.add_argument('--patch-output',type=Path,help='Optional IPS output; always based on pristine Rev1')
    args=parser.parse_args()
    manifest=common.load_manifest(args.manifest);base=args.rom.read_bytes()
    if args.manifest.resolve()==common.DEFAULT_MANIFEST.resolve():
        change_surface.verify(change_surface.load_spec(),manifest)
    output=common.construct(base,manifest)
    protected=(args.rom,args.manifest)
    common.require(args.patch_output is None or args.patch_output.resolve()!=args.output.resolve(),
                   'ROM and patch output paths must differ')
    common.write_output(args.output,output,protected)
    if args.patch_output:
        patch=common.create_ips(base,output)
        common.require(common.apply_ips(base,patch)==output,'IPS replay mismatch')
        common.write_output(args.patch_output,patch,protected)
    common.require(args.rom.read_bytes()==base,'Base ROM changed during build')
    print('BUILD=PASS RELEASE='+manifest['release']+' SHA256='+common.fingerprints(output)['sha256'])
    print('OUTPUT='+str(args.output.resolve()))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:
        print('BUILD=ERROR '+str(exc),file=sys.stderr);sys.exit(1)
