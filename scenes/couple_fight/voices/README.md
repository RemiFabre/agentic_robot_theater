# Voice candidates (ElevenLabs voice design, 2026-09-12)

Play them all in order with `scenes/couple_fight/voices/audition.sh` (each one is announced first).
Six per character: two text briefs, three previews each. The `generated_voice_id` of each preview is in the
`*.log` next to the folder; `uv run voice/design_voice.py --save <id> --name "..."` keeps one (one voice slot
was free on the account: it went to Loretta A1; freeing a slot is needed before saving a husband).

## Loretta
Brief A (`loretta_a/`): sharp, sassy, theatrical soap-opera wife, American, fast, a little nasal, icy to shouting.
- A0 `loretta_a/design_0.mp3`: higher, brighter, steadier pitch.
- A1 `loretta_a/design_1.mp3`: the widest pitch swings of the twelve (most over-acted). **Default pick, saved as voice `Loretta (couple fight)`.**
- A2 `loretta_a/design_2.mp3`: mid pitch, strong loudness contrast.
Brief B (`loretta_b/`): warm, deep, husky, Southern, a wounded diva.
- B0 `loretta_b/design_0.mp3`: high and even.
- B1 `loretta_b/design_1.mp3`: highest of the set.
- B2 `loretta_b/design_2.mp3`: the lowest, huskiest Loretta.

Brief C (`loretta_c/`, 2026-09-20, after Rémi found A1 too annoying): warm, low, natural, slightly husky, American,
measured and dry, quietly furious rather than shrill, no nasal edge.
- C0 `loretta_c/design_0.mp3`: low (about two hundred fifteen hertz median), short sample.
- C1 `loretta_c/design_1.mp3`: a bit higher.
- C2 `loretta_c/design_2.mp3`: the lowest and longest. **Take 4 pick, saved as `6UPiLePyL7dZLvH5zq4j` "Loretta 2 (couple fight)".**
  The old A1 voice `nJhrqPUzktvhpy7Sfrrx` was deleted from the account to free the slot (its previews stay in `loretta_a/`).

## Husband
Brief A (`husband_a/`): tired, whiny, placating sitcom husband, mild American, nasal, breathless.
- A0, A1, A2: three takes of the same brief, A1 has the most pitch movement.
Brief B (`husband_b/`): deep, gravelly, weary, slow, pompous stage actor, British.
- B0, B1: mid-deep; B2 `husband_b/design_2.mp3`: very deep (about eighty hertz), the gravel one.
The husband is the library voice `James - English Butler` (Rémi likes it, kept for take 4).
Larry (the WALL-E friend, one line) is the library voice `Retro Robot`.

The ranking words above come from a crude pitch and loudness analysis, not from listening. Rémi picks by ear.
