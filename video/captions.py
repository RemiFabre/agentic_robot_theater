"""Cut the filmed clip and burn speaker captions for the robot's lines.

Timing: each line WAV is cross-correlated with the film audio (where it plays), then ElevenLabs
STT word timestamps on the WAV give phrase boundaries. Captions are PIL PNG overlays (this
ffmpeg has no subtitles filter).

Usage: uv run video/captions.py --video clip.mp4 --scene scenes/<name> --out ~/Videos/<name>
         [--start 4 --end 54] [--speaker "REACHY MINI"] [--font-size 58]
Writes: <out>/skit_cut.mp4, <out>/skit_captioned.mp4, <out>/skit_captions.srt, <out>/timing.json
"""
import argparse, json, os, re, subprocess
import numpy as np, soundfile as sf
from scipy.signal import fftconvolve, butter, sosfilt
from PIL import Image, ImageDraw, ImageFont
from elevenlabs.client import ElevenLabs

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True); ap.add_argument("--scene", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--start", type=float, default=0); ap.add_argument("--end", type=float, default=None)
ap.add_argument("--speaker", default="REACHY MINI"); ap.add_argument("--font-size", type=int, default=58)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
CUT, OUT, TMP = f"{a.out}/skit_cut.mp4", f"{a.out}/skit_captioned.mp4", f"{a.out}/_cut16k.wav"
beats = [b for b in json.load(open(f"{a.scene}/scene.json")) if b.get("text")]

# 1. cut
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a.start)] + (["-to", str(a.end)] if a.end else []) + \
      ["-i", a.video, "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", CUT]
subprocess.run(cmd, check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", CUT, "-ar", "16000", "-ac", "1", TMP], check=True)
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", CUT], capture_output=True, text=True).stdout
W, H = map(int, probe.strip().split("\n")[0].split(",")[:2])

# 2. align each line in the film
vid, sr = sf.read(TMP, dtype="float32"); sos = butter(4, [300, 3400], btype="band", fs=sr, output="sos")
prep = lambda x: (lambda y: y / (np.abs(y).max() + 1e-9))(sosfilt(sos, x))
V = prep(vid); timing = {}
for b in beats:
    w, s2 = sf.read(f"{a.scene}/audio/{b['id']}.wav", dtype="float32"); assert s2 == sr
    c = fftconvolve(V, prep(w)[::-1], mode="valid"); e = np.sqrt(fftconvolve(V**2, np.ones(len(w)), mode="valid")) + 1e-6
    nc = c / e; i = int(np.argmax(nc)); mask = np.ones_like(nc, bool); mask[max(0, i-sr):i+sr] = False
    timing[b["id"]] = {"start": i / sr, "score": float(nc[i]), "runner_up": float(nc[mask].max())}
    print(f"{b['id']}: at {i/sr:.2f}s (peak {nc[i]:.1f} vs {nc[mask].max():.1f})")

# 3. phrase chunks from STT word times
stt = ElevenLabs(); caps = []
clean = lambda t: re.sub(r"\[[^\]]*\]", "", t).strip()
for b in beats:
    text = clean(b["text"]); chunks = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    r = stt.speech_to_text.convert(file=open(f"{a.scene}/audio/{b['id']}.wav", "rb"), model_id="scribe_v1", language_code="en", timestamps_granularity="word", tag_audio_events=False)
    words = [(w.start, w.end) for w in r.words if getattr(w, "type", "word") == "word"]
    n_script = len(text.split()); n_stt = len(words); k = 0
    for ch in chunks:  # map script word span -> STT word span (proportional if counts differ)
        i0, i1 = k, k + len(ch.split()); k = i1
        j0 = round(i0 * n_stt / n_script); j1 = max(j0 + 1, round(i1 * n_stt / n_script))
        t0 = timing[b["id"]]["start"]
        caps.append([t0 + words[j0][0], t0 + words[min(j1, n_stt) - 1][1], ch])
caps.sort()
for i in range(len(caps) - 1): caps[i][1] = min(caps[i + 1][0] - 0.05, caps[i][1] + 0.4)
caps[-1][1] += 0.5
json.dump({"lines": timing, "captions": caps}, open(f"{a.out}/timing.json", "w"), indent=1)
srt_t = lambda s: f"{int(s//3600):02d}:{int(s%3600//60):02d}:{s%60:06.3f}".replace(".", ",")
with open(f"{a.out}/skit_captions.srt", "w") as f:
    for i, (s, e, t) in enumerate(caps, 1): f.write(f"{i}\n{srt_t(s)} --> {srt_t(e)}\n{a.speaker.title()}: {t}\n\n")

# 4. render + burn
def render(text, idx):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    fm, ft = ImageFont.truetype(FONT, a.font_size), ImageFont.truetype(FONT, a.font_size // 2)
    lines, cur = [], ""
    for wd in text.split():
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=fm) > W * 0.8 and cur: lines.append(cur); cur = wd
        else: cur = t
    lines.append(cur); lh = int(a.font_size * 1.2); bh = 40 + len(lines) * lh; y = H - 90 - bh
    bw = max(max(d.textlength(l, font=fm) for l in lines), d.textlength(a.speaker, font=ft)) + 80; bx = (W - bw) / 2
    d.rounded_rectangle([bx, y, bx + bw, y + bh], radius=18, fill=(0, 0, 0, 150))
    d.text((W / 2, y + 22), a.speaker, font=ft, fill=(255, 196, 60, 255), anchor="mm")
    for i, l in enumerate(lines):
        d.text((W / 2, y + 40 + i * lh + lh / 2), l, font=fm, fill="white", anchor="mm", stroke_width=3, stroke_fill="black")
    p = f"{a.out}/_cap_{idx:02d}.png"; img.save(p); return p
pngs = [render(t, i) for i, (_, _, t) in enumerate(caps)]
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", CUT]; fc = ""; prev = "[0:v]"
for i, (s, e, _) in enumerate(caps):
    cmd += ["-i", pngs[i]]; outl = f"[v{i}]" if i < len(caps) - 1 else "[vout]"
    fc += f"{prev}[{i+1}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'{outl};"; prev = outl
cmd += ["-filter_complex", fc.rstrip(";"), "-map", "[vout]", "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "copy", "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True)
for p in pngs + [TMP]: os.remove(p)
for s, e, t in caps: print(f"{s:6.2f}-{e:6.2f}  {t}")
print("wrote", OUT)
