"""Design a voice from a text brief (3 previews) or save a preview as a permanent voice.

  uv run voice/design_voice.py --desc "..." --text "sample line" [--play]   -> prints generated_voice_ids
  uv run voice/design_voice.py --save <generated_voice_id> --name "Name"     -> prints voice_id
"""
import argparse, base64, subprocess, os
from elevenlabs.client import ElevenLabs

ap = argparse.ArgumentParser()
ap.add_argument("--desc"); ap.add_argument("--text"); ap.add_argument("--play", action="store_true")
ap.add_argument("--save"); ap.add_argument("--name", default="Robot voice"); ap.add_argument("--out", default="out")
a = ap.parse_args(); c = ElevenLabs()
if a.save:
    v = c.text_to_voice.create(voice_name=a.name, voice_description=a.desc or a.name, generated_voice_id=a.save)
    print("voice_id", v.voice_id)
else:
    os.makedirs(a.out, exist_ok=True)
    r = c.text_to_voice.design(voice_description=a.desc, text=a.text, model_id="eleven_multilingual_ttv_v2")
    for i, p in enumerate(r.previews):
        path = f"{a.out}/design_{i}.mp3"; open(path, "wb").write(base64.b64decode(p.audio_base_64))
        print(i, p.generated_voice_id, path)
        if a.play: subprocess.run(["say", f"candidate {i}"]); subprocess.run(["afplay", path])
