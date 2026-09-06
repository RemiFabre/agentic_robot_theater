# agentic_robot_theater

Make short scripted scenes ("skits") with a Reachy Mini: an agent writes the lines, renders the
voice with ElevenLabs, stages emotions + head wobble on the real robot, then cuts, captions and
scores the filmed clip. Everything is scriptable; the human only films and gives taste feedback.

Pipeline (each step is one command):

```
scene.json ──► voice/render_lines.py ──► audio/<line>.wav
                       │
robot/run_on_robot.sh ─┴─► plays on the robot (wakes up, ENTER start / ESC abort)   ← human films
                                        │
video/captions.py  (cut + burned captions, timing from audio alignment + STT word times)
video/gen_music.py + video/mix_music.sh  (ElevenLabs music bed, ducked under the voice)
```

Episode 2 added phone-audio clean-up, a mid-video music switch, landscape gags and a thumbnail
recipe: see [`video/README.md`](video/README.md).

## Setup

- `ELEVENLABS_API_KEY` in the shell env (a Starter plan covers everything: TTS, voice design,
  music, sound effects, speech-to-text). Run Python via `uv run` from this folder.
- Robot: Reachy Mini **wireless**, reachable as `pollen@reachy-mini.local` over ssh (key installed).
  Its apps venv `/venvs/apps_venv` already has `reachy_mini` and the emotions dataset cached.
- Mac tools: `ffmpeg` (the Homebrew build has no subtitles/drawtext filter, so captions are PIL
  PNG overlays), `afplay` to audition.

## Scene format

One file drives everything: `scenes/<name>/scene.json`, a list of beats in order.

```json
{"id": "wake", "text": "[gasps] Oh my! Good afternoon.", "emotions": ["surprised1", "welcoming1"], "tail": 0.3, "gap": 0.5}
{"id": "duck_falls", "emotions": ["inquiring2"], "hold": 3.0, "gap": 0.3}
```

- A beat with `text` is a spoken line: rendered to `audio/<id>.wav`, played with head wobble.
- A beat without `text` is a pause for the other character; `hold` is its minimum length.
- `emotions` is a chain of silent recorded moves played back to back under the beat.
  A beat ends when both audio and the emotion chain are done (never cut an emotion short).
- `pre` / `tail` / `gap` are seconds before the audio, after it, and after the beat.
- `[gasps]`, `[sighs]`, `[pause]` etc. are ElevenLabs v3 audio tags; they are stripped from captions.

## Commands

```bash
# 1. voice: design candidates (plays them), then save one -> voice_id
uv run voice/design_voice.py --desc "fussy prim protocol robot, refined British accent, anxious" \
    --text "Oh my! Good afternoon." --play
uv run voice/design_voice.py --save <generated_voice_id> --name "My Robot"

# 2. render all lines of a scene
uv run voice/render_lines.py scenes/<name> --voice <voice_id>

# 3. play on the robot (syncs files, wakes the robot, then ENTER = start delay + beat 0; ESC aborts -> robot sleeps)
robot/run_on_robot.sh scenes/<name> [--start-delay 5] [--from-beat 2]

# 4. after filming: cut + captions (speaker tag only for the robot's lines)
uv run video/captions.py --video ~/Downloads/clip.mp4 --scene scenes/<name> --start 4 --end 54 \
    --out ~/Videos/<name>
# 5. music bed candidates + mix
uv run video/gen_music.py --out ~/Videos/<name>/music "warm piano, hopeful, under dialogue"
video/mix_music.sh ~/Videos/<name>/skit_captioned.mp4 ~/Videos/<name>/music/x.mp3 out.mp4 [end_s]
```

## Two robots in one script (episode 3)

The same `scene.json` drives both robots. A beat may carry one duck cue next to Reachy's line
and emotions; the two run in parallel and the beat lasts at least as long as the duck needs:

```json
{"id": "duck_angry", "duck": "angry", "emotions": ["surprised2"], "hold": 3.5}
{"id": "duck_pick", "duck_skill": "ground_pick", "hold": 5.0}
{"id": "duck_off", "duck_move": [0.3, 0, 0], "for": 1.5}
{"id": "duck_rises", "wait": "key", "note": "Rémi: Start, turn the duck, then ENTER"}
```

