# STATUS (couple_fight), 2026-09-12, end of the first hour

Read this first. Everything is committed locally (this repo and the wobbler worktree), nothing pushed.

## Listen and look (absolute paths, all on disk)
- The whole scene, take 3, 55 s: `afplay /Users/remi/reachy_mini_apps/agentic_robot_theater/scenes/couple_fight/audio/scene_mix.wav`
- Voice candidates, 12, announced one by one: `scenes/couple_fight/voices/audition.sh` (descriptions in `voices/README.md`)
- Offscreen previews (MuJoCo puppets, wobbler offsets on the head, lines mixed, captions):
  `scenes/couple_fight/preview_v0.mp4`, `preview_v5.mp4`, `preview_v0_vs_v5.mp4` (side by side), `preview_v5_vs_v6.mp4`
- Live simulation proof (two real sim daemons, two MuJoCo windows captured side by side):
  `scenes/couple_fight/sim_v0.mp4`, `sim_v5.mp4`, `sim_v6.mp4` (about 24 s each, the first beats)
- Wobbler plots v0 / v5 / v6 on the nine lines:
  `~/reachy_mini_apps/reachy_mini_wobbler/examples/wobbler_lab/out/couple_fight/summary.png` (+ one PNG per line, `metrics.md`)
- The study memo: `scenes/couple_fight/MEMO_learning_from_video.md`

## Done
1. **Scripts**: `script_v1.md` (your draft, tightened), `script_v2.md` (every trope, nine lines), `script_v3.md`
   (eight lines plus a button, with a twist: Lisa is the office printer, she sends hearts when the toner is low).
   **Take 3 is the one rendered**: shortest lines, the jump from the hearts straight to "your father" reads as
   panic, and the calm twist at the end gives the wobbler a contrast after the shouting. Every line carries v3 tags.
2. **Voices**: 12 designed candidates in `voices/` (two briefs per character, three previews each).
   Loretta A1 (widest pitch swings of the twelve) saved as `nJhrqPUzktvhpy7Sfrrx` "Loretta (couple fight)".
   The husband in this render is the library voice `James - English Butler` (see the limits below).
   Ranking words in the README come from a crude pitch/loudness analysis, not from listening: you pick by ear.
