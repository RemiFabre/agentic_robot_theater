# Microduck meets Reachy Mini — working notes

Started 2026-09-02. Rémi's brief (voice): a short film. Reachy Mini is asleep in its egg-like
sleeping pose. Microduck is curious and dynamic: walks around it, looks at it, pecks it.
Reachy Mini wakes up; Microduck screams, falls over, stands back up; then the two talk, the duck
in duck language, Reachy Mini in English. First in simulation with scripted motions, then on the
real Microduck. No retraining unless really needed (discuss first).

All paths are absolute. Folder: `/Users/remi/microduck/notes/reachy-encounter/`.

## 1. What already exists that I reuse

- `/Users/remi/microduck/notes/madison/madison.py`: BAM-actuated ducks driven by the shipped
  ONNX policies, and a calibrated table of walk commands (forward 0.3 = 0.10 m/s, strafe
  (0, ±0.5, ...), turns wz 1.5 = 42 deg/s, wz >= 1.7 falls). Head slots: head_yaw slot 5 and
  head_pitch slot 4 track while walking, neck slot 3 on the sitstand net, body z/roll/pitch
  slots 9/10/11 on the stand net.
- `/Users/remi/microduck/notes/comic-video/comic.py`: a beak that opens (visual hinge, no
  physics change), gaze aiming, a smooth one-take camera rig, PIL speech bubbles, an event log
  for sound design, and `mix_animalese.py` (duck-language voice cut from the duck's own sound
  bank).
- The robot runtime (`/Users/remi/microduck/microduck/`): clients never send joint targets.
  They send intents over JSON-RPC on `/run/robotd.sock`: `robot.move {vx, vy, vyaw}`
  (notification, 20-50 Hz, expires after 150 ms), `robot.head {neck_pitch, head_pitch,
  head_yaw, head_roll}` (radians, EMA-smoothed with head_alpha 0.2 per tick), `robot.pose
  {z, roll, pitch}` (stand net body pose), `robot.mouth {open 0..1}` (the 15th servo, not in any
  policy), `robot.sound {tag}` (alarm, greet, inquire, peck, chirp, coo, wheee), `robot.do
  {skill}` (ground_pick, kick_left, kick_right, sit_toggle, roulade), `robot.relax` (motors off,
  it collapses), `robot.init` (ramp to home pose). This IS "the controller, but from a script".

## 2. Consequence for the design (why the sim must be built a certain way)

On the real robot the head can only move through the policy's command block (slots 3..6) and
the twist. So the sim duck must also be driven ONLY through those channels, otherwise what
looks good in sim will not transfer. Exceptions allowed: the mouth (real servo, `robot.mouth`)
and `robot.relax` (the "scared, collapses" gag is literally motors off).

The stand net is what runs whenever the twist is inside the standing deadband (robotd:
`will_stand`), the walk net otherwise. Gains: walk kP 200, stand / kicks / rise kP 160.

## 3. Plan

1. Probe (headless): which head slots track on the stand net and on the walk net, how big the
   amplitudes can be before a fall, what a "peck" looks like through the command block, and
   three "scared fall" options: (a) relax = motors off, (b) an over-fast spin (wz 2.0, known to
   invert), (c) a backward burst. Then three "get up" options: sitstand rise from the heap,
   relax + init ramp, roulade.
2. Film v1 in sim: sleeping Reachy Mini = white body + black dome head + folded antennas
   (kinematic, wakes up by raising the head and popping the antennas). Duck: approach, look,
   circle, peck, scream/fall, get up, dialogue. One-take camera. Bubbles. Sounds: duck bank +
   animalese; Reachy Mini via Kokoro TTS.
3. Real robot: the same segment list replayed through `robot.move` / `robot.head` /
   `robot.mouth` / `robot.sound` over ssh (`ssh microduck`), with Reachy Mini's lines played
   from the Mac.

## 4. Log

### 2026-09-02, first probes (all headless, CPU MuJoCo, BAM servo model, the shipped ONNX policies)

Files: `/Users/remi/microduck/notes/reachy-encounter/duckfilm.py` (shared: a Duck driven by intents
exactly like robotd, the Reachy Mini puppet, camera rig, bubbles), `probe.py` (the tables below),
`encounter.py` (the film).

**Head command slots** (deltas from HOME, radians; the same on the stand net and the walk net):
- head_pitch: tracks 1:1 over the whole ±1.0 rad range. This is the expressive pitch axis.
- head_yaw: tracks 1:1 over ±1.0 rad. Looking sideways works fully.
- neck_pitch: tracks only DOWN, and only about half (command -1.0 gives -0.52). Looking up through
  the neck is impossible with these policies. (So "head thrown back" = head_pitch +1.0.)
