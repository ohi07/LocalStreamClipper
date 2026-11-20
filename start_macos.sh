#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo 'Run ./setup_macos.sh first'; exit 1; }
exec .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port "${PORT:-8501}"
