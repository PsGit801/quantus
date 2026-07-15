#!/usr/bin/env bash
#
# Weekly digest: live results (how fired alerts are playing out) + a health check,
# pushed to Telegram/Discord. Meant for a weekly cron.
#   scripts/digest.sh --dry-run     # print instead of send
#   scripts/digest.sh --days 7      # summarise the last 7 days (default)
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

exec .venv/bin/python -m ddbot.digest "$@"
