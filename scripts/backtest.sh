#!/usr/bin/env bash
#
# Backtest the double-bottom strategy over history. Examples:
#   scripts/backtest.sh --timeframe 1d --history-bars 1000
#   scripts/backtest.sh --timeframe 1wk --target r_multiple --r-target 2 --csv trades.csv
#   scripts/backtest.sh --timeframe 1d --walk-forward 4   # edge stable across time?
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

exec .venv/bin/python -m ddbot.backtest "$@"
