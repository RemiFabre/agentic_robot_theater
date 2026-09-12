# Couple fight scene + head wobbler exploration. Brief for a fresh agent (2026-09-12, written by Rémi's previous session)

Rémi is away for about one hour, then comes back to check progress. Work autonomously until then; leave him rendered
things to look at and listen to (open files on his screen with `open`, audition audio with `afplay`), and a short
STATUS.md in this folder with what is done, what you decided, and what you need from him. He will read that first.

## The goal, in his words (lightly cleaned up)

1. **A test scene between two Reachy Mini robots, in simulation first** ("robot theater"), and the same scene must be
   viewable with different head-wobbler implementations: the default one shipped on `main`, the one from his branch
   (v4 and v5, which he liked), and the new explorations you make. Once the scene is good enough he will film it on real
   robots and ask the community what they think of the wobbler versions.
2. **Improve the head wobbler.** He has worked on it several times; the last time was with a less capable coding agent.
   Read that work first (pointers below) to understand and then push it further. New ideas he wants explored:
   - **Emotional colouring of the wobble.** The wobbler stays general purpose (it must work in any scenario, driven by
     the speech audio as today) but takes an extra input: the emotion the robot is trying to display (sassy, angry,
     sad, pleading, ...) and maybe a notion of amplitude or energy. Example: "sassy" could add small left/right glides.
     Explore several such colourings, make them testable in the scene.
   - Anything else code based that makes the head motion feel more alive and better tied to the voice.
   - **A study, not an execution:** is there an angle to get human-labelled data (e.g. talking heads on YouTube, or
     existing datasets of speech + head motion) and learn a speech-to-head-motion model (imitation / RL) transferable to
     Reachy Mini? Write a short memo (feasibility, data sources, what compute it would take; Hugging Face compute could
     be available). Do NOT start training anything on your own; he wants to discuss how to articulate it first.
3. **The scene must be very emotional and funny to listen to:** a hyperbolic robot husband-and-wife fight using classic
   couple-fight tropes, voices that sometimes speak fast and angry, sometimes over-act. Escalate quickly. His draft:
   - Wife: "You're home late again."
   - Husband: "Loretta, please. Loretta, please. I come from a very long session at work." (something that says he had
     a lot of work)
   - Wife: "Oh. And I assume you were working with Lisa."
   - Husband: "Loretta, please. Not this again. She is just a co-worker."
   - Wife: "Oh yes? Then why is she always, always messaging you? And all those little hearts I see?"
   - ... find a quick path to a strong escalation (a typical couple fight), then:
   - Husband: "Your father never liked me. He called me a clank." (robot slur, keep it)
   - Wife: "Oh my god, let it go! It was sixteen years ago and he didn't mean it."
   He says this may be too long; iterate on the text (several versions), keep it punchy. Two voices (Loretta and the
   husband), designed with ElevenLabs voice design, several candidates each, auditioned on his screen. He picks.
   Lines rendered with ElevenLabs v3 audio tags for the acting (`[shouting]`, `[sighs]`, `[sarcastic]`, `[fast]`...).

## What exists (read these before writing code)

- This repo (`~/reachy_mini_apps/agentic_robot_theater`, README.md): the skit pipeline. `scenes/<name>/scene.json` is a
  list of beats (`text` = spoken line rendered to `audio/<id>.wav`, `emotions` = chain of recorded moves, `hold`, `gap`,
  `say_at`, `cap`, `body_yaw`...). `voice/design_voice.py --desc ... --text ... --play` designs voice candidates,
  `--save <id> --name ...` keeps one; `voice/render_lines.py scenes/<name> --voice <id> [--play]` renders every line
  (`eleven_v3`, tags are stripped from captions later). `robot/skit.py` plays a scene on a robot (REST/SDK, calls
  `mini.enable_wobbling()` while it speaks). `scenes/episode3/` is the latest two-character scene (Reachy Mini +
  Microduck) and its README describes the beat table format; `robot/run_episode3.sh` shows how two robots were run
  from one script. Python: `uv run` from this folder; `ELEVENLABS_API_KEY` is in the shell env.
  Two robots in one scene is new for Reachy-Reachy: the scene needs a `speaker` field per beat (e.g. "loretta" /
  "husband") and the player must drive two daemons (two sim instances on different ports).
