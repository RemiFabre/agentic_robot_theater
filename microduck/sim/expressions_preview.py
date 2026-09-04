#!/usr/bin/env python
"""Preview of the two gamepad expressions (LB curious, RB peck) on the sim duck, same head intents as padd.

    /Users/remi/microduck/.venv-mjlab/bin/python /Users/remi/microduck/notes/reachy-encounter/expressions_preview.py [--no-open]
"""
import argparse, math, subprocess, sys
from pathlib import Path
import imageio, mujoco, numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckfilm as F

HERE = Path(__file__).resolve().parent
PECK_DOWN, PECK_PERIOD, PECK_COUNT, CURIOUS_LEG = 0.45, 0.85, 2, 0.7


def ramp(t, ln):
    x = min(1.0, max(0.0, t / ln))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def head_at(kind, t):
    """Exact port of padd/src/expressions.rs::head_at (neck, head_pitch, head_yaw, head_roll)."""
    if kind == "peck":
        if t >= PECK_PERIOD * PECK_COUNT:
            return None
        ph = t % PECK_PERIOD
        down = ramp(ph, 0.12) if ph < PECK_DOWN else 1.0 - ramp(ph - PECK_DOWN, 0.15)
        return (-1.5 * down, -0.6 * down, 0.0, 0.0)
    if t >= CURIOUS_LEG * 3:
        return None
    if t < CURIOUS_LEG:
        roll = 0.27 * ramp(t, 0.3)
    elif t < 2 * CURIOUS_LEG:
        roll = 0.27 - 0.54 * ramp(t - CURIOUS_LEG, 0.35)
    else:
        roll = -0.27 + 0.27 * ramp(t - 2 * CURIOUS_LEG, 0.3)
    dip = ramp(t, 0.4) * (1.0 - ramp(t - 2 * CURIOUS_LEG, 0.4))
    return (-0.5 * dip, 0.0, 0.0, roll)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--out", default=str(HERE / "expressions_preview.mp4"))
    a = ap.parse_args()
    size = (1280, 720)
    m, d = F.build_scene(size, reachy_at=(0.0, 0.0, math.pi))
    du = F.Duck(m, d, "duck_")
    du.make_bam()
    du.spawn(-0.32, 0.0, 0.0)
    rm = F.Reachy(m, d)
    mujoco.mj_forward(m, d)
    du.bam.last_ts = d.time
    r = mujoco.Renderer(m, size[1], size[0])
    cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = [-0.16, 0.0, 0.14]; cam.distance, cam.azimuth, cam.elevation = 0.9, 135, -10
    ov = F.Overlay(size)
    frames = []
    # timeline: stand 1 s, curious (LB), stand 1 s, peck (RB), stand 1 s, peck again while walking? no: peck standing, then curious again
    plan = [(1.0, None), (CURIOUS_LEG * 3 + 0.3, "curious"), (1.0, None), (PECK_PERIOD * PECK_COUNT + 0.4, "peck"), (1.2, None)]
    t = 0.0
    for dur, kind in plan:
        t0 = t
        n = int(round(dur / F.CDT))
        for k in range(n):
            tau = t - t0
            h = head_at(kind, tau) if kind else None
            du.head[:] = h if h else (0, 0, 0, 0)
            du.twist[:] = 0
            du.control_tick(t)
            for _ in range(F.DECIMATION):
                du.physics_substep(); rm.step(F.DT, t); mujoco.mj_step(m, d)
            du.after_step(t)
            if k % 2 == 0:
                r.update_scene(d, camera=cam)
                img = Image.fromarray(r.render()); draw = ImageDraw.Draw(img)
                label = {"curious": "LB  curious: tilt right, tilt left, small neck dip", "peck": "RB  peck: head forward twice (neck + head pitch, no body lean)"}.get(kind, "sticks idle")
                ov.caption(draw, label + f"\nhead intent  neck {du.head[0]:+.2f}  pitch {du.head[1]:+.2f}  roll {du.head[3]:+.2f}   (net: {du.net})")
                frames.append(np.asarray(img))
            t += F.CDT
    imageio.mimwrite(a.out, frames, fps=F.FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=8,
                     output_params=["-crf", "18", "-movflags", "+faststart"])
    print("wrote", a.out, f"{len(frames)/F.FPS:.1f} s, fell={du.fell_at}")
    if not a.no_open:
        subprocess.run(["open", a.out])


if __name__ == "__main__":
    main()
