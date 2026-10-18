#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
exec "${PYTHON:-python}" 00_Tools/rollback.py "$@"