- **Reachy Mini simulation:** `reachy-mini-daemon --sim` (MuJoCo; on macOS use `mjpython -m reachy_mini.daemon.app.main --sim`),
  docs in the reachy_mini repo `docs/source/platforms/simulation/get_started.md`. Check how to run two instances
  (port flag) and whether the sim daemon runs the wobbler on played audio the same way the real one does (the live
  wobbler runs inside the audio playback path of the daemon). If the sim cannot wobble, drive the head yourself from
  the wobbler's offsets (the offline harness below computes them from a wav) so every version is comparable.
- **The wobbler work, branch `1060-i-swear-the-wobbler-sucks-lets-do-better` of `~/reachy_mini_apps/reachy_mini`**
  (GitHub issue #1060 "I swear the wobbler sucks"). Read in this order: `examples/wobbler_lab/BLOG.md` (his development
  journal), `examples/wobbler_lab/v4_v5_explained.md`, then `src/reachy_mini/motion/speech_tapper_v4.py`, `_v5.py`,
  `head_wobbler.py`, `examples/wobbler_lab/{simulate,features,metrics,plot,run}.py` (offline harness: wav in, head
  offsets + plots out) and `examples/live_mic_wobble.py` (version selector). v0 = `speech_tapper.py` = the default on
  `main`, immutable baseline. v1-v3 are frozen historical experiments. v4 = strict gate + AGC + rising-edge nucleus +
  breath layer; v5 = v4 + F0-relative pitch tilt. Known constraints from his notes: the live wobbler must be cheap
  (it runs on the CM4 of the wireless robot: no librosa/pyin, no big FFTs live; the offline harness may use anything);
  silences must be reliably silent (his main complaint about v0: it fails to deactivate on reverb tails, breath, room tone).
  **Do not touch the main checkout** (it has uncommitted face-tracking work and ~23 untracked files). Use a worktree:
  `cd ~/reachy_mini_apps/reachy_mini && git worktree add ../reachy_mini_wobbler -b wobbler-v6-explorations origin/1060-i-swear-the-wobbler-sucks-lets-do-better`
  and work in `~/reachy_mini_apps/reachy_mini_wobbler`. New versions land as new files (v6, v7...), never edits to v0.
- Voices used so far: Reachy Mini's series voice is ElevenLabs `0m5sA4wKd4nKxBtRAu0n` ("Reachy Mini Protocol"); do not
  reuse it here, these are two new characters.

## Deliverables for the one-hour checkpoint (in order)

1. `scenes/couple_fight/script_v1.md` .. `script_v3.md`: three takes on the dialogue (short, escalating, funny), with the
   v3 audio tags in place. Pick your favourite for rendering, say why in STATUS.md.
2. Voice candidates: 3-4 per character in `scenes/couple_fight/voices/` (mp3 + a one-line description each), opened /
   played for him. Render the chosen script with your top pick for each so he can hear the whole scene (`audio/`).
3. `scenes/couple_fight/scene.json` with a `speaker` per beat and a player that runs it on two simulated Reachy Minis
   (or a rendered preview video if live sim is not achievable in the hour), selectable wobbler version:
   `--wobbler v0|v4|v5|v6...`. Show at least one preview video / screen recording of the scene with two versions.
4. `wobbler_lab` explorations: at least one new version (v6) with an emotion/energy input, run through the offline
   harness on the rendered lines, with plots comparing v0 / v5 / v6 on the same wav.
5. `scenes/couple_fight/MEMO_learning_from_video.md`: the data + learning study (one page, honest about feasibility).
6. STATUS.md: done / decided / questions for him.

## Rules

- Commit locally, small commits, in both repos (this one and the worktree). **Never push.** Never `git add -A` in
  reachy_mini (stage explicit paths).
- No em-dashes anywhere (prose, code comments, scripts): Rémi finds them a tell of AI writing.
- Show, don't tell: every audio candidate is played (`afplay`) and every visual is opened on his screen with an
  absolute path. Iterate on stills/short clips before long renders.
- Keep lines and prose short. Numbers and acronyms in spoken text written the way they should be pronounced.
- If something needs his decision (which voice, which script), make a default choice, keep going, and list the
  question in STATUS.md. Do not block on him.
