# SPDX-License-Identifier: MIT
"""ROM-free codec and packaged-resource self-test using only the standard library."""
import sys
import common
from hal_codec import decode, pack


def main():
    cases = (b'', b'A', b'A'*1024, b'AB'*600, bytes(range(256))*3,
             bytes((i*73+19)&255 for i in range(1500)))
    for raw in cases:
        packed = pack(raw)
        common.require(decode(packed) == (raw, len(packed)), 'HAL roundtrip failed')
    for invalid in (b'', b'\x00', b'\xe0'):
        try:
            decode(invalid)
        except ValueError:
            pass
        else:
            raise common.ProjectError('Truncated HAL stream was accepted')
    before = b'synthetic baseline, not a game ROM'
    targets = (before, before + b'Z'*2048 + bytes(range(256)), b'changed' + before)
    for after in targets:
        patch = common.create_ips(before, after)
        common.require(common.apply_ips(before, patch) == after, 'IPS roundtrip failed')
    manifest = common.load_manifest()
    resources = common.prepare_resources(manifest)
    print(f'SELFTEST=PASS HAL_CASES={len(cases)} MALFORMED_HAL=3 IPS_CASES={len(targets)} RESOURCES={len(resources)} NO_ROM=YES')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print('SELFTEST=ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
