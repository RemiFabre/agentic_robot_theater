#!/bin/zsh
# Episode 3 on the two robots, from the laptop. Checks both robots, syncs the player + the scene to the
# Reachy Mini, then the player sets up (moves, motors on, wake-up, pings the duck) and waits for ENTER:
# the scene starts the moment you press it (START_DELAY=5 to get 5 s to walk to the camera).
# Mid-scene, at `duck_rises`, it waits for ENTER again (stand the duck up with Start, face it to Reachy).
# ESC / q / Ctrl+C aborts (motion + audio stop, the duck gets a stop cue, Reachy sleeps).
#
#   robot/run_episode3.sh                # both robots
#   START_DELAY=5 robot/run_episode3.sh  # 5 s between ENTER and beat 0
#   robot/run_episode3.sh --no-duck      # Reachy only (any skit.py flag passes through)
#
# Before ENTER: duck standing, policy on (Start twice after an install), pad connected (the cue port needs it),
# leash at the pick spot, a mat behind the duck; the duck on Reachy's LEFT at three-quarters, ~60 cm away.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
export ROBOT="${ROBOT:-pollen@reachy-mini.local}"
export DUCK_CUE="${DUCK_CUE:-192.168.1.29:7777}"
DUCK_HOST="${DUCK_CUE%%:*}"; DUCK_PORT="${DUCK_CUE##*:}"
START_DELAY="${START_DELAY:-0}"

echo "== Reachy Mini ($ROBOT)"
ssh -o ConnectTimeout=5 -o BatchMode=yes "$ROBOT" 'curl -s -m 3 localhost:8000/api/daemon/status' | grep -q '"state":"running"' \
  && echo "   daemon running" || { echo "   !!! the Reachy daemon does not answer (is it on? on the Wi-Fi?)"; exit 1; }
echo "== Microduck cue port ($DUCK_CUE)"
if nc -z -G 3 "$DUCK_HOST" "$DUCK_PORT" 2>/dev/null; then echo "   port open (the player pings it next; it answers only with a pad connected)"
else echo "   !!! $DUCK_CUE closed: duck off, or padd without the cue port. (Use --no-duck for Reachy alone.)"; exit 1; fi
echo "== syncing and starting the player (ENTER starts beat 0 after ${START_DELAY}s; ESC aborts)"
exec "$HERE/run_on_robot.sh" "$ROOT/scenes/episode3" --start-delay "$START_DELAY" "$@"
