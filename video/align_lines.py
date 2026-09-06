"""Align each ElevenLabs line WAV onto the video audio by normalised cross-correlation
of log-mel-ish envelopes (band energies), report start/end in video time."""
import json, sys, numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly, fftconvolve, stft

VIDEO = "samples/audio48k.wav"
SCENE = "/Users/remi/reachy_mini_apps/agentic_robot_theater/scenes/lake/audio"
LINES = ["hey", "talk", "bad_news", "excuse", "not_scared"]
WIN = {"hey": (0, 12), "talk": (4, 14), "bad_news": (8, 30), "excuse": (25, 50), "not_scared": (40, 63)}

def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(np.float32)
    if x.ndim > 1: x = x.mean(1)
    x /= (np.abs(x).max() + 1e-9)
    if sr != 16000:
        from math import gcd
        g = gcd(sr, 16000); x = resample_poly(x, 16000//g, sr//g)
    return x

def feat(x, hop=160):
    f, t, Z = stft(x, fs=16000, nperseg=512, noverlap=512-hop)
    P = np.abs(Z)**2
    bands = np.array_split(np.arange(len(f))[(f>=200)&(f<=4000)], 24)
    F = np.stack([np.log(P[b].sum(0)+1e-6) for b in bands])  # (24, T)
    F -= F.mean(1, keepdims=True); F /= (F.std(1, keepdims=True)+1e-6)
    return F

v = load(VIDEO); Fv = feat(v)
out = {}
for name in LINES:
    l = load(f"{SCENE}/{name}.wav")
    # trim leading/trailing silence of the line
    env = np.abs(l); thr = 0.02
    idx = np.where(env > thr)[0]; l = l[idx[0]:idx[-1]+1]
    Fl = feat(l)
    n = Fl.shape[1]
    # normalised cross-correlation over time via sliding windows
    T = Fv.shape[1]
    scores = np.zeros(T-n)
    Flc = Fl - Fl.mean(1, keepdims=True); Fln = np.linalg.norm(Flc)
    for k in range(24):
        scores += fftconvolve(Fv[k], Flc[k][::-1], mode="valid")[:T-n]
    # local norm of video window
    sq = (Fv**2).sum(0); win = np.convolve(sq, np.ones(n), mode="valid")[:T-n]
    scores /= (np.sqrt(win)*Fln + 1e-9)
    lo, hi = WIN[name]; sc = scores.copy(); sc[:int(lo*100)] = -9; sc[int(hi*100):] = -9
    best = int(np.argmax(sc)); s = best*0.01
    mask = np.ones_like(scores, bool); mask[max(0,best-300):best+300] = False
    runner = float(scores[mask].max())
    out[name] = {"start": round(s,3), "end": round(s+len(l)/16000,3), "dur": round(len(l)/16000,3),
                 "score": round(float(scores[best]),3), "runner_up": round(runner,3)}
    print(name, out[name])
json.dump(out, open("line_times.json","w"), indent=1)
