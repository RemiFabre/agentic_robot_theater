"""Render every spoken beat of a scene to <scene_dir>/audio/<id>.wav (16 kHz mono, silences trimmed).

Usage: uv run voice/render_lines.py scenes/<name> --voice <voice_id> [--only id1,id2] [--speed 1.0]
"""
import argparse, json, os, subprocess
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings

TRIM = ("silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.1,"
        "silenceremove=stop_periods=-1:stop_threshold=-40dB:stop_silence=0.6,"
        "areverse,silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.2,areverse")

ap = argparse.ArgumentParser()
ap.add_argument("scene_dir"); ap.add_argument("--voice", required=True)
ap.add_argument("--only", default=""); ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--model", default="eleven_v3"); ap.add_argument("--play", action="store_true")
a = ap.parse_args()
only = set(filter(None, a.only.split(",")))
out_dir = os.path.join(a.scene_dir, "audio"); os.makedirs(out_dir, exist_ok=True)
c = ElevenLabs()
for b in json.load(open(os.path.join(a.scene_dir, "scene.json"))):
    if not b.get("text") or (only and b["id"] not in only): continue
    audio = c.text_to_speech.convert(voice_id=a.voice, text=b["text"], model_id=a.model, output_format="mp3_44100_128",
        voice_settings=VoiceSettings(stability=0.35, similarity_boost=0.8, style=0.6, speed=a.speed))
    raw = os.path.join(out_dir, f"{b['id']}_raw.mp3"); wav = os.path.join(out_dir, f"{b['id']}.wav")
    open(raw, "wb").write(b"".join(audio))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", TRIM, "-ar", "16000", "-ac", "1", wav], check=True)
    print("ok", wav)
    if a.play: subprocess.run(["afplay", wav])
