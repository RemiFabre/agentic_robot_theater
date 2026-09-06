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

## Beats (times from beat 0, lengths from the wavs and the emotion lengths; total 127 s + the pause at `duck_rises`)

| t | beat | length | who / what | camera, notes |
|---|---|---|---|---|
| 0.0 | `duck_excited` | 3.5 s | **Duck: excited** (3.4 s) | Microduck, excited about the lake |
| 3.8 | `duck_pick` | 5.0 s | **Duck: ground_pick** / Reachy: attentive1 | Microduck picks the leash up from the ground (leash placed at the tested spot) |
| 9.1 | `lake` | 9.9 s | Reachy: "[sighs] The lake. [pause] The lake. [weary] You are obsessed with the lake. [pause] But you are not a dog, Microduck. [firmly] You are a Microduck." (9.6 s) under reprimand1 |  |
| 19.3 | `duck_closed_1` | 2.6 s | **Duck: closed_quack** (2.2 s) / Reachy: inquiring1 | Microduck quacks with the beak closed (the leash stays in) |
| 22.1 | `difference` | 4.1 s | Reachy: "[patiently] The difference... [pause] the difference, is your water resistance." (3.8 s) under thoughtful1 |  |
| 26.6 | `duck_closed_2` | 2.6 s | **Duck: closed_quack** (2.2 s) / Reachy: attentive2 |  |
| 29.4 | `sun` | 11.3 s | Reachy: "[worried] And the sun. [pause] Do we even know what the sun does to us? [anxious] Do we use sun cream? [pause] That is also a liquid. [escalating] Will it get into our circuits? [alarmed] Will it get into MY circuits?" (11.0 s) under anxiety1, frustrated1 |  |
| 41.0 | `duck_angry` | 3.5 s | **Duck: angry** (2.6 s) / Reachy: surprised2 | Microduck gets angry: the beak opens, the leash drops |
| 45.0 | `bad_dog` | 9.1 s | Reachy: "[shocked] ... [pause] How... [pause] how dare you say that, to my face. [pause] [wounded] You are... [pause] you are a bad dog." (8.6 s) under displeased2, contempt1 |  |
| 54.6 | `duck_play_dead` | 8.0 s | **Duck: play_dead** (7.5 s) / Reachy: surprised1 | Microduck: shock quack, sits, tips over backwards, death quack |
| 63.4 | `are_you_ok` | 12.3 s | Reachy: "[alarmed] Microduck? [pause] Microduck, are you all right? [panicking] No. Microduck, no. [pause] Did you die? [pause] Did I kill you with my extremely insensitive comment? [pause] Did it overwhelm your emotional circuitry?" (11.9 s) under scared1, fear1 |  |
| 76.3 | `lament` | 9.1 s | Reachy: "[grieving] Oh my dear friend. [pause] You were so young. [pause] You had so much to learn. [sobbing] What have I done. [pause] [wistful] I still remember your first quacks..." (8.5 s) under downcast1, lonely1 |  |
| 85.7 | `duck_rises` | 1.0 s | **WAIT for ENTER.**  / Reachy: sad1 | Rémi: Start (sit-stand rise), turn the duck to face Reachy with the stick, then ENTER |
| 86.9 | `duck_quack_1` | 3.0 s | **Duck: curious** (3.0 s) | the risen duck quacks (Reachy still looks away) |
| 90.2 | `like_that` | 5.1 s | Reachy: "[dreamily] Yes. [pause] Like that. [pause] I still hear you, in my mind." (4.8 s) under thoughtful2 |  |
| 95.5 | `duck_quack_2` | 1.6 s | **Duck: yes** (1.5 s) | quack quack |
| 97.7 | `alive` | 3.4 s | Reachy: "[gasps] Microduck! [overjoyed] You are alive!" (3.1 s) under amazed1 |  |
| 101.3 | `duck_excited_2` | 3.5 s | **Duck: excited** (3.4 s) / Reachy: enthusiastic1 |  |
| 105.1 | `relieved` | 12.1 s | Reachy: "[relieved] I am so relieved to see you well, and alive. [pause] I will never talk to you like that again. [earnest] But please. [pause] Please, be careful. [gravely] The world is dangerous, and you are fragile." (11.7 s) under relief1, loving1, calming1 |  |
| 117.6 | `duck_roulade` | 4.0 s | **Duck: roulade** / Reachy: surprised1 | Microduck does the roulade at once and very likely falls forward |
| 122.4 | `die_again` | 5.0 s | Reachy: "[hesitant] Did... [pause] did you die again?" (2.0 s) under uncertain1 |  |

## Lines (refined from Rémi's draft; `[tags]` are ElevenLabs v3 audio tags, stripped from captions)

Reachy escalates about the lake, the water resistance and the sun; the duck answers with the leash in its beak,
gets angry (the beak opens, the leash drops), then plays dead after "you are a bad dog"; Reachy laments, the
duck rises and quacks, Reachy is relieved, and the duck immediately does the roulade and probably falls forward:
"Did... did you die again?"

## Open choices (Rémi)

- The final fall: the roulade (as written) or a walk attempt / the wheee.
- Play dead ends limp; Start is the way up (the `duck_rises` wait). Torque off includes the jaw on the real
  robot (gated on "driving"), so the death quack will most likely play with the beak shut.
- The leash: which object, where the pick happens; the angry beak is forced wide for 0.4 s at the first bark.
- Reachy's emotion names per beat are first guesses from the library list; swap freely in `scene.json`.
