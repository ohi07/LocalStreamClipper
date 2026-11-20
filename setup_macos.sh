#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo 'Python 3.11 or 3.12 required'; exit 1; }
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg: brew install ffmpeg'; exit 1; }
python3 - <<'PYV'
import sys
assert (3,11) <= sys.version_info[:2] <= (3,12), 'Use Python 3.11 or 3.12'
PYV
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
mkdir -p data
printf '\nReady: ./start_macos.sh and open http://127.0.0.1:8501\n'
