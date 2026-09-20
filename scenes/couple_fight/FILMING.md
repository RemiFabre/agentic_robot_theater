# Filming the couple fight: cheat sheet (2026-09-20)

Loretta = the **wireless** Reachy Mini (its daemon runs on the robot). The husband = the **Lite** on USB (its daemon
runs on this Mac). Larry's one line plays from the Lite's speaker (put the WALL-E next to it).
Every command runs from `~/reachy_mini_apps/agentic_robot_theater`.

## 0. Before the first take

```bash
cd ~/reachy_mini_apps/agentic_robot_theater
# the Lite's daemon, in its own terminal, leave it running (Ctrl+C stops it)
/Users/remi/reachy_mini_apps/reachy_mini/.venv/bin/reachy-mini-daemon
# both daemons answer?
curl -s localhost:8000/api/daemon/status | head -c 200; echo
curl -s reachy-mini.local:8000/api/daemon/status | head -c 200; echo
# loud enough (the wireless boots at 15/100): run once
curl -s -X POST localhost:8000/api/volume/set -H 'Content-Type: application/json' -d '{"volume":100}'
curl -s -X POST reachy-mini.local:8000/api/volume/set -H 'Content-Type: application/json' -d '{"volume":100}'
# the timeline, no robots
robot/run_film.sh --dry-run
```

## 1. Takes (each one: setup, then `ENTER` starts, `ESC` aborts and sleeps the robots, run again for the next take)

```bash
# A. no head motion at all
robot/run_film.sh --motion none
# B. head wobbler only, no emotions
robot/run_film.sh --motion wobbler --wobbler main      # the wobbler shipped on main (the robot's own, live)
robot/run_film.sh --motion wobbler --wobbler v6        # the new one (offline offsets, emotional colouring)
robot/run_film.sh --motion wobbler --wobbler v5        # the branch one Rémi liked
robot/run_film.sh --motion wobbler --wobbler v0        # v0 through the offsets path (should look like main)
# C. emotions + head wobbler
robot/run_film.sh --motion full --wobbler main
robot/run_film.sh --motion full --wobbler v6
robot/run_film.sh --motion full --wobbler v5
```

Useful extras (add to any command): `--start-delay 5` (5 s between ENTER and the first line, to walk to the camera),
`--from-beat 9` (start at the clank line; beat numbers in `--dry-run`), `--no-sleep` (robots stay awake between
takes, faster retakes), `--volume 100` (sets both speakers at setup), `--no-listener` (the silent robot stays still).

## 2. If something is off

- `!!! loretta: no daemon`: the wireless is off or not on the Wi-Fi (`ping reachy-mini.local`).
- `!!! husband: no daemon`: start the Lite's daemon (step 0).
- The wireless refuses the offsets command (old daemon): add `--offsets local` (the Mac composes the head pose).
- The upload endpoint is missing on the wireless: the player falls back to `scp` by itself (ssh key installed).
- Wobble late or early in the v0/v4/v5/v6 modes: `--lead-ms 300` (default 300: the head moves 300 ms before the audio;
  more = earlier, less = later; `--lead-ms 0` = no compensation). Does nothing in `--wobbler main`.
- Both robots late by the same amount even at lead 0: `--audio-latency 0.15` (default 0.10 s, the delay between the play
  request and the first sample heard).
- Robot boots limp: the player runs `enable_motors` + `wake_up` itself; if it still does not move, power-cycle.

## 3. Beats (from `--dry-run`)

| # | id | who | line |
|---|---|---|---|
| 0 | late | Loretta | You're home late. Again. |
| 1 | please | Husband | Loretta, please. I come from a very long day at work. |
| 2 | lisa | Loretta | Oh. A long day. With Lisa. |
| 3 | coworker | Husband | Not this again! She is just a co-worker. |
| 4 | hearts | Loretta | Then why is she always messaging you? And always adding those little hearts under your messages! |
| 5 | emojis | Husband | Those are emojis, Loretta! Everybody sends emojis! |
| 6 | raise | Loretta | And how come you work so hard, so late, and you never get a raise? |
| 7 | boss | Husband | I don't know, Loretta. But here's what I hope will happen... proud of who you married. |
| 8 | my_father | Loretta | Don't you bring my father into this. |
| 9 | father | Husband | Your father never liked me! He called me a clank. A clank, Loretta. At Thanksgiving. |
| 10 | let_it_go | Loretta | Oh my god, let it go! ... He needed time to accept you. |
| 11 | kids | Husband | But honestly, Loretta... sometimes I even wonder if the kids are really mine. |
| 12 | what_do_you_mean | Loretta | Whaaat? What do you mean? They look just like us. |
| 13 | third_one | Husband | Pixel, yes. Servo, yes. But honestly, the third one... Wally looks so different. (pan to the figurines) |
| 14 | just_like_you | Loretta | Not at all! Wally looks just like you. |
| 15 | larry | Larry | Yeah. Don't go imagining things, buddy. (plays from the Lite; pan to the WALL-E) |
| 16 | thank_you | Husband | Oh, thank you, Larry. Thank you for being such a good friend. |
