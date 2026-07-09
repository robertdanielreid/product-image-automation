#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
STORE_ROOT="${1:-$PACKAGE_ROOT/webstore-output}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" "$PACKAGE_ROOT/scripts/validate_all_20076_real_images.py" \
  --package-root "$PACKAGE_ROOT" --store-root "$STORE_ROOT" \
  --materialize-approved --expected-count 20076
