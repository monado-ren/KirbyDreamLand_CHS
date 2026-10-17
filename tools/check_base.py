# SPDX-License-Identifier: MIT
"""Validate the one supported original ROM without producing output."""
import argparse
from pathlib import Path
import sys
import common


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=common.ROOT/'baserom.gb')
    a=p.parse_args()
    result=common.validate_input(a.rom.read_bytes(),common.load_manifest())
    print('BASELINE=PASS MD5='+result['md5']+' SHA1='+result['sha1']+' SHA256='+result['sha256'])
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:
        print('BASELINE=ERROR '+str(exc),file=sys.stderr);sys.exit(1)
