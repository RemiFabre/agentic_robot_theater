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

## Husband
Brief A (`husband_a/`): tired, whiny, placating sitcom husband, mild American, nasal, breathless.
- A0, A1, A2: three takes of the same brief, A1 has the most pitch movement.
Brief B (`husband_b/`): deep, gravelly, weary, slow, pompous stage actor, British.
- B0, B1: mid-deep; B2 `husband_b/design_2.mp3`: very deep (about eighty hertz), the gravel one.
Default for the first render (no slot left): the library voice `James - English Butler` already on the account.

The ranking words above come from a crude pitch and loudness analysis, not from listening. Rémi picks by ear.
