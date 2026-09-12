# Two simulated Reachy Minis on the Mac (couple_fight)

Written 2026-09-12 by the sim agent. Everything below was run on this Mac (macOS 15.6, MuJoCo 3.3, SDK venv
`~/reachy_mini_apps/reachy_mini/.venv`). Nothing in the SDK checkout was edited; the GStreamer plugin
`libgstpython.dylib` was NOT renamed.

## What runs

```bash
cd ~/reachy_mini_apps/agentic_robot_theater
robot/run_sim_duo.sh                  # two sim daemons: loretta :8000, husband :8001 (logs /tmp/couple_fight_sim_*.log)
robot/run_sim_duo.sh status           # both /api/daemon/status
robot/run_sim_duo.sh stop
SDK=~/reachy_mini_apps/reachy_mini    # (default)
$SDK/.venv/bin/python robot/skit_duo.py scenes/couple_fight --dry-run            # timeline, no robots
$SDK/.venv/bin/python robot/skit_duo.py scenes/couple_fight --wobbler v5         # v0|v4|v5|v6 offsets, none, daemon
$SDK/.venv/bin/python robot/skit_duo.py scenes/couple_fight --wobbler v0 --from-beat 4 --start-delay 3 --no-audio
robot/record_duo.sh v5 [out.mp4] [seconds]   # proof video: plays the scene, records both windows side by side, muxes the lines
```

The player runs with the SDK venv's plain `python` (not mjpython): it is a client of the two daemons.
Ctrl+C aborts and both robots go back to a neutral pose. The whole scene lasts about 66 s (9 beats).

## Launcher facts (run_sim_duo.sh)

- `mjpython -m reachy_mini.daemon.app.main --sim --robot-name <n> --fastapi-port <p> --no-wake-up-on-start --no-media`.
  Two instances coexist: distinct `--fastapi-port`, distinct `--robot-name` (mDNS registers with
  `allow_name_change=True` anyway), no lock file, the API binds 127.0.0.1.
- `mjpython` failed to start at first: `Library not loaded: @rpath/libpython3.12.dylib`. uv's Python keeps the
  dylib in `<python home>/../lib`, outside the rpaths of MuJoCo's app bundle. Fix used (no change to the venv):
  `export DYLD_LIBRARY_PATH=/Users/remi/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/lib`.
  Second trap: `nohup` is a SIP-protected binary and macOS strips `DYLD_*` from its environment, so the
  launcher backgrounds with `&` + `disown` instead of nohup.
- No `libgstpython.dylib` segfault with `--no-media`: the daemon never loads GStreamer then. See the media section
  for the `MEDIA=1` case.
- Default `--no-media`: with media, both daemons bind the same fixed resources (udp 5005 for the sim camera,
  `/tmp/reachymini_camera_socket`), and the scene's audio is played by `afplay` anyway.
- Windows: two "MuJoCo : scene" windows open, but at the same place (362,102, 1280x748), so you only see one.
  Moving them needs assistive access, which the terminal does not have ("osascript is not allowed assistive
  access"), so drag one aside by hand, or grant System Settings > Privacy > Accessibility to the terminal and run:
  `osascript -e 'tell application "System Events" to set position of window 1 of (first process whose unix id is <PID>) to {0, 40}'`.
  The proof recorder works around it (below).

## How the offsets are applied (skit_duo.py)

Per beat, the speaker's `emotions` chain is played by our own 100 Hz loop (like `EmotionRunner._play_turned` in
skit.py): `move.evaluate(t)` gives head pose, antennas, body yaw. While the line plays, the head pose sent to the
daemon is `compose_world_offset(pose, create_head_pose(x_m, y_m, z_m, roll, pitch, yaw, degrees=False))`, the same
two SDK functions the daemon uses in `AbstractBackend.set_target_head_pose` for `set_speech_offsets` (translations
add in world, `R_final = R_off @ R_abs`). Offsets come from `audio/offsets/<id>.<version>.json` (mm -> m), indexed
by `round((now - line_t0) / hop)` with `hop = hop_ms / 1000` read from the file (the real files use 50 ms), one
monotonic clock for everything. `line_t0` = the `afplay` Popen time + 80 ms (`--audio-latency`).
After the chain ends the last pose is held and the offsets keep being composed on it until the line ends.
The listener plays `listener_emotions` in parallel, not awaited: its chain is dropped (0.3 s blend) when it must speak.
Measured loop rate: see the end of each player log (`loretta: loop N Hz ...`).

## Files

- `robot/run_sim_duo.sh`, `robot/skit_duo.py`, `robot/fake_offsets.py` (placeholder offsets; the real ones from the
  wobbler harness were already on disk, so no placeholder was used or written), `robot/record_windows.py`,
  `robot/mux_lines.py`, `robot/record_duo.sh`.
- `scenes/couple_fight/sim_v0.mp4`, `sim_v5.mp4` (proof recordings, see below).
