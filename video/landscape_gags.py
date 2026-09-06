"""build_landscape.py + typewriter ending: freeze on Reachy's last pose (FREEZE2 in source time), music keeps playing,
TEXT types in with a key click per character and a bell at the end, then fade. Usage:
python3 scripts/build_landscape_v2.py <boom.mp3> <out.mp4> <boom_db> <freeze_src_s> <freeze2_src_s> "<text>" """
import subprocess, sys, os, shutil
from PIL import Image, ImageDraw, ImageFont
IN = "03_captioned_clean.mp4"; A = "music/E04_pixar_confession.mp3"; B = "music_switch/T1_adventure_kickoff.mp3"; B_OFF = 1.027846
BOOM, OUT = sys.argv[1], sys.argv[2]; BOOM_DB = float(sys.argv[3]); FREEZE = float(sys.argv[4]); FREEZE2 = float(sys.argv[5]); TEXT = sys.argv[6]
CLICK, DING = "landscape/type_click.mp3", "landscape/type_ding.mp3"
PIVOT = 40.9; HOLD = 0.8; N = 3; GAP = HOLD * N; RESUME = FREEZE + GAP
PRE, CPS, POST = 0.2, 0.055, 1.5            # pause before typing, seconds per character, hold after the bell
FPS = 30; T2 = FREEZE2 + GAP               # output time of the ending freeze
n = len(TEXT); TYPE_END = PRE + n * CPS; ENDING = PRE + n * CPS + POST; END = T2 + ENDING
FADE_AT = END - 0.6; MFADE = min(END - 1.0, 64.0)  # T1 runs out at ~65 s of output time
THR = 0.02; DB = -12; BDB = -11.5
# --- typing frames
fd = "landscape/typing_frames"; shutil.rmtree(fd, ignore_errors=True); os.makedirs(fd)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(FREEZE2), "-i", IN, "-frames:v", "1", "-vf", "scale=-2:1080,pad=1920:1080:(ow-iw)/2:0:black", f"{fd}/base.png"], check=True)
base = Image.open(f"{fd}/base.png").convert("RGB"); W, H = base.size
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", 66)
full_w = ImageDraw.Draw(base).textlength(TEXT, font=font); x0 = (W - full_w) / 2; y = 930
nf = int(round(ENDING * FPS))
for i in range(nf):
    t = i / FPS; k = 0 if t < PRE else min(n, int((t - PRE) / CPS) + 1)
    im = base.copy(); d = ImageDraw.Draw(im)
    s = TEXT[:k]; cursor = "_" if (int(t / 0.4) % 2 == 0) else ""
    d.text((x0, y), s + cursor, font=font, fill="white", stroke_width=4, stroke_fill="black")
    im.save(f"{fd}/{i:04d}.png")
# --- ffmpeg
words = [f"landscape/words_{k}.png" for k in range(1, N + 1)]
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", IN, "-i", A, "-ss", str(B_OFF), "-i", B, "-i", BOOM]
for w in words: cmd += ["-loop", "1", "-t", str(HOLD), "-i", w]
cmd += ["-framerate", str(FPS), "-i", f"{fd}/%04d.png", "-i", CLICK, "-i", DING]      # inputs 7, 8, 9
V = "scale=-2:1080,pad=1920:1080:(ow-iw)/2:0:black,fps=30,format=yuv420p,setsar=1"
fc = f"[0:v]{V},split=2[va][vb];[va]trim=0:{FREEZE},setpts=PTS-STARTPTS[p1];[vb]trim={FREEZE}:{FREEZE2},setpts=PTS-STARTPTS[p3];"
for k in range(N): fc += f"[{4+k}:v]fps=30,format=yuv420p,setsar=1[w{k}];"
fc += "[7:v]fps=30,format=yuv420p,setsar=1[typ];"
fc += "[p1]" + "".join(f"[w{k}]" for k in range(N)) + f"[p3][typ]concat=n={N+3}:v=1:a=0,fade=t=out:st={FADE_AT}:d=0.6[vout];"
fc += (f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[a1][a2];[a1]atrim=0:{FREEZE},asetpts=PTS-STARTPTS[d1];"
       f"[a2]atrim={FREEZE}:{FREEZE2},asetpts=PTS-STARTPTS[d3];aevalsrc=0:d={GAP}:s=48000,aformat=sample_rates=48000:channel_layouts=stereo[sil];"
       f"[d1][sil][d3]concat=n=3:v=0:a=1,apad=whole_dur={END},asplit=2[dlg][key];")
fc += (f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{PIVOT},volume={DB}dB,afade=t=in:st=0:d=1.5,afade=t=out:st={PIVOT-0.25}:d=0.25,apad=whole_dur={END}[ma];"
       f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={BDB}dB,afade=t=in:st=0:d=0.12,adelay={int(RESUME*1000)}|{int(RESUME*1000)},apad=whole_dur={END},atrim=0:{END},afade=t=out:st={MFADE}:d=1.0[mb];"
       f"[ma][mb]amix=inputs=2:normalize=0:duration=first[mus];[mus][key]sidechaincompress=threshold={THR}:ratio=5:attack=40:release=700:makeup=1[ducked];")
fc += f"[3:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={BOOM_DB}dB,asplit={N}" + "".join(f"[b{k}]" for k in range(N)) + ";"
for k in range(N):
    t = int((FREEZE + k * HOLD) * 1000); fc += f"[b{k}]adelay={t}|{t},apad=whole_dur={END}[bd{k}];"
fc += "".join(f"[bd{k}]" for k in range(N)) + f"amix=inputs={N}:normalize=0:duration=first[booms];"
fc += f"[8:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-10dB,asplit={n}" + "".join(f"[c{i}]" for i in range(n)) + ";"
for i in range(n):
    t = int((T2 + PRE + i * CPS) * 1000); fc += f"[c{i}]adelay={t}|{t},apad=whole_dur={END}[cd{i}];"
fc += "".join(f"[cd{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:duration=first[clicks];"
td = int((T2 + TYPE_END + 0.1) * 1000); fc += f"[9:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-12dB,adelay={td}|{td},apad=whole_dur={END}[ding];"
fc += "[dlg][ducked][booms][clicks][ding]amix=inputs=5:normalize=0:duration=first[aout]"
cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]", "-t", str(END), "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True); print("wrote", OUT, "END", round(END, 2), "typing", round(T2 + PRE, 2), "->", round(T2 + TYPE_END, 2))
