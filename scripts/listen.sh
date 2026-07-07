#!/usr/bin/env bash
#
# Always-on Telegram listener. Runs in the foreground and long-polls Telegram so
# watchlist buttons/commands respond instantly. Keep it alive with launchd (see
# deploy/ai.ddbot.telegram-listener.plist), or run manually for testing.
#
# Do NOT run this at the same time as the ddbot-watchlist-sync cron — only one
# process may poll Telegram for a given bot token.
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

exec .venv/bin/python -m ddbot.listen "$@"
