"""Clean the dialogue track of the cut (wind/dlg_orig.wav -> wind/dlg_FINAL_v3.wav).
Wind/handling noise is sub-150 Hz rumble: steep high-pass where it lives, gentle elsewhere; +10/+9 dB makeup (opening is far-mic); limiter."""
import subprocess
HP220 = "highpass=f=220:poles=2,highpass=f=220:poles=2"
HP160 = "highpass=f=160:poles=2,highpass=f=160:poles=2"
XF = 0.4
# (start, end, filter) in cut time; consecutive segments overlap by XF and are crossfaded
segs = [
 (0.0,  8.5,  f"{HP220},afftdn=nr=15:nf=-35:tn=1,volume=10dB"),   # opening: wind + far mic
 (8.1,  22.5, f"{HP220},volume=9dB"),                              # gusts under the lake line
 (22.1, 40.7, f"{HP160},volume=9dB"),                              # clean; keep Remi's voice full
 (40.3, 44.3, f"{HP220},volume=9dB"),                              # pan handling rumble
 (43.9, None, f"{HP160},volume=9dB"),
]
n = len(segs); fc = f"[0:a]asplit={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
for i, (a, b, f) in enumerate(segs):
    tr = f"atrim={a}:{b}" if b else f"atrim={a}"
    fc += f"[s{i}]{f},{tr},asetpts=PTS-STARTPTS[p{i}];"
prev = "[p0]"
for i in range(1, n):
    out = f"[x{i}]" if i < n-1 else "[pre]"
    fc += f"{prev}[p{i}]acrossfade=d={XF}:c1=tri:c2=tri{out};"; prev = out
fc += "[pre]alimiter=limit=0.891:attack=5:release=50[out]"
subprocess.run(["ffmpeg","-y","-loglevel","error","-i","wind/dlg_orig.wav","-filter_complex",fc,"-map","[out]","-c:a","pcm_s16le","wind/dlg_FINAL_v3.wav"], check=True)
print("wrote wind/dlg_FINAL_v3.wav")
