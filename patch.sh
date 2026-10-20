#!/bin/sh
# Apply the Chinese localization patch to a Japanese Rev 1 ROM.
#
# Only needs xdelta3 and the tracked patch file -- no RGBDS, no Python
# packages, no network.  Verifies the input before patching and the output
# afterwards, so a wrong or corrupt baserom.gb fails loudly instead of
# producing a ROM that silently differs.
#
# Usage:
#   ./patch.sh                       # default paths, output next to baserom.gb
#   ./patch.sh path/to/baserom.gb    # explicit input
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INPUT=${1:-$ROOT/baserom.gb}
PATCH=$ROOT/patches/KirbyDreamLand_CHS-Monado.xdelta3
OUTPUT=$ROOT/KirbyDreamLand_CHS-Monado.gb

BASE_SHA256=c4c6aff6242116c4f26bdcf3343b6c27836010853b8753da8b0cb953a200834a
ROM_SHA256=179a1943511e04e7cb63897c1b8a56442715428f382c343031a5a84ddbf95005

die() { printf 'PATCH=ERROR %s\n' "$1" >&2; exit 1; }

XDELTA=${XDELTA3:-xdelta3}
command -v "$XDELTA" >/dev/null 2>&1 ||
    die "xdelta3 not found; install it (apt install xdelta3 / brew install xdelta), or set XDELTA3"
command -v sha256sum >/dev/null 2>&1 || die "sha256sum not found"

[ -f "$INPUT" ] || die "input ROM not found: $INPUT"
[ -f "$PATCH" ] || die "patch not found: $PATCH"

# Refuse to overwrite a previous result rather than clobbering it silently.
[ -e "$OUTPUT" ] && die "output already exists, move it away first: $OUTPUT"

actual=$(sha256sum "$INPUT" | cut -d' ' -f1)
[ "$actual" = "$BASE_SHA256" ] ||
    die "input is not Japanese Rev 1 (expected $BASE_SHA256, got $actual)"

"$XDELTA" -d -s "$INPUT" "$PATCH" "$OUTPUT" || die "xdelta3 failed"

actual=$(sha256sum "$OUTPUT" | cut -d' ' -f1)
[ "$actual" = "$ROM_SHA256" ] || {
    rm -f "$OUTPUT"
    die "output does not match the expected ROM (got $actual)"
}

printf 'PATCH=PASS\n'
printf 'OUTPUT=%s\n' "$OUTPUT"
printf 'SHA256=%s\n' "$ROM_SHA256"
