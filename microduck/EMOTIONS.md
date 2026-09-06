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
| **Y** | mmh ("what do you mean?") | a roll tilt +0.22 from 0.45 s, held, back by 1.6 s; 2.0 s | a muffled rising "mmh?" |
| (cue) | curious ("what? what?") | standing; head tilt right on the first chirp, left on the second; back to centre by 2.6 s (Y's former job; LB outside emotion mode is the silent version) | two of the bank's rising chirps, the second 2 semitones higher |
| **X** | angry | standing; beak-up glare, four snaps (yaw +0.7/-0.7/+0.7/centre, a short head jab, a small bow pulse), the beak forced wide 0.3-0.7 s so a held leash drops; 2.6 s | four hard barks on the snaps (or a growl into them: two wavs, random) |
| **LB** | yes | one nod (head_pitch +0.7, 0.25 s down, 0.35 s up); 1.5 s | one quack falling 3 semitones at 0.45 s |
| **L3** | yes, fast | the same nod; 1.5 s | a curt "wak" |
| **R3** | laugh | beak aimed up (-0.7), head wagging, a body dip on every "ha"; 3.0 s | one longer "haaa" then seven short ha's dying out |
| (cue) | mock | `laugh_roll`: beak up, the head rolling +-0.35, body dips; 2.6 s | the staccato run "gnagnagnagna" (after a scolding) |
| **RB** | no | one head shake (yaw +0.55 at 0.35 s, -0.55 at 0.85 s); 1.8 s | "no-ah": two notes, the second a fourth lower (three wavs, random) |
| **RT** | excited | six accelerating head swings +-0.6 with a body bob on each, the beak climbing to -0.7, a bow flourish; 3.4 s | six synth quacks, each higher, shorter, rising more (X1) |
| (cue) | pick | the ground pick with the beak opening on the way down and shutting at the floor (the leash grasp); 3.0 s | none |
| **LT** | play dead | sits on the press (shock), head hard to the side and back; at 1.4 s the three head servos hang free and the legs straighten (`robot.poseJoints`): it rolls flat onto its back, limp head on the side; legs up at 3.6 s; holds the dead pose until Start (the full init); 7.5 s | alarm, silence, a falling glide with a dying wobble (5.0-6.8 s, beak 0.3, the jaw stays powered) |

Start, Select, the sticks, the triggers (mouth + chirp / wheee) and DPad-Right (servo reboot) keep working in both
modes. Sticks are locked during an expression. Episode 3 (2026-09-06) added X / LB / RB / DPad-Down / DPad-Left, all
simulation picks not yet tested on the robot, and a **cue port** (TCP 7777 on `padd`: `{"express":"yes"}`,
`{"skill":"ground_pick"}`, `{"sound":"chirp"}`, `{"move":[vx,vy,wz],"for":1.5}`, `{"stop":true}`) so a scene
script cues the duck as if a button were pressed, plus `{"init":true}` / `{"policy":true}` = the two Start presses;
`robot/duck_cue.py` is the client, `robot/skit.py` plays duck cues from `scene.json` (see the main README, "Two robots
in one script"). The full pad map: `BINDINGS.md` (a copy of the one in the emotions repo). The wavs are
in `/var/lib/robot/sounds/{sad,devastated,curious,yes,yes_fast,no,mmh,laugh,angry,excited,play_dead}/` (outside the seeded bank: `sounds
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
