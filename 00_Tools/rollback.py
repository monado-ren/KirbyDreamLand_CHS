# SPDX-License-Identifier: MIT
"""Restore a separate localized test copy from the user's verified base ROM."""
import argparse
from pathlib import Path
import sys
import common


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=common.ROOT/'baserom.gb')
    p.add_argument('--target',type=Path,required=True,help='A separate localized copy to restore')
    a=p.parse_args();m=common.load_manifest()
    base=a.base.read_bytes();common.validate_input(base,m)
    common.require(a.target.resolve() not in {a.base.resolve(),(common.ROOT/m['default_output']).resolve()},
                   'Rollback must use a separate test copy, not the input or main build output')
    common.verify_output(a.target.read_bytes(),m)
    common.write_output(a.target,base,(a.base,common.DEFAULT_MANIFEST))
    common.validate_input(a.target.read_bytes(),m)
    common.require(a.base.read_bytes()==base,'Base ROM changed')
    print('ROLLBACK=PASS RESTORED=JAPAN_REV1_UNLOCALIZED SHA256='+common.fingerprints(base)['sha256'])
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:
        print('ROLLBACK=ERROR '+str(exc),file=sys.stderr);sys.exit(1)
