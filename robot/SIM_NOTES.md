# Two simulated Reachy Minis on the Mac (couple_fight)

Written 2026-09-12 by the sim agent. Everything below was run on this Mac (macOS 15.6, MuJoCo 3.3, SDK venv
`~/reachy_mini_apps/reachy_mini/.venv`). Nothing in the SDK checkout or its venv was edited; the GStreamer plugin
`libgstpython.dylib` was NOT renamed (not needed, see the media section).

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
- `scenes/couple_fight/sim_v0.mp4`, `sim_v5.mp4`, `sim_v6.mp4` (proof recordings, about 1.1 MB each; `*.mp4` is
  gitignored so they stay on disk only).

## Daemon-side wobbler in sim (MEDIA=1), what was checked

- `MEDIA=1 robot/run_sim_duo.sh` starts both daemons with the GStreamer media server. They booted and stayed up,
  no `libgstpython.dylib` segfault in the mjpython process on this Mac (the plugin is still in place). Both bind
  udp 5005 (udpsrc has reuse on) and the same camera socket; harmless for the scene, just do not trust the sim
  cameras.
- Is there an audio pipeline in sim on macOS: yes. The daemon opens `osxaudiosrc` / `osxaudiosink` on the default
  devices (log: "No Reachy Mini Audio Sink card found ... using default audio sink"), so `play_sound` goes to the
  Mac speakers. The SDK's `media_backend="local"` (what `--wobbler daemon` uses) does the same on the client side and
  runs the v0 speech tapper there, sending `SetSpeechOffsetsCmd` to the daemon over the WebSocket. It only works
  when the daemon reports `no_media: false`, hence MEDIA=1.
- `skit_duo.py --wobbler daemon` ran for two beats without errors on the MEDIA=1 daemons (log
  `/tmp/couple_fight_play_daemon.log`). UNVERIFIED: whether the head visibly wobbled and whether the sound came out
  of the speakers (no recording was made, nobody was listening). To check: `MEDIA=1 robot/run_sim_duo.sh` (after a
  stop), then `robot/record_duo.sh daemon` and look at the head during the lines. The v0 offsets recording shows what
  the same tapper produces offline.
- The offsets player (`--wobbler v0|v4|v5|v6`) also works against MEDIA=1 daemons: it connects with `no_media`,
  which releases the daemon's media while it runs and re-acquires it at exit (full scene run, log
  `/tmp/couple_fight_play_v5_media.log`).

## Proof recordings

`robot/record_duo.sh <ver>`: starts the player (`--start-delay 1.5`, `--timeline-out`), waits for its "setup done",
records both windows for 24 s (beats late, please, lisa, coworker, hearts) with `record_windows.py`, then
`mux_lines.py` puts the wavs under the video at the exact times the player started them. Real offset files were used
(the wobbler agent's `audio/offsets/*.{v0,v4,v5,v6}.json`, hop 50 ms), no placeholder.
Capture is 9 fps (CGWindowListCreateImage costs ~30 ms per window and the window server serialises it); the mux
re-times the frames so the video plays at real speed. `screencapture -v` and ffmpeg avfoundation were not used:
they capture the screen, where only one of the two windows is visible. Screen Recording permission is granted to the
terminal (screencapture -x worked).
Measured player loop: 96 Hz per robot over a 70 s scene, about 50 late ticks (3 WebSocket commands per tick per robot).

## Left running

The two MEDIA=1 daemons: loretta PID 89081 (port 8000), husband PID 89082 (port 8001), logs
`/tmp/couple_fight_sim_loretta.log` and `/tmp/couple_fight_sim_husband.log`, PID files `/tmp/couple_fight_sim_*.pid`.
Stop: `robot/run_sim_duo.sh stop`. Restart without media (the default): `robot/run_sim_duo.sh`.

## Not done / decisions

- Windows not moved side by side (no assistive access); drag one by hand, they are stacked at the same spot.
- Stop keys: Ctrl+C in a terminal, or SIGTERM (a background job started with `&` from a script ignores SIGINT, so
  use `kill -TERM`). ENTER-to-start was dropped; use `--start-delay`.
- No `--wobbler daemon` recording. `robot/record_duo.sh daemon` is ready if wanted.
- The robots do not turn toward each other (they are in two separate MuJoCo worlds); a `body_yaw` per beat still
  works if the real shoot needs it (the moves' own body yaw is passed through).
- Scratch venv for the recorder (pyobjc Quartz):
  `/private/tmp/claude-501/-Users-remi-reachy-mini-apps-agentic-robot-theater/5d567a64-3ce8-4a0b-a381-82b6427026ef/scratchpad/qz`
  (recreate anywhere with `uv venv qz && uv pip install --python qz/bin/python pyobjc-framework-Quartz`, `QZ=` env).
