#!/bin/sh
# Run every gate this tree has, in the order CI runs them, plus the ones that
# need artifacts CI cannot produce.
#
# A clean checkout can run the first group.  The second group needs the built
# ROM and, for the visual audit, an emulator capture package; it reports SKIP
# rather than pretending to have checked something it did not.
#
# Usage: ./check.sh            # everything available here
#        ./check.sh --fast     # skip the visual regression pass
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

FAST=
for arg in "$@"; do
    case $arg in
        --fast) FAST=1 ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'CHECK=ERROR unknown option: %s\n' "$arg" >&2; exit 1 ;;
    esac
done

PYTHON=${PYTHON:-python3}
export PYTHONPATH="$ROOT/build/pylibs:$ROOT/00_Tools${PYTHONPATH:+:$PYTHONPATH}"

failed=0
run() {
    name=$1; shift
    printf '\n=== %s ===\n' "$name"
    if "$@"; then :; else
        printf 'CHECK=FAIL %s\n' "$name" >&2
        failed=$((failed + 1))
    fi
}

# --- gates that need only the tree ----------------------------------------
run "public-tree"    "$PYTHON" 00_Tools/audit_public_tree.py

# --- gates that need the built ROM ----------------------------------------
if [ -f "$ROOT/KirbyDreamLand_CHS-Monado.gb" ]; then
    run "verify"         "$PYTHON" 00_Tools/verify.py
    run "change-surface" "$PYTHON" 00_Tools/change_surface.py check
    run "pages"          "$PYTHON" 00_Tools/pages.py render --check
    run "text-layout"    "$PYTHON" 00_Tools/text_layout.py check
    run "rom-pages"      "$PYTHON" 00_Tools/audit_rom_pages.py --write-check
    run "page-audit"     "$PYTHON" 00_Tools/audit_pages.py --check
    run "loader-timing"  "$PYTHON" 00_Tools/audit_loader_timing.py
    run "dead-loads"     "$PYTHON" 00_Tools/audit_dead_loads.py
    run "loader-payload" "$PYTHON" 00_Tools/audit_loader_payload.py
    # The suite builds against the ROM and needs RGBDS, so it belongs here rather
    # than with the tree-only gates: a bare checkout has neither.
    run "tests"          "$PYTHON" -m unittest discover -s tests -q
    run "selftest"       "$PYTHON" 00_Tools/selftest.py
    if [ -z "$FAST" ]; then
        # Without the emulator package this prints SKIP; with it, every captured
        # screen is compared against the page it should be showing.
        run "visual-regression" \
            "$PYTHON" 00_Tools/audit_visual_regression.py --allow-missing
    fi
else
    printf '\nRENDER/BUILD gates skipped: no built ROM (run ./build.sh)\n'
fi

if [ "$failed" -ne 0 ]; then
    printf '\nCHECK=FAIL failed=%d\n' "$failed" >&2
    exit 1
fi
printf '\nCHECK=PASS\n'
