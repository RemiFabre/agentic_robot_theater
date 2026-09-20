#!/bin/zsh
# The filming player for the two-Reachy couple fight, from the Mac. Every flag passes through to robot/skit_film.py.
#   robot/run_film.sh                                   # full motion, wobbler v6
#   robot/run_film.sh --motion none                     # no head motion
#   robot/run_film.sh --motion wobbler --wobbler main   # the daemon's own wobbler (main), no emotions
# Loretta = the wireless (reachy-mini.local:8000), the husband = the Lite (daemon on this Mac, localhost:8000).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PY="${PY:-/Users/remi/reachy_mini_apps/reachy_mini/.venv/bin/python}"
cd "$ROOT"
exec "$PY" robot/skit_film.py "${SCENE:-scenes/couple_fight}" "$@"
