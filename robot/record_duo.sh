#!/bin/zsh
# Proof recording of the couple_fight scene on the two sim daemons: starts skit_duo.py with the given wobbler,
# waits for its "setup done" line (robots awake, beat 0 about to start), then records the two MuJoCo windows
# side by side for SECONDS (default 24 s: beats late, please, lisa, coworker) with the scene's wavs mixed under.
#
#   robot/record_duo.sh v0 [scenes/couple_fight/sim_v0.mp4] [24]
#
# Needs the daemons up (robot/run_sim_duo.sh), the SDK venv, and the Quartz scratch venv used by record_windows.py
# (QZ=/path/to/qz/bin/python; default: the session scratchpad one).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
VER="${1:-v5}"; OUT="${2:-$ROOT/scenes/couple_fight/sim_$VER.mp4}"; SECONDS_REC="${3:-24}"
PY="${PY:-/Users/remi/reachy_mini_apps/reachy_mini/.venv/bin/python}"
QZ="${QZ:-/private/tmp/claude-501/-Users-remi-reachy-mini-apps-agentic-robot-theater/5d567a64-3ce8-4a0b-a381-82b6427026ef/scratchpad/qz/bin/python}"
LOG="/tmp/couple_fight_play_$VER.log"
[ -x "$QZ" ] || { echo "!!! $QZ missing: uv venv qz && uv pip install --python qz/bin/python pyobjc-framework-Quartz"; exit 1; }

cd "$ROOT"
TL="/tmp/couple_fight_lines_$VER.jsonl"; RAW="${OUT%.mp4}_raw.mp4"
"$PY" robot/skit_duo.py scenes/couple_fight --wobbler "$VER" --start-delay 1.5 --timeline-out "$TL" > "$LOG" 2>&1 &
PLAYER=$!
for i in {1..60}; do grep -q "setup done" "$LOG" && break; sleep 0.5; done
grep -q "setup done" "$LOG" || { echo "!!! player did not get to 'setup done', see $LOG"; kill $PLAYER; exit 1; }
sleep 0.2   # the recorder's first frame lands about a second before beat 0 (start-delay 1.5)
"$QZ" robot/record_windows.py --seconds "$SECONDS_REC" --out "$RAW" --label "wobbler $VER"
wait $PLAYER
echo "player log: $LOG"; grep -E "^\[.*(\[[0-9]\]|loop|done)" "$LOG" | head -20
"$PY" robot/mux_lines.py "$RAW" "$TL" "$OUT" && rm -f "$RAW" "$RAW.json"
ls -la "$OUT"
