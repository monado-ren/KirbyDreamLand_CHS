# SPDX-License-Identifier: MIT
"""Verify output fingerprint and checksums; optionally verify all base hashes."""
import argparse
from pathlib import Path
import sys
import change_surface
import common


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=common.ROOT/'KirbyDreamLand_CHS-Monado.gb')
    p.add_argument('--base',type=Path,help='Also require exact size, MD5, SHA-1 and SHA-256 of the Rev1 base')
    p.add_argument('--manifest',type=Path,default=common.DEFAULT_MANIFEST)
    a=p.parse_args();manifest=common.load_manifest(a.manifest)
    if a.manifest.resolve()==common.DEFAULT_MANIFEST.resolve():
        change_surface.verify(change_surface.load_spec(),manifest)
    if a.base:common.validate_input(a.base.read_bytes(),manifest)
    actual=common.verify_output(a.rom.read_bytes(),manifest)
    print('VERIFY=PASS RELEASE='+manifest['release']+' SHA256='+actual['sha256'])
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:
        print('VERIFY=ERROR '+str(exc),file=sys.stderr);sys.exit(1)