- head_roll: tracks ±0.27 (its mechanical range). Enough for a "huh?" head tilt.
- Tracking is slow: the policies follow a head step in about half a second. Pulses shorter than
  0.3 s barely move anything.

**Body pose slots** (stand net): z does nothing visible; roll ±0.3 makes the duck FALL (never use);
pitch ±0.4 = a lean of 20 to 35 degrees with a crouch (trunk drops 5 cm). Pitch is the "bow" axis.

**Peck**: a head-only dip moves the beak by millimetres (the neck is slow and weak). The peck that
works is a whole-body bow: body pitch +0.3 and head_pitch -0.6 for 0.35 s: beak dips 9 cm and
reaches 13 to 17 cm forward. IMPORTANT: the duck must not be looking down (neck command) during
the bow, otherwise its head is already forward and the bow trips the runtime's fall detector
(limp_fall: tilted past 26 degrees AND the 300 ms extrapolation of gravity heading past 60 degrees).
That detector is on by default on the real robot (`[safety] limp_fall`, robotd.toml). A fast bow is
close to its threshold: hardware risk noted, `limp_fall = false` in robotd.toml is the fallback.

**Scared fall**: the walk policy is too robust to fall on command (wz 2.3 spins, backward bursts at
-0.8 m/s: no fall). Motors off (`robot.relax`) collapses the duck face-first in 0.4 s. That is the gag.

**Getting up**: the runtime's own limp-fall ramp (limp 50, then a 0.6 s ramp to HOME at 160) does
NOT get a face-down duck up (it just cycles). The sit-stand network with the all-zero "rise" command
DOES: from the collapsed heap it stood up in every trial (4 of 4 fall variants). On the real robot
that is `robot.do sit_toggle` (the rise half). Never tested on hardware from a face-down heap.

**Reachy Mini puppet**: white cylinder (r 8 cm, 15 cm) + rounded shoulder, a skull ellipsoid with a
black face plate and two eyes, a neck column, two antennas. Asleep: head sunk and pitched 30 deg
forward, antennas hanging down the back. Awake: head up 6 cm, antennas up, head yaws to the duck.
It is a free body of 1.5 kg so pecks rock it. Still: `still_set.png`.

### 2026-09-02, film v1 to v3 (sim)

- v1: the camera lost both characters. Cause: Reachy Mini drifted away at 0.14 m/s from t=0. Writing
  the puppet's head joint positions directly every physics step pumped momentum into its free body.
  Fix: the head joints are now stiff springs whose rest position the film moves (`qpos_spring`), so
  the puppet lives inside the physics.
- v2: Reachy's head turned the wrong way / barely. Cause: MjSpec compiles angles in DEGREES by
  default, so my joint ranges of ±2.6 "rad" became ±2.6 degrees. Fix: `spec.compiler.degree = False`.
