#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
START="${1:?start index required}"
COUNT="${2:?count required}"
OUT="${3:-$ROOT/cloud-output/chunk-$START}"
META="$OUT/chunk-metadata"
mkdir -p "$META" "$OUT/staging"
python3 -m pip install -r "$ROOT/requirements-v33.txt"
python3 -m playwright install chromium 2>/dev/null || true
python3 "$ROOT/scripts/acquire_all_20076_real_images.py" \
  --package-root "$ROOT" --store-root "$OUT" --results-dir "$META" \
  --workers "${IMAGE_WORKERS:-12}" --search-fallback --resume \
  --start "$START" --limit "$COUNT"
python3 "$ROOT/scripts/verify_image_paths.py" \
  --package-root "$ROOT" --artifact-root "$OUT" --start "$START" --limit "$COUNT"
