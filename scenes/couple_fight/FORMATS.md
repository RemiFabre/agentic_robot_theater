# Shared formats for the couple_fight tracks (agreed 2026-09-12)

## scene.json (two Reachy Minis)
List of beats, in order. New key: `speaker` = "loretta" | "husband". Everything else as in the main README:
`id`, `text` (spoken line, rendered to `audio/<id>.wav` by voice/render_lines.py with the speaker's voice),
`emotions` (chain of recorded moves for the speaker), `hold`, `gap`, `say_at`, `cap`, `tail`, `pre`.
Optional `emotion` (string, e.g. "angry", "sassy", "sad", "pleading", "neutral") and `energy` (float, 1.0 default):
the emotional colouring passed to wobblers that accept it (v6+). Others ignore it.
The non-speaking robot keeps listening: it may carry `listener_emotions` (chain of moves for the other robot).

Example beat:
{"id": "late", "speaker": "loretta", "text": "[cold] You're home late again.", "emotion": "angry", "energy": 0.8,
 "emotions": ["reprimand1"], "listener_emotions": ["uncertain1"], "gap": 0.3}

## Head offsets from the offline wobbler harness
Path: `scenes/couple_fight/audio/offsets/<beat_id>.<version>.json` (version = v0, v4, v5, v6...).
One JSON object, arrays all of length T, hop = `hop_ms`:
{"version": "v5", "emotion": "angry", "energy": 1.0, "hop_ms": 20, "sample_rate": 16000,
 "t": [0.0, 0.02, ...],            # seconds from the start of the wav
 "pitch": [...], "yaw": [...], "roll": [...],   # radians, head offsets (same sign convention as the live wobbler)
 "x": [...], "y": [...], "z": [...]}            # millimetres
Producer: `python examples/wobbler_lab/offsets.py --wav <wav> --version v6 --emotion angry --energy 1.2 --out <json>`
in the worktree ~/reachy_mini_apps/reachy_mini_wobbler (batch: `--wav-dir <dir> --out-dir <dir>` for all versions).
Consumers: robot/skit_duo.py (live sim, two daemons) and robot/render_duo.py (offscreen MuJoCo video).
