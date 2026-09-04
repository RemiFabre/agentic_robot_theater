# Microduck side of the theater

Everything needed to make the duck act in a scene: what the gamepad does with the film build,
how to put that build on the robot and take it off again, the voice, and the simulation used
to prototype a scene before filming. Written 2026-09-04 from the "Microduck meets Reachy Mini"
work (the day-by-day log is `LOG.md`).

## The robot

- Name `remi_duck`, ssh `microduck@192.168.1.29` at home (user `microduck`). It advertises over
  Bluetooth too: `duckctl scan`, `duckctl --name remi_duck wifi connect "<ssid>" --psk "<pw>"`,
  `duckctl --name remi_duck ip`. The Bluetooth advertisement is slow, so a scan can miss it;
  retry. `duckctl` is built from the runtime repo (`cargo install --path duckctl`).
- The runtime is the Rust workspace in `/Users/remi/microduck/microduck` (clone of
  `pollen-robotics/microduck`). Daemons on the robot: `robotd` (50 Hz control loop, policies,
  gains, torque), `padd` (gamepad to intents), `btd` (Bluetooth), `robotctl` (CLI on the robot).
- Useful on the robot: `robotctl health`, `robotctl monitor`, `journalctl -u robotd -f`,
  `sudo robotctl robot init | relax | soften | reboot-motors [ids]`, `robotctl quack`.

## Branches and pull requests

- **`pad-expressions`** (local branch of `/Users/remi/microduck/microduck`, not pushed): the film
  build = upstream `main` + PR #203 + our commits (expressions, soft release, two-press Start,
  startled). This is what to install for filming.
- Upstream draft PRs, one feature each, minimal:
  - #203 `reboot-motors`: `robot.rebootMotors`, `robotctl robot reboot-motors`, D-pad right.
  - #210 `start-twice`: first Start stands up, second Start drives.
  - #212 `select-relax`: Select press = torque off (`robot.relax`).
  Worktrees for them: `/Users/remi/microduck/microduck-wt-{reboot,start,relax}`.
- Installing a build on the robot without the signed updater (no dev key on the Mac):
  `tools/ship-to-duck.sh` builds robotd/padd/robotctl/btd for arm64 in Docker from whatever
  branch the clone has checked out, copies them over ssh, swaps them in
  `/opt/robot/daemon/releases/<v>/bin/` with `.orig` backups, restarts. `tools/unship-from-duck.sh`
  puts the originals back. The updater still thinks the release is stock; a `robotctl update apply`
  overwrites the swap, which is fine.

## Gamepad, film build (`pad-expressions`)

| control | does |
|---|---|
| Start, first press | torque on, 2 s ramp to the home pose, hold (`robot.init`) |
| Start, again | walking policy on; further presses toggle it |
| left stick / right stick | walk, strafe / turn (head mode Y: pose the head; body mode B: lean, crouch) |
| LB | curious: head tilt right, tilt left, small neck dip (2 s) |
| RB | peck: head forward twice, beak level (1.7 s) |
| R3 (right stick click) | startled: head up at once, a step back, head settles (2 s). Scream with RT |
| RT | mouth + chirp; LT: mouth + "wheee" while held |
| Select | soft release: gain 50 at once, to 0 over 1 s, torque off (`robot.soften`). The duck folds |
| Select held 3 s | power off |
| DPad-Right | reboot the servos (after an overload trip), torque off, then Start |
| DPad-Left | left kick (the right kick has no button on this build) |
| DPad-Down | sit / stand toggle; A ground pick; X roulade; DPad-Up held 3 s walk/roller |

Adding an expression: `expressions.rs` (copied here for reference; the real one is
`padd/src/expressions.rs` on the branch). An expression is a pure function of time: `head_at`
returns the four head deltas, `twist_at` an optional walking command. Add a `Kind`, bind a
button in `padd/src/main.rs`, `cargo test -p padd`, then `ship-to-duck.sh`. Numbers that work on
the shipped policies (measured in simulation, confirmed on the robot):

- head_pitch tracks ±1 rad one to one; **negative = beak up**. head_yaw tracks ±1 rad.
- neck_pitch only goes down, about half the command (ask −1.5 to get −0.85). Looking up is
  head_pitch, not the neck. head_roll ±0.27 (its range).
- The policies follow a head step in about 0.5 s; pulses shorter than 0.3 s barely move.
- Body pose pitch up to ±0.3 is a bow; body roll makes the duck fall. Backward walk:
  (−0.35, 0, 0.22) is the calmest command. Turns: wz 1.5 (44°/s); ≥ 1.7 falls.
- The whole "head forward" travel of the neck is about 3 cm; a bigger peck needs a body bow.

## Voice

Every sound the duck makes is a seeded synth (`sounds` crate). Tags the pad and the film use:
chirp, greet, inquire, alarm (the scream), peck, coo, wheee. The seed comes from the chip
serial (this robot: 4145077059). To audition others: `cargo run -p sounds -- render-all --seed N
DIR` on the Mac (see `LOG.md` for the ten rendered and the audition page); to install one:

```bash
ssh microduck@192.168.1.29 'sudo /opt/robot/daemon/current/bin/sounds ensure-bank --force --seed SEED && sudo systemctl restart robotd'
```

A release install regenerates the bank from the serial, so rerun after updates.

## Simulation, to prototype a scene before filming

`sim/` runs in `/Users/remi/microduck/.venv-mjlab` (MuJoCo, the shipped ONNX policies, the BAM
servo model). The duck is driven only through what the real robot accepts from a client (twist,
head deltas, body pose, mouth, sounds, relax), so what works there transfers.

- `sim/duckfilm.py`: the duck, a kinematic Reachy Mini puppet, camera rig, bubbles.
- `sim/encounter.py`: the full "meets Reachy" film (approach, circle, pecks, wake-up, scream,
  collapse, get up, dialogue) with sound mixed in: `python sim/encounter.py` writes an mp4.
- `sim/probe.py`: the measurements above (head tracking, pecks, falls, getting up).
- `sim/expressions_preview.py`: renders LB / RB as the pad plays them.
- `tools/duck_rpc.py`: drive the real robot from a script over ssh (JSON-RPC to `robotd`).
  Open-loop replay was abandoned for filming: the walk is not repeatable enough to land next
  to Reachy, so scenes are piloted with the pad and the expressions are buttons.

Scared fall on the real robot = Select (soft release); getting up = Start. In the simulation the
sit-stand policy stood the duck up from a face-down heap every time; on hardware use Start.
