#!/usr/bin/env bash
#
# Signal-outcome report: how did the bot's fired alerts actually play out?
#   scripts/journal.sh                    # all fired signals
#   scripts/journal.sh --since 2026-07-03 # only post-go-live
#   scripts/journal.sh --csv journal.csv
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

exec .venv/bin/python -m ddbot.journal "$@"
