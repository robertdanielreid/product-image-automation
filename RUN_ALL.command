#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "Run ONE_CLICK_SETUP.command first."; read -r; exit 1; fi
set -a; [ -f .env ] && source .env; set +a
mkdir -p webstore_image_output logs
CMD=(.venv/bin/python scripts/master_pipeline.py --package-root "$PWD" --store-root "$PWD/webstore_image_output")
set +e
if command -v caffeinate >/dev/null 2>&1; then caffeinate -dimsu "${CMD[@]}"; else "${CMD[@]}"; fi
CODE=$?
set -e
echo "Run finished with exit code $CODE. Open STATUS_REPORT.html."
open STATUS_REPORT.html 2>/dev/null || true
read -r -p "Press Return to close..." _
exit $CODE
