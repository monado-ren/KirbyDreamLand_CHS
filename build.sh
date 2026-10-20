#!/bin/sh
# Build the localized ROM from source in this tree.
#
# Needs no network access at build time beyond the one RGBDS source tarball,
# which is downloaded once into build/ and then cached.  Produces the same
# 524288-byte ROM as the tracked xdelta3 patch.
#
# Usage:
#   ./build.sh              # incremental; skips RGBDS if already built
#   ./build.sh --force      # rebuild RGBDS from scratch
#   ./build.sh --patch      # also regenerate patches/*.xdelta3 (needs xdelta3)
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

FORCE=
PATCH=
for arg in "$@"; do
    case $arg in
        --force) FORCE=--force ;;
        --patch) PATCH=1 ;;
        -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'BUILD=ERROR unknown option: %s\n' "$arg" >&2; exit 1 ;;
    esac
done

die() { printf 'BUILD=ERROR %s\n' "$1" >&2; exit 1; }

# --- prerequisites ---------------------------------------------------------
PYTHON=${PYTHON:-python3}
command -v "$PYTHON" >/dev/null 2>&1 || die "python3 not found"
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' ||
    die "$("$PYTHON" -V 2>&1) is too old; Python 3.10 or newer is required"

if [ -z "$FORCE" ] && [ ! -x build/rgbds/rgbasm ]; then
    command -v make >/dev/null 2>&1 || die "make not found; it is needed to build RGBDS"
    command -v c++ >/dev/null 2>&1 || die "a C++ compiler not found; it is needed to build RGBDS"
fi

[ -f baserom.gb ] || die "baserom.gb not found; put the Japanese Rev 1 ROM in $ROOT"

export PYTHONPATH="$ROOT/build/pylibs:$ROOT/00_Tools${PYTHONPATH:+:$PYTHONPATH}"

# --- RGBDS (cached under build/, never committed) ---------------------------
printf 'STEP=rgbds\n'
# RGBDS compiles a handful of large C++ translation units.  Using nproc lets a
# many-core machine start them all at once and get OOM-killed: observed on a
# 20-core box, where the default build died and --jobs 2 and 4 both succeeded.
# Parallelism above 4 buys little here, so cap it and let RGBDS_JOBS override.
RGBDS_JOBS=${RGBDS_JOBS:-4}
case $RGBDS_JOBS in
    ''|*[!0-9]*) die "RGBDS_JOBS must be a positive integer, got: $RGBDS_JOBS" ;;
esac
[ "$RGBDS_JOBS" -ge 1 ] || die "RGBDS_JOBS must be at least 1"
"$PYTHON" 00_Tools/build_rgbds.py --jobs "$RGBDS_JOBS" ${FORCE:+--force} ||
    die "RGBDS build failed; see the output above"

# --- the ROM --------------------------------------------------------------
printf 'STEP=build\n'
"$PYTHON" 00_Tools/build.py || die "build failed"

printf 'STEP=verify\n'
"$PYTHON" 00_Tools/verify.py || die "verify failed"

if [ -n "$PATCH" ]; then
    printf 'STEP=patch\n'
    command -v xdelta3 >/dev/null 2>&1 ||
        die "xdelta3 not found; install it or drop --patch"
    "$PYTHON" 00_Tools/release.py || die "release failed"
fi

printf 'BUILD=OK\n'
