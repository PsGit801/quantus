#!/usr/bin/env bash
#
# Watchlist management CLI wrapper. Intended for hermes/qwen (or you) to call:
#   scripts/watchlist.sh list
#   scripts/watchlist.sh add PLTR COIN
#   scripts/watchlist.sh remove TSLA
#
# Self-contained: resolves project dir, loads .env, uses the venv.
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec .venv/bin/python -m ddbot.watchlist "$@"
