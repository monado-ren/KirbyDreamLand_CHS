# SPDX-License-Identifier: MIT
"""Explicitly accept edited PNG tile/map sources into a separate dev manifest.

This does not rasterize translations, move pointers, resize decoded resources
or change tile counts. Each recompressed resource must fit its fixed bank capacity.
The official release manifest is preserved. Keep the modified PNG sources
alongside the generated dev manifest to reproduce that development build.
"""
import argparse
from pathlib import Path
import sys
import common


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=common.ROOT/'baserom.gb')
    p.add_argument('--manifest',type=Path,default=common.DEFAULT_MANIFEST)
    p.add_argument('--version',required=True,help='A new name, e.g. v0.5.1-custom.1')
    p.add_argument('--manifest-out',type=Path,default=common.ROOT/'build/manifest.edited.json')
    p.add_argument('--output',type=Path,default=common.ROOT/'build/KirbyDreamLand_CHS-edited.gb')
    a=p.parse_args();manifest=common.load_manifest(a.manifest);base=a.rom.read_bytes()
    updated,output=common.refreshed_manifest(base,manifest,a.version)
    protected=(a.rom,a.manifest,common.DEFAULT_MANIFEST)
    common.require(a.output.resolve()!=a.manifest_out.resolve(),'ROM and manifest paths must differ')
    common.write_output(a.output,output,protected)
    common.dump_manifest(a.manifest_out,updated,protected)
    common.require(a.rom.read_bytes()==base,'Base ROM changed during repack')
    print('REPACK=PASS RELEASE='+updated['release']+' CHANGED_RESOURCES='+str(len(updated['resource_edits'])))
    print('TARGET_SHA256='+updated['target']['sha256'])
    print('MANIFEST='+str(a.manifest_out.resolve()))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:
        print('REPACK=ERROR '+str(exc),file=sys.stderr);sys.exit(1)
