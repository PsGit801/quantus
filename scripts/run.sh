#!/usr/bin/env bash
#
# Entrypoint for schedulers (hermes / cron). Self-contained: resolves the project
# directory, loads secrets from .env, uses the project venv, and runs the bot.
# Point hermes (or a crontab line) at this script — it needs no other configuration.
#
# Any extra args are passed through to the bot, e.g.:
#   scripts/run.sh --dry-run       # preview without sending
#
set -euo pipefail

# This script lives in <project>/scripts/, so the project root is one level up.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Make the package importable without a system-wide install.
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# The bot also loads .env itself; sourcing here covers callers that skip it.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec .venv/bin/python -m ddbot.run -v --config config/config.yaml "$@"
