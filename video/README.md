# video/ — post-production tools

Two generations of tools live here. `captions.py` + `gen_music.py` + `mix_music.sh` are the episode 1
one-shot pipeline (ElevenLabs STT for word times). The rest came from episode 2 ("the lake",
2026-09-04/05; full build log in `~/agentic_video_montage/microduck_lake_video/work/NOTES.md`):

| step | tool | notes |
|---|---|---|
| line starts | `align_lines.py` | cross-correlates each line WAV with the footage (24 log-band envelopes, 200-4000 Hz); constrain each search window with the beat table, a short line under noise locks onto the wrong peak |
| word times | `transcribe_whisper.py` | faster-whisper medium, cpu/int8 (no CUDA on the Mac); run on the TTS WAVs (word offsets) and on the footage (the human's lines). Ignore a hallucinated "Thanks for watching" at the very end |
| captions | `build_captions.py` -> `burn_captions.py` | captions.json/srt in the trimmed timeline; PIL overlays (no libass/drawtext in Homebrew ffmpeg). Look: Arial Bold 58, white + 3 px black stroke, amber (255,196,60) speaker tag 30 px caps, black 150-alpha rounded box r=18, bottom margin 90 (landscape) / 160 (vertical). Second speaker = "THE HUMAN" tag |
| phone audio | `clean_dialogue.py` | phone "wind" is sub-150 Hz rumble: profile per octave, then steep high-pass (2x `highpass=f=220:poles=2`) only where it lives, gentler 160 Hz elsewhere, crossfaded segments; `afftdn` barely helps, `arnndn` eats the voice. Then level every line into one band (+10 dB on far-mic lines) with `alimiter` |
| one music bed | `gen_music.py` + `mix_music.sh` | ElevenLabs Music, one request at a time; the approved mix: music -12 dB, `sidechaincompress=threshold=0.02:ratio=5:attack=40:release=700`, fades with the picture. Normalise the voice, never retune this template. `THR` env var overrides the threshold |
| music switch on a story turn | `mix_two_cues.sh` | cue A cut in 0.25 s at the reveal, 0.3 s of nothing, cue B from its first downbeat (`silencedetect`, seek with input `-ss`, then `adelay`) at cue A + 2 dB. Prompt cue B as a 20-22 s track that "starts immediately on a strong downbeat". The user called this "PERFECT" |
| landscape from vertical + gags | `landscape_gags.py` | 1920x1080 with black sides; freeze on the reveal and stamp words one by one (Impact, boom SFX per word); freeze on the last pose and type a verdict line (Courier New Bold, key click per char, bell) timed so the cue's natural last hit lands on the last letters |

Measure audio with **input** seek (`ffmpeg -ss X -t Y -i f -af astats`); output seek feeds astats the whole file.
zsh mangles `$VAR[..]` and `$VAR:x` inside filter strings: write `${VAR}[..]`, `${VAR}:x`.
Hands-free review: `afplay file.mp4` (AppleScript to QuickTime is blocked by a permission prompt).

## Distribution lesson (episode 2)
A vertical file under 3 min becomes a Short on YouTube, and Shorts are recommended separately from
long-form: viewers of the landscape episode 1 were never candidates for the vertical episode 2 (reach ~20x
lower, on top of a Friday post and hype decay). Deliver landscape for the channel; the vertical is for X/TikTok.

## Thumbnails with gpt-image-2 (`thumbnails/`)
- `prompt_swap_text.txt`: replace the title on an existing thumbnail, everything else identical. Pad the 16:9
  file to 3:2 (mirror the bottom strip) so the model keeps the geometry; request n=2 and keep the output whose
  pixels match the input outside the text band (mean abs diff ~2-4); about half the outputs recompose silently.
  Paste only the text band back onto the original for a pixel-exact result.
- `prompt_add_text_in_reference_style.txt`: add a title to a video frame in the style of a reference thumbnail
  (image 2). Same n=2 + diff check.
- `prompt_outpaint_sides_and_text.txt` then `prompt_reframe_tighter.txt`: a vertical frame whose subject does not
  fit 16:9. The model ALWAYS repaints when it extends a frame (three prompt variants, ~0.73x re-render each time), so
  accept the repaint, ask it to re-frame its own output tighter, then widen the 3:2 result to 16:9 by scaling to
  1080x720 and mirroring + blurring 100 px per side. Cropping 3:2 to 16:9 always cuts the title or the feet.
- `prompt_pencil_painting_two_robots.txt`: two robots side by side in the style of a reference drawing (image 1 =
  style + character A, image 2 = product photo of character B, robots called "robot A/B", "faithful tracing").
  Came out accurate on the first try. Same widening trick. Lifting the model's text as a layer onto another
  image fails on textured paper (grain gets into the mask); render text with the model in one go instead.
- Always ask for 2-3 outputs; `curl` to `/v1/images/edits` with `model=gpt-image-2 size=1536x1024 quality=high`.
