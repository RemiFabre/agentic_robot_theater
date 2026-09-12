#!/bin/zsh
# Two simulated Reachy Minis (MuJoCo) for the couple_fight scene, from the main SDK checkout's venv.
#   port 8000 = loretta, port 8001 = husband.
# Each daemon is one mjpython process with its own MuJoCo window; logs go to /tmp/couple_fight_sim_<name>.log.
#
#   robot/run_sim_duo.sh              # start both (no media: the scene's audio is played by afplay)
#   MEDIA=1 robot/run_sim_duo.sh      # start both WITH the daemon media pipeline (needed for skit_duo.py --wobbler daemon)
#   robot/run_sim_duo.sh stop         # stop both
#   robot/run_sim_duo.sh status       # ask both daemons
#
# Why --no-media by default: both daemons with media bind the same fixed resources (udp 5005 for the sim camera,
# /tmp/reachymini_camera_socket). It boots, but only one of the two SDK-side audio paths is trustworthy.
# The offsets player does not need the daemon's audio at all.
set -u
SDK="${SDK:-/Users/remi/reachy_mini_apps/reachy_mini}"
PY="$SDK/.venv/bin/mjpython"
MEDIA="${MEDIA:-0}"
LOG_L=/tmp/couple_fight_sim_loretta.log
LOG_H=/tmp/couple_fight_sim_husband.log
PID_L=/tmp/couple_fight_sim_loretta.pid
PID_H=/tmp/couple_fight_sim_husband.pid

status_of() { curl -s -m 2 "localhost:$1/api/daemon/status"; }

case "${1:-start}" in
  stop)
    for f in $PID_L $PID_H; do
      [ -f "$f" ] && { kill "$(cat $f)" 2>/dev/null && echo "stopped $(cat $f)"; rm -f "$f"; }
    done
    pkill -f "reachy_mini.daemon.app.main --sim" 2>/dev/null
    exit 0 ;;
  status)
    echo "loretta 8000: $(status_of 8000)"; echo "husband 8001: $(status_of 8001)"; exit 0 ;;
esac

[ -x "$PY" ] || { echo "!!! $PY not found (mjpython in the SDK venv)"; exit 1; }
# mjpython (MuJoCo's .app launcher) dlopens libpython3.12.dylib by @rpath; uv's Python keeps it in
# <python home>/../lib, which is not on that rpath. Point dyld at it (no change to the venv).
PYHOME="$(sed -n 's/^home = //p' "$SDK/.venv/pyvenv.cfg")"
export DYLD_LIBRARY_PATH="$(dirname "$PYHOME")/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
for p in 8000 8001; do
  if status_of $p | grep -q state; then echo "!!! something already answers on port $p (run_sim_duo.sh stop first)"; exit 1; fi
done

EXTRA=()
[ "$MEDIA" = "1" ] || EXTRA=(--no-media)
# One MuJoCo window per daemon. mjpython needs the GUI (no --headless). Datasets are not preloaded (skit_duo loads
# the emotions itself). Two robot names so the two mDNS records do not fight.
start_one() {  # name port log pid
  echo "== starting $1 on port $2 (log $3)"
  # no nohup: it is a SIP-protected binary and macOS strips DYLD_* from its environment
  cd "$SDK" && "$PY" -m reachy_mini.daemon.app.main --sim --robot-name "$1" --fastapi-port "$2" \
      --no-wake-up-on-start "${EXTRA[@]}" > "$3" 2>&1 < /dev/null &
  echo $! > "$4"
  disown
}
start_one loretta 8000 $LOG_L $PID_L
start_one husband 8001 $LOG_H $PID_H

wait_for() {  # port name
  for i in {1..90}; do
    if status_of $1 | grep -q '"state":"running"'; then echo "   $2 ($1) running"; return 0; fi
    sleep 1
  done
  echo "!!! $2 ($1) did not answer in 90 s, see the log"; return 1
}
ok=0
wait_for 8000 loretta || ok=1
wait_for 8001 husband || ok=1
echo "PIDs: loretta $(cat $PID_L), husband $(cat $PID_H)"
echo "stop with: robot/run_sim_duo.sh stop   (or kill $(cat $PID_L) $(cat $PID_H))"
echo "logs: $LOG_L $LOG_H"
exit $ok
