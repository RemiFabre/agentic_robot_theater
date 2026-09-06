# Episode 3: the lake leash (two robots, one script)

Reachy Mini is polite, verbose and over-analytical; Microduck answers in quacks. Landscape filming.
Same voice as the other scenes ("Reachy Mini Protocol", `0m5sA4wKd4nKxBtRAu0n`, `eleven_v3`, speed 1.0),
rendered with `voice/render_lines.py`. The duck's cues go to its pad daemon over the cue port (see the main
README, "Two robots in one script"); every duck emotion here is a simulation pick from
`microduck_emotions` (`combined/episode3/index.html` there), not yet validated on the robot.

## Run it

```bash
# both robots (the duck: film build with the cue port, pad connected, standing, policy on)
DUCK_CUE=192.168.1.29:7777 robot/run_on_robot.sh scenes/episode3 --start-delay 5
# Reachy only / print the duck cues instead of sending them
robot/run_on_robot.sh scenes/episode3 --no-duck
robot/run_on_robot.sh scenes/episode3 --dry-duck
# preview in simulation (writes scenes/episode3/preview_sim.mp4)
/Users/remi/microduck/.venv-mjlab/bin/python microduck/sim/episode3_preview.py scenes/episode3
```

Before ENTER: the duck stands about 60 cm in front of Reachy, facing it, with the leash on the floor at the
tested pick spot; a mat behind the duck for the play-dead fall. The pad stays alive: between cues Rémi can
turn the duck with the stick. At `duck_rises` the player waits for ENTER: Start (sit-stand rise), turn the duck
to face Reachy, then ENTER.

## Beats (v3, tight: a beat lasts the longest of its line (from `say_at`), its duck cue, its Reachy moves (cut at `cap`) and its hold; total 124 s + the pause at `duck_rises`)

