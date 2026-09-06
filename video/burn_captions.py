"""Burn captions from captions.json onto 01_trimmed.mp4 -> 02_captioned.mp4.
Same look as episode 1 (skit_captioned.mp4): Arial Bold 58, white + 3px black stroke, amber speaker tag 30px,
black 150-alpha rounded box, bottom 90px. PIL PNG overlays + ffmpeg overlay (this ffmpeg has no subtitles/drawtext)."""
import json, os, subprocess
from PIL import Image, ImageDraw, ImageFont
IN, OUT = "01_trimmed.mp4", "02_captioned.mp4"
probe = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",IN],capture_output=True,text=True).stdout
W, H = map(int, probe.strip().split("\n")[0].split(",")[:2])  # decoded (rotation applied) size, 1080x1920 for this vertical episode
BOTTOM = 160  # ep1 (landscape) used 90; raised a bit for a vertical frame so phone UI overlays do not cover it
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
caps = json.load(open("captions.json"))
def render(text, speaker, idx):
    img = Image.new("RGBA", (W, H), (0,0,0,0)); d = ImageDraw.Draw(img)
    f_main = ImageFont.truetype(FONT, 58); f_tag = ImageFont.truetype(FONT, 30)
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur+" "+w).strip()
        if d.textlength(t, font=f_main) > W*0.8 and cur: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    lh = 70; block_h = 40 + len(lines)*lh; y = H - BOTTOM - block_h
    tw = max(d.textlength(l, font=f_main) for l in lines); tagw = d.textlength(speaker, font=f_tag)
    bw = max(tw, tagw) + 80; bx = (W-bw)/2
    d.rounded_rectangle([bx, y, bx+bw, y+block_h], radius=18, fill=(0,0,0,150))
    d.text((W/2, y+22), speaker, font=f_tag, fill=(255,196,60,255), anchor="mm")
    for i, l in enumerate(lines):
        d.text((W/2, y+40+i*lh+lh/2), l, font=f_main, fill=(255,255,255,255), anchor="mm", stroke_width=3, stroke_fill=(0,0,0,255))
    p = f"samples/_cap_{idx:02d}.png"; img.save(p); return p
pngs = [render(c["text"], c["who"].upper(), i) for i, c in enumerate(caps)]
cmd = ["ffmpeg","-y","-loglevel","error","-i",IN]; fc, prev = "", "[0:v]"
for i, c in enumerate(caps):
    cmd += ["-i", pngs[i]]; outl = f"[v{i}]" if i < len(caps)-1 else "[vout]"
    fc += f"{prev}[{i+1}:v]overlay=0:0:enable='between(t,{c['start']:.3f},{c['end']:.3f})'{outl};"; prev = outl
cmd += ["-filter_complex", fc.rstrip(";"), "-map","[vout]","-map","0:a","-c:v","libx264","-crf","18","-preset","fast","-c:a","copy","-movflags","+faststart",OUT]
subprocess.run(cmd, check=True)
for p in pngs: os.remove(p)
print("wrote", OUT)