- v3 (`/Users/remi/microduck/notes/reachy-encounter/encounter_v3.mp4`, 58 s, 540p, with sound):
  the whole story plays: approach with the head on the egg, "?", clockwise circle on the camera side,
  three pecks (whole-body bows landing on Reachy's shoulder), wake-up chime + antennas + "Oh. Hello.",
  alarm scream + backward burst + motors off (collapse), sit-stand rise, head shake, a wary step back,
  the dialogue (animalese quacks vs Kokoro `bf_emma`), a right kick to show off the legs, "Wheee".
  Sound events are in `v3_540.events.json` (times of every bank sound and line: the same list can
  drive the real robot's speaker through `robot.sound`).

Open points for the next passes: a curious head-bob while walking, a longer retreat before the
collapse (it still falls against Reachy), 720p render, and the real-robot replay tool.

### 2026-09-02, v4 (720p) and the real-robot side

- v4 = `/Users/remi/microduck/notes/reachy-encounter/encounter.mp4` (58 s, 1280x720, sound). Added a
  curious head-bob while walking (head_pitch, the walk net tracks it) and a longer backward burst
  before the collapse, so the duck now falls at a distance from Reachy instead of against it.
- The real robot (192.168.10.139, `ssh microduck`) is OFFLINE right now (ssh times out), so the
  hardware step is prepared, not tested: `duck_rpc.py` talks JSON-RPC to robotd over
  `ssh microduck socat - UNIX-CONNECT:/run/robotd.sock` (newline-delimited, hello api_version 16),
  resends the continuous intents at 25 Hz (they expire after 150 ms), and `play` replays the scene
  open loop with the durations measured in the sim (the robot has no localisation; a ToF-based
  "stop at 25 cm" is the natural upgrade). `--dry` prints the wire messages; `fake` runs a local
  stand-in daemon for a plumbing test.
- Hardware unknowns to check with Rémi next to the robot: (1) `robot.do sit_toggle` from a collapsed
  face-down duck (works in sim, never tried for real); (2) whether the fast bow trips `limp_fall`
  (set `limp_fall = false` in /etc/robot/robotd.toml for the shoot if it does); (3) `robot.init`
  after `robot.relax` ramps to HOME at gain 160 in 0.6 s: from a heap this may be a rough motion.

### 2026-09-02 evening, change of plan: Rémi pilots, the pad gets expression buttons

Rémi's point: the walk is not reproducible enough for an open-loop replay to end up at the right
spot next to Reachy Mini. So the real shoot is piloted with the gamepad, and the pad gains two
expression buttons. Implemented in the runtime clone, local branch `pad-expressions` of
`/Users/remi/microduck/microduck` (never pushed; commit is Rémi's):

- `padd/src/expressions.rs` (new): timed head-intent sequences, pure functions of time.
  LB = curious (tilt right 0.7 s, tilt left 0.7 s, back, with a small neck dip; about 2.1 s).
  RB = peck (the head goes forward twice: 0.45 s forward, 0.4 s back, twice; about 1.7 s).
  The kicks moved to DPad-Left / DPad-Right. The triggers keep the mouth + chirp + wheee.
- `padd/src/main.rs`: bumper edges start an expression; while it plays, the head intent is the
  expression's (sent every tick in drive mode; it overrides the sticks in head mode); one zero
  head is sent when it ends. Body-pose and sticks untouched. Docs table updated in
  `docs/robot/cheatsheet.md`. `cargo test -p padd` = 3 new tests pass, clippy clean.
- A finding that matters for the peck: on the shipped policies **head_pitch negative = beak UP**
  (the pose-gallery note "+ = look up" is the opposite of what the policy does), and the neck is
  short: the whole "head forward" travel is about 3 cm. The peck that reads as a forward jab is
  neck −1.5 (tracks to −0.85) with head_pitch −0.6 to keep the beak level, chosen from an 8-variant
  comparison (`peck_variants.png`, `peck_variants2.png`). A body lean was rejected by Rémi as weird.
- Sim preview of both buttons with exactly the same numbers: `expressions_preview.mp4`
  (`expressions_preview.py` ports `head_at` line by line).

To put it on the robot: `scripts/dev-push.sh` from the clone (needs the team dev key at
`~/.duck-keys/team.dev.key` and `cargo-zigbuild` + `zig`, or `--docker`), then `padd` restarts
with the new mapping. Without the key, the manual path is `cargo zigbuild --target
aarch64-unknown-linux-gnu -p padd --release`, scp the binary and restart `padd.service`.

### 2026-09-02 late: Select = soft release (`robot.soften`), shipping path

Rémi's decisions: the real shoot is piloted; Select PRESS = immediate soft release (gain to the
daemon's limp value 50 at once, then to 0 over 1 s, then torque off), Select held 3 s = power
off as before; Start unchanged (one press = torque on, 2 s ramp home at gain 200, policy drives).
Implemented and committed locally on branch `pad-expressions` of `/Users/remi/microduck/microduck`
(never pushed): new method `robot.soften` in duck-ipc-proto (+ btd refuses it over Bluetooth like
relax), robotd `Softening` state (joints commanded where they were, gain 50→0 in steps of 5 over
1 s, then torque off; the policy is not driving meanwhile; a limp-fall in flight is abandoned),
`robotctl robot soften`, padd Select press → soften, SHUTDOWN_HOLD 3 s. Tests: 4 new, all crates
green. arm64 binaries built in Docker: `target/docker/aarch64-unknown-linux-gnu/release/`.
Ship script (no signing key on this Mac): `/Users/remi/microduck/notes/reachy-encounter/ship-to-duck.sh`.
The robot: remi_duck, 0.10.0 rev 590b986 (= the branch base), ssh microduck@192.168.1.29, dev
board (`allow_dev_keys = true`, team.dev.pub trusted) — pushing the branch to GitHub would make
CI build+sign it and `duckctl update apply --ref pad-expressions` would install it properly.

### 2026-09-02 14:03 shipped to remi_duck (binary swap)

Installed robotd / padd / robotctl / btd from branch `pad-expressions` into
`/opt/robot/daemon/releases/0.10.0/bin/` with `.orig` backups beside them. Restore = 
`/Users/remi/microduck/notes/reachy-encounter/unship-from-duck.sh` (moves the .orig back, restarts).
After the swap: robotd healthy at 49.9 Hz, padd log shows build `590b986-local` and the new mapping.
Nothing else on the board was touched; the OS, updater and config are as before, so this cannot
brick the robot: worst case a daemon fails to start and the restore script (or `mv *.orig` by hand
on the robot) puts the release binaries back.

### 2026-09-02 14:20: robot.recover + two-press Start, shipped

- Rémi's report: a servo in overload (a common thing in some poses) latches torque off and only a
  battery pull recovered it. Implemented `robot.recover`: read every servo's hardware_error_status,
  reboot the ones in error (or silent), torque off everywhere, forget the gain cache (a rebooted
  XL330 comes back at EEPROM gains), back to limp; Start brings it up. Pad: short DPad-Up press
  and release (the 3 s hold still switches walk/roller). Bench: `sudo robotctl robot recover`.
  The journal names the servos and the error words (overload / overheating / electrical shock /
  input voltage / encoder / no answer).
- Rémi's second report: the first Start on a booted duck held in the air ran the gait straight out
  of the home ramp. padd now believes the robot is down until it sent an init: Start 1 =
  `robot.init` (torque on, 2 s ramp home, hold), Start 2 = policy, further presses toggle. The
  belief resets on the soften / recover / shutdown padd sent and whenever padd restarts (a robotd
  restart takes padd down too). Worst case if the belief is wrong: the old one-press behaviour or
  one extra re-home ramp, never a fall.
- The earlier "robot vanished" at 14:04 was a `robot.shutdown` (Select held) in the previous boot's
  journal, not the soften call. In the current boot the soft release ran as designed (gain 50,
  ramp, torque off after 1.0 s, Start brought it back).
- Commits (local branch `pad-expressions`): c8f52ff expressions + soften, 1ef7be2 recover,
  5930255 two-press Start. Shipped by binary swap at 14:20; restore = unship-from-duck.sh.

### 2026-09-02 evening: PR #203 and the branch rebuilt on top of it

- Draft PR https://github.com/pollen-robotics/microduck/pull/203 (branch `reboot-motors`, worktree
  `/Users/remi/microduck/microduck-wt-reboot`, off main 2c61dcc): `robot.rebootMotors {ids}`,
  `robotctl robot reboot-motors [ID ...]` (space separated, none = all), pad DPad-Right = reboot
  every servo. Minimal by request (no hardware-error read; that is the version that was on the robot
  before). DPad-Up was my first choice and wrong: its 3 s hold already switches walk/roller.
- `pad-expressions` (main clone) was REBASED onto `reboot-motors`: now = main + PR + e0f4b54
  (expressions + soften) + db2c70e (two-press Start). My `robot.recover` commit was dropped in
  favour of the PR's mechanism, so merging main later should be trivial. Consequence on this pad
  mapping: DPad-Right = reboot servos, DPad-Left = kick left, the RIGHT KICK HAS NO BUTTON (bumpers
  are the expressions). The pre-rebase state is tagged `pad-expressions-before-rebase`.
- Robot runs the rebased branch (binary swap, `.orig` backups still the release originals).

### 2026-09-02 night: voices to choose from, and a startled button

- Voice: the bank is a seeded synth (`sounds` crate), seed = sha256 of the SoC serial; this robot's
  seed is 4145077059. Ten banks rendered on the Mac (`cargo run -p sounds -- render-all --seed N DIR`)
  into `notes/reachy-encounter/voices/`, audition page `voices.html` (opens locally, buttons per
  seed and sound). To install a chosen seed on the robot:
  `sudo /opt/robot/daemon/current/bin/sounds ensure-bank --force --seed SEED && sudo systemctl restart robotd`.
  Caveat: a release install runs `ensure-bank` again from the serial and would overwrite the choice
  (the marker records the seed); rerun the command after updates.
- Startled (R3 = right stick click): head_pitch −1.0 (beak up) in 0.15 s, backward walk
  (−0.35, 0, 0.22) from 0.3 to 1.5 s, head settles by 2.0 s. Expressions can now override the
  twist. Sim: backs up 8 cm, never fell (3/3). Scream stays on RT. Installed on the robot.