| t | beat | length | who / what | camera, notes |
|---|---|---|---|---|
| 0.0 | `duck_excited` | 3.4 s | **Duck: excited** (3.4 s) | Microduck, excited about the lake |
| 3.5 | `lake` | 9.9 s | **Duck: pick** (3.0 s) / Reachy: "[sighs] The lake. [pause] The lake. [weary] You are obsessed with the lake. [pause] But you are not a duck. [firmly] You are a Microduck." (9.0 s, from 0.8 s) under reprimand1 (4.7 s) | Microduck picks the leash up; the line starts as its beak reaches the ground (0.8 s) |
| 13.5 | `duck_mmh_1` | 2.1 s | **Duck: mmh** (2.0 s) / Reachy: inquiring1 (2.1 s) | "What do you mean?" — the beak opens, the leash falls |
| 15.7 | `difference` | 3.9 s | Reachy: "[patiently] The difference... [pause] the difference, is your water resistance." (3.8 s) under understanding1 (3.9 s) |  |
| 19.8 | `duck_defiant` | 2.2 s | **Duck: defiant** (2.2 s) / Reachy: inquiring2 (2.6 s), cut at 2.2 s | defiance: beak up-left, quack; up-right, quack |
| 22.1 | `sun` | 9.0 s | Reachy: "[worried] And the sun. [anxious] Do we even know what the sun does to us? [alarmed] Do we use sun cream? That is also a liquid! [panicking] Will it get into our circuits? [pause] [firmly] We shouldn't go." (8.9 s) under anxiety1 (8.1 s) |  |
| 31.1 | `duck_impatient` | 2.6 s | **Duck: impatient** (2.6 s) / Reachy: surprised2 (3.0 s), cut at 2.6 s | "Come on!" |
| 33.8 | `duck_yes` | 1.5 s | **Duck: yes** (1.5 s) |  |
| 35.3 | `no_1` | 0.8 s | Reachy: "[firmly] No." (0.5 s) under no1 (2.7 s), cut at 0.8 s |  |
| 36.1 | `duck_yes_fast_1` | 1.5 s | **Duck: yes_fast** (1.5 s) |  |
| 37.6 | `no_2` | 1.0 s | Reachy: "[louder] No!" (0.9 s) under no1 (2.7 s), cut at 1.0 s |  |
| 38.6 | `duck_yes_fast_2` | 1.5 s | **Duck: yes_fast** (1.5 s) |  |
| 40.2 | `asimov` | 4.4 s | Reachy: "[exasperated] Oh, Asimov. [pause] [pleading] Give me the strength, for this one." (4.0 s) under resigned1 (4.7 s), cut at 4.4 s |  |
| 44.7 | `duck_angry` | 2.6 s | **Duck: angry** (2.6 s) / Reachy: surprised2 (3.0 s), cut at 2.6 s | Microduck gets angry |
| 47.4 | `bad_duck` | 11.9 s | Reachy: "[gasps] Oh! [pause] [hurt] How... [pause] how dare you say that, to my face. [pause] [indignant] And my face is, like, fifty percent of me. [pause] [wounded] You are... [pause] you are a bad duck." (11.7 s) under displeased2 (2.9 s), contempt1 (3.6 s), reprimand3 (4.3 s) |  |
| 59.4 | `duck_play_dead` | 7.5 s | **Duck: play_dead** (7.5 s) / Reachy: surprised1 (2.5 s) | Microduck: shock quack, sits, rolls onto its back, legs up, death quack |
| 67.1 | `are_you_ok` | 12.1 s | Reachy: "[alarmed] Microduck? [pause] Microduck, are you all right? [panicking] No. Microduck, no. [pause] Did you die? [pause] Did it overwhelm your emotional circuitry? [pause] Did I kill you with my extremely insensitive comment?" (11.9 s) under scared1 (7.2 s), fear1 (3.5 s) |  |
| 79.4 | `lament` | 8.7 s |  / duck cues: 0.6 s duck_init, 3.6 s duck_policy, 8.2 s duck_sound / Reachy body yaw 1.4 / Reachy: "[grieving] Oh my dear friend. [pause] You were so young. [pause] You had so much to learn. [sobbing] What have I done. [pause] [wistful] I still remember your first quacks..." (8.5 s) under lost1 (8.1 s) | Reachy turns its body away (1.4 rad) and laments; the duck's two Start presses at 0.6 and 3.6 s; a quack right on 'first quacks' (8.2 s) |
| 88.1 | `duck_rises` | 0.3 s | **WAIT for ENTER.**  | Rémi: if the duck did not stand, Start again; turn it to face Reachy at three-quarters; then ENTER |
| 88.4 | `like_that` | 5.1 s | Reachy: "[dreamily] Yes. [pause] Like that. [pause] I still hear you, in my mind." (4.8 s) under thoughtful2 (5.5 s), cut at 5.1 s |  |
| 93.6 | `duck_laugh` | 3.0 s | **Duck: laugh** (3.0 s) | Microduck laughs |
| 96.7 | `alive` | 3.4 s |  / Reachy body yaw 0.0 / Reachy: "[gasps] Microduck! [overjoyed] You are alive!" (3.1 s) under amazed1 (3.4 s) | Reachy turns back |
| 100.1 | `duck_excited_2` | 3.4 s | **Duck: excited** (3.4 s) / Reachy: enthusiastic1 (2.7 s) | keep: Reachy's head goes up and down with the duck |
| 103.6 | `relieved` | 11.5 s | Reachy: "[relieved] I am so relieved to see you well. [pause] I will never talk to you like that again. [earnest] But please. [pause] Please, be careful. [gravely] The world is dangerous, and you are fragile. [pause] [gently] Can you promise me that?" (11.4 s) under relief1 (5.0 s), calming1 (6.1 s) |  |
| 115.2 | `duck_promise` | 1.5 s | **Duck: yes** (1.5 s) | Microduck promises (a nod) |
| 116.7 | `what_a_relief` | 2.4 s |  / duck cues: 0.9 s duck_skill / Reachy: "[relieved] What a relief." (0.9 s) under relief1 (5.0 s), cut at 1.0 s | as soon as Reachy says it, the roulade (Rémi handles Select) |
| 119.1 | `die_again` | 5.0 s | Reachy: "[hesitant] Did... [pause] did you die again?" (2.0 s) under uncertain1 (6.1 s), cut at 5.0 s |  |

New in v3: `say_at` (the line starts later in the beat), `cap` (Reachy's move chain is cut there), `body_yaw` (Reachy turns its body: 1.4 rad away for the lament, 0 back on "alive"). Every hold equals its emotion's length; gaps are 0-0.2 s.

## Lines (v3; `[tags]` are ElevenLabs v3 audio tags, stripped from captions)

Reachy escalates about the lake, the water resistance and the sun; the duck answers with the leash in its beak,
gets angry (the beak opens, the leash drops), then plays dead after "you are a bad duck"; Reachy laments, the
duck rises and quacks, Reachy is relieved, and the duck immediately does the roulade and probably falls forward:
"Did... did you die again?"

## Open choices (Rémi)

- The final fall: the roulade (as written) or a walk attempt / the wheee.
- Play dead ends limp; Start is the way up (the `duck_rises` wait). Torque off includes the jaw on the real
  robot (gated on "driving"), so the death quack will most likely play with the beak shut.
- The leash: which object, where the pick happens; the angry beak is forced wide for 0.4 s at the first bark.
- Reachy's emotion names per beat are first guesses from the library list; swap freely in `scene.json`.
