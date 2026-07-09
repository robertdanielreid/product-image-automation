#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "Run ONE_CLICK_SETUP.command first."; read -r; exit 1; fi
.venv/bin/python scripts/review_server.py --package-root "$PWD" --store-root "$PWD/webstore_image_output"
