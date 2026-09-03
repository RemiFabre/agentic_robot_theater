"""Generate instrumental music beds with ElevenLabs (one request at a time: concurrency limit).

Usage: uv run video/gen_music.py --out DIR [--len 52] "name1: prompt one" "name2: prompt two" ...
Tip: always end prompts with "under dialogue, instrumental only"; offer 3-10 named identities.
"""
import argparse, time
from elevenlabs.client import ElevenLabs

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--len", type=float, default=52)
ap.add_argument("prompts", nargs="+"); a = ap.parse_args(); c = ElevenLabs()
import os; os.makedirs(a.out, exist_ok=True)
for i, p in enumerate(a.prompts):
    name, _, prompt = p.partition(":") if ":" in p else (f"track{i+1}", "", p)
    for attempt in range(3):
        try:
            data = b"".join(c.music.compose(prompt=prompt.strip(), music_length_ms=int(a.len * 1000), force_instrumental=True, output_format="mp3_44100_128"))
            open(f"{a.out}/{name.strip()}.mp3", "wb").write(data); print("ok", name.strip()); break
        except Exception as e:
            print("retry", name, str(e)[-80:]); time.sleep(3)
