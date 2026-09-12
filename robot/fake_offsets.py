"""Placeholder head offsets for skit_duo.py, until the wobbler harness produces the real ones.

Writes scenes/<scene>/audio/offsets/<beat_id>.<version>.json in the FORMATS.md layout (arrays t, pitch, yaw,
roll in radians, x, y, z in mm, hop_ms) from each spoken beat's wav: a gentle 2 Hz nod (0.06 rad on pitch)
only where the wav is loud, plus a smaller yaw sway so the two robots do not look identical.

    python robot/fake_offsets.py scenes/couple_fight --version v5 [--force]

Existing files are kept unless --force (so real harness output is never overwritten by mistake). Each
file carries "placeholder": true so the player can say which it is using.
"""
import argparse, json, math, os, sys, wave

import numpy as np

HOP_MS = 20
NOD_HZ, NOD_RAD = 2.0, 0.06
SWAY_HZ, SWAY_RAD = 0.7, 0.03


def load_mono(path):
    with wave.open(path, "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    dt = {1: np.int8, 2: np.int16, 4: np.int32}[sw]
    x = np.frombuffer(raw, dtype=dt).astype(np.float32) / float(2 ** (8 * sw - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def offsets_for(path, version):
    x, sr = load_mono(path)
    hop = int(sr * HOP_MS / 1000)
    n_hops = int(math.ceil(len(x) / hop))
    rms = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n_hops)])
    db = 20 * np.log10(rms + 1e-9)
    gate = (db > -35.0).astype(np.float32)
    # 100 ms attack / 200 ms release so the nod fades instead of switching
    env = np.zeros(n_hops, dtype=np.float32)
    for i in range(n_hops):
        a = 0.35 if gate[i] > env[i - 1] else 0.1
        env[i] = env[i - 1] + a * (gate[i] - env[i - 1]) if i else gate[i]
    t = np.arange(n_hops) * HOP_MS / 1000.0
    pitch = NOD_RAD * env * np.sin(2 * math.pi * NOD_HZ * t)
    yaw = SWAY_RAD * env * np.sin(2 * math.pi * SWAY_HZ * t)
    roll = 0.3 * SWAY_RAD * env * np.sin(2 * math.pi * SWAY_HZ * t + 1.0)
    z = 3.0 * env * np.sin(2 * math.pi * NOD_HZ * t + 0.5)  # mm
    f = lambda a: [round(float(v), 5) for v in a]
    return {"version": version, "placeholder": True, "emotion": "neutral", "energy": 1.0,
            "hop_ms": HOP_MS, "sample_rate": sr,
            "t": f(t), "pitch": f(pitch), "yaw": f(yaw), "roll": f(roll),
            "x": f(np.zeros(n_hops)), "y": f(np.zeros(n_hops)), "z": f(z)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir")
    ap.add_argument("--version", default="v5")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    beats = json.load(open(os.path.join(a.scene_dir, "scene.json")))
    out_dir = os.path.join(a.scene_dir, "audio", "offsets")
    os.makedirs(out_dir, exist_ok=True)
    for b in beats:
        if not b.get("text"):
            continue
        wav = os.path.join(a.scene_dir, "audio", f"{b['id']}.wav")
        out = os.path.join(out_dir, f"{b['id']}.{a.version}.json")
        if not os.path.exists(wav):
            print(f"skip {b['id']}: no wav"); continue
        if os.path.exists(out) and not a.force:
            print(f"keep {out} (exists)"); continue
        json.dump(offsets_for(wav, a.version), open(out, "w"))
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
