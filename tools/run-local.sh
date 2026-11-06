#!/usr/bin/env bash
# Play Spin-a-Zoo in a window on this machine.
# Optional: SPINAZOO_WINDOW=1920x1080 SPINAZOO_PLAYERS=green:TL,blue:BR tools/run-local.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export SPINAZOO_WINDOW="${SPINAZOO_WINDOW:-1280x720}"
exec .venv/bin/python spinazoo/spinazoo.pygame
