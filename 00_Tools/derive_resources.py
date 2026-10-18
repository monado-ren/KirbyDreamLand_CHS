# SPDX-License-Identifier: MIT
"""Materialise derived 2bpp tile/map bytes from the PNG graphics sources.

The release build reads ``03_Image/graphics/*.png`` directly.  This command only
writes the derived binary form into a gitignored directory so maintainers can
inspect or diff it against earlier snapshots; it never edits tracked files.
"""
import argparse
from pathlib import Path
import sys

import common


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=common.DEFAULT_MANIFEST)
    parser.add_argument('--output', type=Path, default=common.ROOT / 'build/resources')
    args = parser.parse_args()
    manifest = common.load_manifest(args.manifest)
    args.output.mkdir(parents=True, exist_ok=True)
    total = 0
    for entry, raw, _packed in common.prepare_resources(manifest):
        (args.output / (entry['id'] + '.bin')).write_bytes(raw)
        total += len(raw)
    print('DERIVE=PASS RESOURCES=' + str(len(manifest['resources']))
          + ' BYTES=' + str(total) + ' OUTPUT=' + str(args.output.resolve()))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print('DERIVE=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
