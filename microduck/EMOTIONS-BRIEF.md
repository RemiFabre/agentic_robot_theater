# Microduck emotions: brief for a fresh agent

Written 2026-09-04 by the previous agent, from Rémi's spoken brief. Read this, then
`/Users/remi/microduck/notes/START-HERE.md`, `/Users/remi/microduck/microduck_rl/AGENTS.md`, and
`/Users/remi/reachy_mini_apps/agentic_robot_theater/microduck/README.md` (the duck side of the
theater: pad mapping, how to ship a build to the robot, voice tools, simulation scripts).

## The goal

Give Microduck body language and emotional expression, so that Rémi can film short scenes
between Reachy Mini and Microduck with a lot of visible emotion. The framing idea: Reachy Mini is
trying to teach Microduck how to show emotions, or the two simply interact and emotions fly.

Reachy Mini already has this: the public dataset of recorded moves
`pollen-robotics/reachy-mini-emotions-library` on Hugging Face (each move has a motion and a
sound; most of the sounds were made with a flute, Reachy Mini's original sound identity). The job
is to port a few of the best ones to Microduck, in Microduck's own identity: **quacks**.

**A lesson from Reachy Mini that must guide everything: sound is paramount.** An excellent motion
with no sound is not readable as an emotion and has no energy. Every Microduck emotion is a
motion plus a quack sound, designed together.

## Scope for now: two emotions

1. **Sadness.** Motion done programmatically (no training): start the sit policy so the duck sits
   down, then slowly lower the head and shake it slowly, while a sad quack plays: a descending,
   low-voice quack. Reference on Reachy Mini: the move called **`sad2`** (Rémi is fairly sure; use
   its sound as the reference to copy).
2. **Anger.** Motion trained with reinforcement learning: the duck stomps its little foot once,
   or better twice: stomp, head goes to the left at the same time; stomp again on the same foot,
   head goes to the right. Plus an angry quack. Reference on Reachy Mini: name not confirmed yet
   (look at the dataset for the angry/furious move and ask Rémi to confirm).

Later, if these two work: excited (moving left to right, happy quacks) and scared (looking up,
shaking the head, maybe lowering the body a little; probably programmatic, RL if needed).

## Two strategies for the sound, both to be explored (not one or the other)

- **A. Port the Reachy Mini sound.** Take the sound attached to the reference move (`sad2`, and
  the anger one) and recreate it with quacks: same contour, rhythm, energy and length, but made of
  quack material, so the identity stays Microduck's while the emotion reads the same.
- **B. Design it programmatically.** Use music theory: notes played as quacks, or one quack whose
  pitch glides continuously along a contour (descending minor line for sadness, short hard
  repeated hits for anger, and so on).

Anyone may propose a third strategy. Rémi expects several strategies to be tried in parallel,
so spawn subagents when there are independent angles. Deliver candidates as short wav files with
names, several per emotion, so Rémi can listen and choose (he judges by ear; a page or folder of
named candidates works well, as in `notes/reachy-encounter/voices.html`).

Raw material: the robot's quack generator is the Rust crate `/Users/remi/microduck/microduck/sounds`
(seeded synth, tags chirp / greet / inquire / alarm / peck / coo / wheee, `cargo run -p sounds --
render-all --seed N DIR`; this robot's seed is 4145077059). Pre-rendered banks live in
`/Users/remi/microduck/notes/reachy-encounter/voices/` and
`/Users/remi/microduck/notes/comic-video/sounds/`. The comic film has a grain-based "animalese"
quack synthesis in `/Users/remi/microduck/notes/comic-video/mix_animalese.py` worth reusing.
On the robot, sounds are played through `robot.sound {tag}` from the bank in
`/var/lib/robot/sounds`; a new emotion sound will need either a new tag in the `sounds` crate or a
way to play an arbitrary wav (check `robotd/src/sound.rs`; `aplay` on the robot works for tests).

## Two strategies for the motion

- **Programmatic** (sadness, probably scared): drive the shipped policies through the command
  block. Available: the sit policy (`robot.do sit_toggle`), head deltas through `robot.head`
  (head_pitch ±1 rad tracks one to one, **negative = beak up**; head_yaw ±1; neck only down,
  ask −1.5 to get −0.85; roll ±0.27; the policies follow a head step in ~0.5 s), body pose
  through `robot.pose` (pitch up to ±0.3 is a bow, roll makes it fall). The gamepad "expressions"
  in `padd/src/expressions.rs` (branch `pad-expressions` of `/Users/remi/microduck/microduck`)
  are the pattern: a pure function of time returning head deltas and an optional twist, bound to
  a button, shipped with `notes/reachy-encounter/ship-to-duck.sh`. Check first whether the head
  slots track on the sit-stand policy while sitting (the Madison notes say the neck slot does).
- **Reinforcement learning** (anger stomp): a new environment in `microduck_rl` (mjlab, PPO on
  HF Jobs; `duck-train`, cost ≈ $2 to $8 per run; the recipe is in `START-HERE.md` §"The loop"
  and the flamingo specs in `microduck_rl/docs/superpowers/specs/`). A one-shot skill like the
  kicks or the happy hop: all-zero command, starts from a stable stand, lifts one foot and slams
  it down, head to one side on the first stomp and to the other on the second, ends standing.
  Design the reward table in writing first, smoke test, then train. Rémi's hard veto: physically
  plausible for XL330 servos (no thrashing). Evaluate in the CPU proxy with the training actuator
  model and the actuator delay (`duck-hop` shows the flags) and produce videos.

## Working style Rémi asked for

- Autonomous, but **show results early and often**: pop a video or an audio candidate on his
  screen (`open file`) as soon as something is decent, so a wrong angle is caught early. He has
  lost days to agents polishing a dead end.
- Keep a running notes document he can read (what was tried, what failed, why). Absolute paths
  everywhere. Plain English, define terms, no walls of text.
- Videos of every RL run on the environment it was trained on; report joint speeds and falls.
- Never push to `pollen-robotics/*` unless he asks; local branches and HF repos under `RemiFabre/*`
  are fine. Ask before paid training beyond a smoke test the first time, then run.
- The robot: `remi_duck`, ssh `microduck@192.168.1.29` (home Wi-Fi Livebox-6730; over Bluetooth
  with `duckctl` if the address changes). Other agents may be working on it: check
  `robotctl version` and the padd journal line before swapping binaries, and say what you did.

## First steps

1. Fetch `pollen-robotics/reachy-mini-emotions-library`, list the moves, play `sad2` and the
   candidates for anger; confirm the anger name with Rémi. Extract the sounds as wav.
2. Sound, in parallel: strategy A (port) and strategy B (programmatic) for sadness and anger,
   three to five named candidates each; put them in one folder or page and open it for Rémi.
3. Sadness motion, programmatic, in simulation first (`notes/reachy-encounter/duckfilm.py` has
   the duck driven exactly like the robot), then on the robot as a pad button.
4. Anger motion: write the environment design (reward table, spawn, termination, success
   metric), smoke test, train, video, iterate. Meanwhile, check whether a programmatic stomp
   through the command block is at all possible, as a fallback.
5. Combine: each emotion = motion + sound on one button, filmed with Reachy Mini's
   `agentic_robot_theater` pipeline.
