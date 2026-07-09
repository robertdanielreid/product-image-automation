#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"

echo "Product Image Automation V33 setup"
echo "This installs a private Python environment and Chromium inside this folder."

PY=""
if command -v python3 >/dev/null 2>&1; then
  if python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3,10) else 1)
PY
  then PY="$(command -v python3)"; fi
fi

if [ -z "$PY" ]; then
  echo "Python 3.10+ was not found. Installing the official uv Python manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  uv python install 3.12
  uv venv --python 3.12 .venv
else
  "$PY" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-v33.txt
python -m playwright install chromium

if [ ! -f .env ]; then cp .env.example .env; fi
if ! grep -Eq '^GEMINI_API_KEY=.+$' .env; then
  echo
  echo "Paste your Gemini API key. It will be stored only in this local .env file."
  read -r -s -p "Gemini API key: " KEY
echo
  if [ -z "$KEY" ]; then echo "No key entered. Add it later to .env."; else
    python - "$KEY" <<'PY'
from pathlib import Path
import sys
p=Path('.env');key=sys.argv[1];lines=p.read_text().splitlines();out=[];done=False
for line in lines:
    if line.startswith('GEMINI_API_KEY='):
        out.append('GEMINI_API_KEY='+key);done=True
    else:out.append(line)
if not done:out.append('GEMINI_API_KEY='+key)
p.write_text('\n'.join(out)+'\n')
PY
    chmod 600 .env
  fi
fi

chmod +x ./*.command scripts/*.py *.sh 2>/dev/null || true
python scripts/network_preflight.py || true

echo
echo "Setup complete. Double-click RUN_ALL.command."
echo "The run is resumable; closing it does not lose completed work."
read -r -p "Press Return to close..." _