- `duck`: an emotion of the film build (`yes`, `no`, `angry`, `excited`, `play_dead`, `sad`,
  `devastated`, `curious`, `closed_quack`, `peck`, `startled`; see `microduck/EMOTIONS.md`).
  `duck_skill`: `ground_pick`, `sit_toggle`, `kick_left`, `kick_right`, `roulade`. `duck_sound`:
  a bank tag (`chirp`, `inquire`, `alarm`...). `duck_move`: a twist held for `for` seconds.
- `wait: "key"`: the player stops and waits for ENTER before the beat, for the moments Rémi pilots
  the duck by hand (standing it up after play dead, turning it to face Reachy).
- Transport: `robot/duck_cue.py` sends one JSON line per cue to the duck's pad daemon (`padd`,
  film build, TCP port 7777, `DUCK_CUE=host:port`, default `192.168.1.29:7777`) and reads the
  answer (`{"ok": true, "duration": 8.5}`). The cue lands as if the button had been pressed, so
  the gamepad stays alive between cues (only an expression locks the sticks while it plays), and
  a pad must be connected (the pad loop is what applies the cues). If the duck does not answer
  at start-up the scene runs Reachy-only (`--no-duck` forces that, `--dry-duck` prints the cues).
- Preview in simulation before filming: `microduck/sim/episode3_preview.py scenes/episode3`
  renders the whole scene with the sim duck (the same motions and wavs that ship) and the Reachy
  puppet, lines mixed in.

Scene `scenes/episode3` (Reachy the over-analytical friend, the duck and the lake leash) is the
first one written this way; its README has the beat table.

## The other actor: Microduck

Everything for the duck side is in [`microduck/`](microduck/README.md): the gamepad mapping of the
film build (LB curious, RB peck, R3 startled, Select soft release, D-pad right servo reboot), how
to ship that build to the robot and revert it, the branch and PR names, the voice seeds, and the
MuJoCo simulation used to prototype a scene before filming.

## Lessons learned (read these)

- **Robot boots limp** (motor control disabled). `enable_motors()` first, `wake_up()` to start,
  `goto_sleep()` + `disable_motors()` at the end. Default speaker volume was 15/100:
  `curl -X POST localhost:8000/api/volume/set -d '{"volume":100}'` on the robot.
- Robot startup app was cleared so it boots idle (`PUT /api/apps/startup-app {"startup_app": null}`).
- `play_move(move, sound=False)` = silent emotion; `enable_wobbling()` composes wobble on top of
  moves daemon-side, nothing to sync by hand. Emotion durations vary 2-20 s; check
  `RecordedMove.duration` and prefer < 5 s under a spoken line (long ones: curious1 11.8, anxiety1 8.1).
- Voice: `eleven_v3` with tags is expressive but non-deterministic; keep the take you like.
  Speed 1.0 (1.08 felt rushed). Trim silences with ffmpeg `silenceremove`, cap internal gaps ~0.6 s.
- Caption timing: cross-correlate each line WAV with the film audio (band-pass 300-3400 Hz,
  normalised), then STT (`scribe_v1`, word timestamps) on the line WAVs for phrase boundaries.
- Music: ElevenLabs `music.compose` makes 50 s in ~8 s but **one request at a time** (concurrency
  limit). Mix at -12 dB with sidechain ducking; instrumental only. Ask for taste feedback with
  3-10 named candidates rather than one.
- Iterate with the human in the loop: play candidates aloud (`afplay`), run the robot, ask which
  number they liked. Keep emotions/timing edits in the scene JSON, not code.
- Episode 2 lessons (details in `video/README.md`): phone wind = sub-150 Hz rumble, high-pass it; level the
  voice before mixing and keep the mix template; a music switch on the story's turn works; a vertical upload
  is a Short and does not reach the long-form audience; gpt-image-2 repaints when outpainting, keep the
  output that matches, re-frame, then widen with mirrored edges.

## Microduck side

`microduck/README.md` (pad, ship/unship, voice, simulation) and `microduck/EMOTIONS.md` (the duck's
emotions on the gamepad, the recipe to make more, lessons from the real robot; the work itself is in
https://github.com/RemiFabre/microduck_emotions).
