# The lake, v2 (2026-09-04)

Reachy Mini has to tell Microduck that the trip to the lake is off, and is too scared to say why.
Same pipeline and same voice as `microduck_meets_reachy`: ElevenLabs voice "Reachy Mini Protocol",
voice_id `0m5sA4wKd4nKxBtRAu0n` (from `scenes/microduck_meets_reachy/NOTES.md`), model `eleven_v3`,
speed 1.0, rendered with `voice/render_lines.py`. Head wobble while speaking, silent emotion moves
from `pollen-robotics/reachy-mini-emotions-library` chained under the lines.

## Run it

```bash
robot/run_on_robot.sh scenes/lake --start-delay 5
```

Setup takes a few seconds (loads the moves, motors on), then it prints `ENTER to start`.
Press ENTER, start filming, and 5 s later the robot wakes up and beat 0 begins
(change `--start-delay` to taste; `--from-beat K` restarts from a beat; ESC aborts and sleeps).

Re-render a line (spends credits): `uv run voice/render_lines.py scenes/lake --voice 0m5sA4wKd4nKxBtRAu0n --only excuse`

## Beats (times from the wake-up, computed from the WAVs and the recorded move lengths)

| t | beat | length | Reachy | camera (Rémi, phone vertical) / Rémi's voice |
|---|---|---|---|---|
| 0.0 | `hey` | 3.6 s | "Hey, Microduck!" (1.3 s) under `come1` (beckoning head, 3.2 s) | on Microduck walking |
| 4.0 | `talk` | 4.3 s | "[sighs] Look, I have to talk to you." (1.8 s) under `understanding1` (serious nod, 3.9 s) | pan to Reachy |
| 8.6 | `duck_curious` | 4.7 s | silent, `attentive1` (listening, head tilts, 4.3 s), hold 3.5 s | on Microduck: LB curious ("what? what?", ~3 s) |
| 13.6 | `bad_news` | 12.2 s | "I know you were very excited to go to the lake. But we won't be able to go today. I'm sorry." (6.4 s) under `resigned1` (4.7 s) then `no_sad1` (7.0 s). The head sinks into the sad "no" right on "I'm sorry" (~5.7 s in), stays bowed until ~10 s, comes back up by 12 s | on Reachy |
| 26.2 | `but_why` | 6.5 s | silent, `uncertain1` (listening, no answer, 6.1 s), hold 6 s | Rémi, off-screen: "But why?" Say it as the head comes back up at the end of `bad_news` (~24-26 s); Reachy then stays uncertain for 6.5 s |
| 33.0 | `excuse` | 8.2 s | "[nervously] Because, well... [pause] the meteorological conditions... [nervous laugh] are not optimal right now." (6.9 s) under `shy1` (embarrassed, head dips, 7.8 s) | on Reachy |
| 41.5 | `window` | 6.4 s | silent, `uncomfortable1` (looks down / away, 6.0 s), hold 4 s | pan to the window (beautiful day) and back |
| 48.2 | `are_you_scared` | 2.9 s | silent, `surprised1` (caught, 2.5 s), hold 2.5 s | Rémi, off-screen: "Are you scared?" Say it as the camera comes back from the window (~47-48 s), so the startle reads as the reaction |
| 51.3 | `not_scared` | 9.7 s | "[quickly] No. [dismissive] I'm not scared. [proudly] I'm just optimizing our long-term survivability." (4.7 s) under `no1` (firm no, 2.7 s), `proud2` (satisfied, 3.2 s), then `fear1` (a 3.5 s crack of fear after the words, ~6.3 s in) | on Reachy |
| 61.4 | `the_end` | 8.0 s | silent, `sad2`: the head sinks slowly over ~2 s, is fully down (antennas drooping) from ~2.5 s to ~5 s, then comes back up; hold 8 s | on Reachy, end |
| 69.4 | end | | lingers 10 s, then goes to sleep (ESC = sleep now) | |

**Total: 69.4 s from the wake-up** (plus the 5 s start delay and the wake-up move itself);
about 80 s including the 10 s linger before it sleeps.

Notes:
- Every recorded move returns to the neutral pose at its end, `sad2` included. For the final
  shot, either cut the film while the head is down (61.4 + 2.5 s to 61.4 + 5 s), or press ESC right
  after `the_end` so the robot folds slowly into its sleeping pose on camera (that is the
  `goto_sleep` move, also a slow lowering of the head).
- Beats never cut an emotion short, so the silent beats last as long as their move
  (`duck_curious` 4.7 s, `window` 6.4 s) even though the requested holds are 3.5 s and 4 s.
- Lines are `eleven_v3` with audio tags (`[sighs]`, `[sympathetic]`, `[sadly]`, `[nervously]`,
  `[pause]`, `[nervous laugh]`, `[quickly]`, `[dismissive]`, `[proudly]`), which is non-deterministic:
  re-render one line with `--only` and keep the take you like. Rendered line lengths, silences
  trimmed: hey 1.31 s, talk 1.84 s, bad_news 6.39 s, excuse 6.85 s, not_scared 4.73 s.
- Microduck's beats are the pauses: `duck_curious` = LB (curious) on the pad; the duck walks in
  under `hey`.
- v1 (2026-09-04 morning) had a 3 s `but_why`, a "lying" excuse ("it's raining outside") and ended
  right after the window pan; Rémi asked for 3 more seconds before the excuse, a scared (not lying)
  character, and the "Are you scared?" exchange.
