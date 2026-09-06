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

## Beats (times from beat 0, lengths from the wavs and the emotion lengths; total 135 s + the pause at `duck_rises`; v2 of 2026-09-06 evening)

| t | beat | length | who / what | camera, notes |
|---|---|---|---|---|
| 0.0 | `duck_excited` | 3.5 s | **Duck: excited** (3.4 s) | Microduck, excited about the lake |
| 3.8 | `duck_pick` | 5.0 s | **Duck: pick** (3.0 s) / Reachy: attentive1 | Microduck picks the leash up (the beak opens on the way down, closes at the ground) |
| 9.1 | `lake` | 9.1 s | Reachy: "[sighs] The lake. [pause] The lake. [weary] You are obsessed with the lake. [pause] But you are not a duck. [firmly] You are a Microduck." (8.8 s) under reprimand1 |  |
| 18.5 | `duck_mmh_1` | 2.2 s | **Duck: mmh** (2.0 s) / Reachy: inquiring1 | "What do you mean?" — the beak opens, the leash falls |
| 20.9 | `difference` | 4.1 s | Reachy: "[patiently] The difference... [pause] the difference, is your water resistance." (3.8 s) under thoughtful1 |  |
| 25.4 | `duck_quack_quack` | 1.4 s | **Duck: chirp** x2 / Reachy: attentive2 | quack quack (RT twice) |
| 27.0 | `sun` | 9.2 s | Reachy: "[worried] And the sun. [anxious] Do we even know what the sun does to us? [alarmed] Do we use sun cream? That is also a liquid! [panicking] Will it get into our circuits? [pause] [firmly] We shouldn't go." (8.9 s) under anxiety1, frustrated1 |  |
| 36.5 | `duck_mmh_2` | 2.2 s | **Duck: mmh** (2.0 s) / Reachy: surprised2 | "What do you mean?" |
| 39.0 | `duck_yes` | 1.6 s | **Duck: yes** (1.5 s) |  |
| 40.8 | `no_1` | 0.7 s | Reachy: "[firmly] No." (0.5 s) under no1 |  |
| 41.6 | `duck_yes_fast_1` | 1.5 s | **Duck: yes_fast** (1.5 s) |  |
| 43.2 | `no_2` | 1.1 s | Reachy: "[louder] No!" (0.9 s) under no1 |  |
| 44.5 | `duck_yes_fast_2` | 1.5 s | **Duck: yes_fast** (1.5 s) |  |
| 46.3 | `asimov` | 4.3 s | Reachy: "[exasperated] Oh, Asimov. [pause] [pleading] Give me the strength, for this one." (4.0 s) under exhausted1 |  |
| 51.1 | `duck_angry` | 3.0 s | **Duck: angry** (2.6 s) / Reachy: surprised2 | Microduck gets angry |
| 54.6 | `bad_duck` | 8.8 s | Reachy: "[gasps] Oh! [pause] [hurt] How... [pause] how dare you say that, to my face. [pause] [wounded] You are... [pause] you are a bad duck." (8.3 s) under displeased2, contempt1 |  |
| 63.8 | `duck_play_dead` | 8.5 s | **Duck: play_dead** (7.5 s) / Reachy: surprised1 | Microduck: shock quack, sits, keels over backwards, torque back on, death quack |
| 73.1 | `are_you_ok` | 12.3 s | Reachy: "[alarmed] Microduck? [pause] Microduck, are you all right? [panicking] No. Microduck, no. [pause] Did you die? [pause] Did I kill you with my extremely insensitive comment? [pause] Did it overwhelm your emotional circuitry?" (11.9 s) under scared1, fear1 |  |
| 86.0 | `lament` | 8.8 s |  / duck cues: 0.6 s duck_init, 3.6 s duck_policy / Reachy: "[grieving] Oh my dear friend. [pause] You were so young. [pause] You had so much to learn. [sobbing] What have I done. [pause] [wistful] I still remember your first quacks..." (8.5 s) under lost1, downcast1 | Reachy looks away; 0.6 s later the duck's first Start (torque on, ramp home), 3 s later the second Start (policy on): the duck stands up |
| 94.8 | `duck_first_quack` | 1.0 s | **Duck: chirp** x1 | a quack right after 'your first quacks' |
| 96.0 | `duck_rises` | 0.3 s | **WAIT for ENTER.**  | Rémi: if the duck did not stand, Start again; turn it to face Reachy with the stick; then ENTER |
| 96.5 | `like_that` | 5.1 s | Reachy: "[dreamily] Yes. [pause] Like that. [pause] I still hear you, in my mind." (4.8 s) under thoughtful2 |  |
| 101.9 | `duck_laugh` | 3.0 s | **Duck: laugh** (3.0 s) | Microduck laughs |
| 105.3 | `alive` | 3.4 s | Reachy: "[gasps] Microduck! [overjoyed] You are alive!" (3.1 s) under amazed1 |  |
| 108.9 | `duck_excited_2` | 3.5 s | **Duck: excited** (3.4 s) / Reachy: enthusiastic1 |  |
| 112.7 | `relieved` | 12.4 s | Reachy: "[relieved] I am so relieved to see you well. [pause] I will never talk to you like that again. [earnest] But please. [pause] Please, be careful. [gravely] The world is dangerous, and you are fragile. [pause] [gently] Can you promise me that?" (11.4 s) under relief1, loving1, calming1 |  |
| 125.0 | `duck_roulade` | 4.0 s | **Duck: roulade** / Reachy: surprised1 | one second of thought, then the roulade; Rémi handles Select |
| 129.8 | `die_again` | 5.0 s | Reachy: "[hesitant] Did... [pause] did you die again?" (2.0 s) under uncertain1 |  |

## Lines (refined from Rémi's draft; `[tags]` are ElevenLabs v3 audio tags, stripped from captions)

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
