# Microduck emotions (episode 2): what exists and how to make more

Written 2026-09-06. The duck-side emotion work of episode 2 ("Reachy Mini breaks bad news to
Microduck") lives in its own private repo, **https://github.com/RemiFabre/microduck_emotions**
(working copy `/Users/remi/microduck/notes/emotions/`). Read its `README.md` first (decided
emotions, layout, the recipe), then `NOTES.md` (the day's log: every attempt, what failed, why,
Rémi's decisions). This page is the short bridge from the theater repo.

## What is on the duck's gamepad (film build, branch `pad-expressions` of the runtime)

`DPad-Up tap` toggles **emotion mode** (chirp on, low tock off). In emotion mode:

| button | emotion | what it does (from the press) | sound |
|---|---|---|---|
| **A** | sad | standing; beak lifts a little, then head droops to half depth with a slight bow over 2.5 s; two slow silent head shakes; hold; level again at 7.5 s | the robot's coo recipe synthesized, gliding 200 to 140 Hz with the head; silent shakes |
| **B** | devastated | sits at once (the surprise); head droops; three slow "no" shakes starting while the head is still going down, with a sob on each; hold; head level by 8.5 s, stays seated | inquire shock at the sit, silence, three soft sobs |
| **Y** | curious ("what? what?") | standing; head tilt right on the first chirp, left on the second; back to centre by 2.6 s | two of the bank's rising chirps, the second 2 semitones higher |
| X | angry | not shipped (RL stomp still in training, see below) | |

Start and Select keep working in both modes. Sticks are locked during an expression. The wavs are
in `/var/lib/robot/sounds/{sad,devastated,curious}/` (outside the seeded bank: `sounds
ensure-bank --force` deletes them; copies in `microduck_emotions/sounds/robot/`). Code:
`padd/src/expressions.rs` (`Kind::Sad`, `Kind::Devastated`, `Kind::CuriousQuacks`), the
`SoundTag` enum in `duck-ipc-proto`, `robotd/src/intents.rs`. The whole branch is snapshotted as
`microduck_emotions/runtime-pad-expressions.patch`. Install with
`microduck_emotions/install-on-duck.sh` (sudo password needed on the robot).

## The recipe that worked (details and scripts in the emotions repo)

1. **Motion first, in simulation**, as a pure function of time on the shipped walking / sit
   policies (head deltas, body pitch, a skill trigger, mouth). `motion/sadness/sadness.py` and
   `v2.py`, `motion/curious/curious.py` render candidates with contact sheets and a page. Rémi
   picks. Beats go in a spec JSON.
2. **Sound designed on the beats**: `sounds/make_synced*.py`, `sounds/make_curious.py`, using
   `quack.py` (an exact Python port of the robot's Rust voice; `Personality(4145077059)` is this
   duck). Smooth glides, soft attacks, no brutal transitions for sad emotions. Shock from the
   existing bank at a surprise beat, silence where nothing happens, one slide per head movement.
3. **Beak follows the sound** (RMS envelope at 50 Hz to mouth 0..1, 0.15 s lag). `combine.py`
   muxes wav into mp4; every round has a page under `combined/`.
4. **Ship**: expression + sound tag in the runtime, `install-on-duck.sh`, Rémi tests with the
   pad. Never move the robot from a script: Rémi triggers every motion.

## Lessons from the real robot (the simulation does not show these)

- Anything that moves the head's mass forward (neck forward/down, deep head pitch) makes the
  walking policy step forward. Full-depth sad and the curious head-forward both did it. Keep
  |neck| <= 0.75, avoid forward head poses, use roll and yaw for expressiveness.
- Time-stretching bank sounds granularly reads as robotic; synthesize the recipe instead.
- Four head swings are too many; three (devastated) or two (sad) read better. Sad is slow and
  quiet (peak -9 dBFS vs -3 for the bank).
- Speaker level: `sudo amixer -c aic3104 cset name='PCM Playback Volume' 115,115` (-6 dB,
  persisted in `/usr/local/bin/aic3104-init.sh`).

## Angry (RL), not finished

A trained three-tap stomp (`Mjlab-Stomp*-Flat-MicroDuck`, local branch `emotions-stomp` of
`microduck_rl`, patch and spec in `microduck_emotions/rl/`, runs logged in
`microduck_emotions/motion/anger-rl/REPORT.md`). r1 learned to just stand; r2 stomped with huge
amplitude (rejected: "we want a very short, very low amplitude foot movement"); r3 (small-stomp
redesign) was in progress when the session ended. Rémi's veto: physically plausible for XL330
servos, no thrashing.
