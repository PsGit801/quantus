#!/usr/bin/env bash
#
# Telegram watchlist sync — one-shot, meant to run on a frequent scheduler
# (hermes cron, e.g. every 2 minutes). Polls Telegram for /add /remove /list
# commands and button taps, updates the DB watchlist, and exits.
#
# Self-contained like scripts/run.sh: resolves project dir, loads .env, uses the venv.
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

exec .venv/bin/python -m ddbot.sync -v "$@"
