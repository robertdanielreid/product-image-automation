#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
STORE_ROOT="${1:-$PACKAGE_ROOT/webstore-output}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
mkdir -p "$STORE_ROOT" "$PACKAGE_ROOT/output"
"$PYTHON_BIN" "$PACKAGE_ROOT/scripts/network_preflight.py"
"$PYTHON_BIN" -m pip install -r "$PACKAGE_ROOT/requirements.txt"
"$PYTHON_BIN" "$PACKAGE_ROOT/scripts/acquire_all_20076_real_images.py" \
  --package-root "$PACKAGE_ROOT" --store-root "$STORE_ROOT" \
  --workers "${IMAGE_WORKERS:-12}" --search-fallback --resume --limit 20076
"$PYTHON_BIN" "$PACKAGE_ROOT/scripts/build_review_dashboard.py" --package-root "$PACKAGE_ROOT" --store-root "$STORE_ROOT"
"$PYTHON_BIN" "$PACKAGE_ROOT/scripts/validate_all_20076_real_images.py" --package-root "$PACKAGE_ROOT" --store-root "$STORE_ROOT" --materialize-approved --expected-count 20076