3. **Scene**: `scene.json`, nine beats, each with `speaker`, `emotion` + `energy` (the wobbler colouring),
   `emotions` (speaker's recorded moves), `listener_emotions` (the other robot). Format in `FORMATS.md`.
   Two players:
   - `robot/skit_duo.py`: live on two sim daemons (`robot/run_sim_duo.sh` starts them, ports 8000 loretta / 8001
     husband), `--wobbler v0|v4|v5|v6|none|daemon`; the head offsets come from `audio/offsets/<id>.<version>.json`
     and are composed on the recorded move like the daemon composes speech offsets. Audio through `afplay`.
     `robot/record_duo.sh v5` records both windows side by side and muxes the lines. Details: `robot/SIM_NOTES.md`.
   - `robot/render_duo.py`: offscreen render (mjlab venv), same scene, same offsets, `--side-by-side v0,v5`.
4. **Wobbler v6** (worktree `~/reachy_mini_apps/reachy_mini_wobbler`, branch `wobbler-v6-explorations`, 4 commits):
   `speech_tapper_v6.py` = v5 + `emotion` / `energy` inputs (`set_emotion()` at runtime, cross-fade 300 ms) +
   two phrase layers (phrase-final tilt from the F0 slope of the last 300 ms, up on a rise, down on a fall; a per-phrase
   yaw drift). Colourings: angry (sharper, jabs, forward lean), sassy (yaw/roll glides alternating sides every
   three nuclei), sad (small, low, slow, occasional drop), pleading (up and forward, frequent small nods).
   Registered in `head_wobbler.py` (`WOBBLER_VERSION=v6 WOBBLER_EMOTION=angry WOBBLER_ENERGY=1.2`), in the lab
   (`simulate.py`, new `offsets.py` and `compare.py`), in `live_mic_wobble.py` (`--emotion`). BLOG.md section 16.
   Metrics on the nine lines: silences stay silent (mean stillness 0.87 vs 0.89 for v5, the loss is only the 300 ms
   phrase-final tilt), onset alignment 1.16 like v5 (v0: 0.98), and the colouring shows: `hearts` (angry 1.4) has
   9 deg rotation RMS, `father` (sad 0.9) 1.8 deg, where v5 gives 4 to 5 deg on both.
5. **Memo**: `MEMO_learning_from_video.md`, one page. Headline: feasible and cheap at the model level (3 angles at
   20 Hz, a causal GRU/TCN under 1 M params runs on the CM4); data exists (BEAT2 60 h mocap with head joints and
   emotion labels, HDTF and TalkingHead-1KH videos with pose extraction); the real risks are licences, retargeting
   to the Stewart platform, and GENEA's finding that speech-appropriateness is barely above chance even for the best
   systems. Recommends supervised imitation first, then a preference step on your filmed A/B pairs; full RL optional.
   Nothing was trained.

## Decisions I made (say if you disagree)
- Rendered take 3, not 1 or 2. Take 2 keeps "you never listen" and "my mother was right" if you want the longer pile-on.
- The clank line got "At Thanksgiving." as a rider, and Loretta's "He meant it a little." as a whispered button.
- Emotions per beat are first guesses (reprimand1, resigned1, contempt1, no1, furious1, displeased2 + lost1,
  reprimand3 + downcast1, calming1, contempt1); swap in `scene.json`.
- v6 amplitude caps: 1.5 x the v5 maxima (39 deg pitch, 48 yaw, 17 roll). `hearts` at energy 1.4 reaches 26 deg
  peaks and 27 mm forward: probably too much on the real robot, lower `energy` there to 1.1 if it looks wild.
- Sim: the launcher defaults to `--no-media` (with media both daemons bind the same camera socket); the scene audio
  goes through afplay. The two daemons left running now were started with `MEDIA=1` (loretta PID 89081, husband
  PID 89082, `robot/run_sim_duo.sh stop` stops them). Both MuJoCo windows open at the same screen spot: drag one aside.

## Account limits found (important)
- **ElevenLabs characters**: about 2800 were left in the cycle when I started (reset 2026-10-02). Take 3 costs 870.
  About 1900 remain: enough to re-render two or three lines, not the whole scene twice.
- **Voice slots**: 10 of 10 used (9 before, Loretta took the last). A designed husband needs a freed slot;
  I deleted nothing. The library voices (Dan, Grandpa Spuds, Minerva, James, Starboy, Jean Atlas, Retro Robot)
  can be removed and re-added from the Voice Library if you want slots.

## Questions for you
1. Which Loretta (A0..B2) and which husband (A0..B2)? Freeing one slot lets me save the husband and re-render his
   five lines (about 480 characters).
2. Take 3 as is, or take 2's longer pile-on? Any line to cut? `father` is 8.2 s, the longest.
3. The v6 colourings: which ones read as intended in the previews, which look like twitches? Real robot signs
   (pitch down = positive, x forward) are assumed from v5 and unverified.
4. Is the memo's medium plan (streaming GRU/TCN on 20 to 50 h of extracted poses, 5 to 20 GPU-hours) the right
   size to discuss with Hugging Face, or do you want the small distillation first?

## Not done / unverified
- Nothing was heard by me (no ears): the acting of the takes and the voices need your ear.
- Sim daemon's own wobbler on played audio: `--wobbler daemon` ran two beats without error on the media daemons,
  but nobody checked that the head moved or that sound came out. `robot/record_duo.sh daemon` is ready for that.
- v6 on the real robot: untested. CM4 cost not measured (same FFT as v5 plus scalar ops).
- The mp4 files are gitignored in this repo (as for episode 3), so the previews and sim recordings live on disk only.
- The screen captures run at 9 fps (window-server bound): fine to judge the motion, not for publishing.
- The renderer agent queued a re-render of `preview_v0.mp4` and `preview_v0_vs_v5.mp4` with its last fix (beat timing,
  the newer renders are 66 s, the first v0 render 63 s). If a file looks half written when you open it, wait a few
  minutes: `pgrep -fl render_duo.py` shows whether it is still running.
