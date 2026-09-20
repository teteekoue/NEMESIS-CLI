#!/usr/bin/env bash
# Lance l'interface web NEMESIS sur toutes les interfaces pour un preview local.
set -euo pipefail
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" web_server.py --host "${NEMESIS_WEB_HOST:-0.0.0.0}" --port "${PORT:-8000}" "$@"
