#!/usr/bin/env python
"""Headless probes for the encounter film: what the shipped policies do with head / body intents,
and how the duck falls and gets up. Prints a table; --still renders one frame of the set.

    /Users/remi/microduck/.venv-mjlab/bin/python /Users/remi/microduck/notes/reachy-encounter/probe.py [--still] [--only head|peck|fall]
"""
import argparse, math, sys
from pathlib import Path
import numpy as np, mujoco, imageio

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckfilm as F

HERE = Path(__file__).resolve().parent


def fresh(reachy=True):
    m, d = F.build_scene((640, 360), reachy_at=(0.0, 0.0, math.pi) if reachy else None)
    du = F.Duck(m, d, "duck_")
    du.make_bam()
    du.spawn(-0.6, 0.0, 0.0)
    rm = F.Reachy(m, d) if reachy else None
    mujoco.mj_forward(m, d)
    du.bam.last_ts = d.time
    return m, d, du, rm


def run(m, d, du, rm, seconds, fn, log=None):
    n = int(round(seconds / F.CDT))
    for k in range(n):
        t = k * F.CDT
        fn(du, t)
        du.control_tick(t)
        for _ in range(F.DECIMATION):
            du.physics_substep()
            if rm is not None:
                rm.step(F.DT, t)
            mujoco.mj_step(m, d)
        du.after_step(t)
        if log is not None:
            log(du, t)


def probe_head():
    print("\n== head slots: commanded delta -> measured joint delta (rad), on the stand net and on the walk net ==")
    names = ["neck_pitch", "head_pitch", "head_yaw", "head_roll"]
    for net_name, twist in (("stand", (0, 0, 0)), ("walk fwd0.3", (0.3, 0, 0))):
        for i, nm in enumerate(names):
            row = []
            for amp in (-1.0, -0.6, -0.3, 0.3, 0.6, 1.0):
                if nm == "head_roll" and abs(amp) > 0.35:
                    continue
                m, d, du, rm = fresh(reachy=False)
                du.limp_fall = False
                meas = []

                def fn(du, t, amp=amp, i=i):
                    du.twist[:] = twist if t > 0.5 else (0, 0, 0)
                    du.head[:] = 0
                    if t > 1.0:
                        du.head[i] = amp

                def lg(du, t):
                    if t > 2.2:
                        meas.append(du.q()[F.HEAD_IDX[i]] - F.HOME[F.HEAD_IDX[i]])
                run(m, d, du, rm, 3.0, fn, lg)
                row.append(f"{amp:+.1f}->{np.mean(meas):+.2f}{' FALL' if du.fell_at is not None else ''}")
            print(f"  {net_name:12s} {nm:11s} " + "  ".join(row))


def probe_body():
    print("\n== body pose slots on the stand net (z, roll, pitch): commanded -> trunk height / roll / pitch ==")
    for i, nm, amps in ((0, "z", (-0.04, -0.02, 0.02)), (1, "roll", (-0.3, 0.3)), (2, "pitch", (-0.4, -0.2, 0.2, 0.4))):
        row = []
        for amp in amps:
            m, d, du, rm = fresh(reachy=False)
            du.limp_fall = False
            meas = []

            def fn(du, t, amp=amp, i=i):
                du.body[:] = 0
                if t > 1.0:
                    du.body[i] = amp

            def lg(du, t):
                if t > 2.2:
                    g = du.grav()
                    meas.append((du.pos()[2], math.atan2(g[1], -g[2]), math.atan2(-g[0], -g[2])))
            run(m, d, du, rm, 3.0, fn, lg)
            z, r, p = np.mean(meas, axis=0)
            row.append(f"{amp:+.2f}->z{z:.3f} r{math.degrees(r):+.0f} p{math.degrees(p):+.0f}{' FALL' if du.fell_at is not None else ''}")
        print(f"  {nm:6s} " + "  ".join(row))


def probe_peck():
    print("\n== peck: neck dip pulses through the command block (stand net), beak tip travel ==")
    for neck, hp, lean, dur in ((-0.6, 0.0, 0.0, 0.3), (-0.9, 0.0, 0.0, 0.3), (-0.9, -0.4, 0.0, 0.3), (-0.9, 0.0, 0.3, 0.3), (-1.2, 0.0, 0.3, 0.4), (-0.9, 0.0, 0.0, 0.15)):
        m, d, du, rm = fresh(reachy=False)
        du.limp_fall = False
        beak = []

        def fn(du, t):
            ph = (t - 1.0) % 1.0
            on = t > 1.0 and ph < dur
            du.head[:] = (neck if on else 0.0, hp if on else 0.0, 0, 0)
            du.body[:] = 0
            du.body[2] = lean if on else 0.0

        def lg(du, t):
            beak.append(du.beak_pos())
        run(m, d, du, rm, 4.0, fn, lg)
        b = np.array(beak)
        rest = b[35:48].mean(axis=0)
        low = b[50:].min(axis=0)
        fwd = b[50:, 0].max()
        print(f"  neck {neck:+.1f} head_pitch {hp:+.1f} lean {lean:+.1f} pulse {dur:.2f}s: beak rest z {rest[2]:.3f} x {rest[0]:+.3f}; "
              f"lowest z {low[2]:.3f} (dip {rest[2]-low[2]:.3f}), furthest x {fwd:+.3f} (reach {fwd-rest[0]:+.3f})"
              f"{' FALL' if du.fell_at is not None else ''}")


def probe_fall():
    print("\n== scared-fall options (from a stand, 1 s in) and what follows ==")
    opts = {
        "relax 1.5s then runtime limp-fall ramp": lambda du, t: setattr(du, "relax", 1.0 < t < 2.5),
        "spin wz 2.3 for 2 s": lambda du, t: du.twist.__setitem__(slice(None), (0, 0, 2.3) if 1.0 < t < 3.0 else (0, 0, 0)),
        "back burst (-0.8,0,0) 1 s": lambda du, t: du.twist.__setitem__(slice(None), (-0.8, 0, 0) if 1.0 < t < 2.0 else (0, 0, 0)),
        "back burst (-0.6,0,0) + head up 1.0, 1 s": lambda du, t: (du.twist.__setitem__(slice(None), (-0.6, 0, 0) if 1.0 < t < 2.0 else (0, 0, 0)),
                                                                   du.head.__setitem__(slice(None), (1.0, 0, 0, 0) if 1.0 < t < 2.0 else (0, 0, 0, 0))),
        "roulade skill 2.5 s": lambda du, t: setattr(du, "skill", "roulade" if 1.0 < t < 3.5 else None),
        "relax 1.5 s then sitstand rise 3 s": lambda du, t: (setattr(du, "relax", 1.0 < t < 2.5), setattr(du, "limp_fall", False),
                                                            setattr(du, "skill", "rise" if 2.5 <= t < 5.5 else None)),
    }
    for name, fn in opts.items():
        m, d, du, rm = fresh(reachy=False)
        hist = []

        def lg(du, t):
            hist.append((t, du.pos()[2], du.grav()[2], du.net, du.upright()))
        run(m, d, du, rm, 7.0, fn, lg)
        fell = du.fell_at
        lowest = min(h[1] for h in hist)
        nets = []
        for h in hist:
            if not nets or nets[-1][1] != h[3]:
                nets.append((round(h[0], 2), h[3]))
        up_end = du.upright() and du.fell_at is not None
        g = du.grav()
        print(f"  {name:42s} fell@{fell if fell is None else round(fell,2)}  lowest trunk z {lowest:.3f}  end grav {np.round(g,2)} "
              f"upright at end: {du.upright()}  nets: {nets[:8]}")


def still():
    m, d = F.build_scene((1280, 720), reachy_at=(0.0, 0.0, math.pi))
    du = F.Duck(m, d, "duck_")
    du.make_bam()
    du.spawn(-0.45, 0.0, 0.0)
    rm = F.Reachy(m, d)
    mujoco.mj_forward(m, d)
    rm.step(1.0, 0.0)
    mujoco.mj_forward(m, d)
    r = mujoco.Renderer(m, 720, 1280)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    frames = []
    for az in (150, 210, 90):
        cam.lookat[:] = [-0.2, 0, 0.12]
        cam.distance, cam.azimuth, cam.elevation = 1.1, az, -14
        r.update_scene(d, camera=cam)
        frames.append(r.render().copy())
    # awake pose
    rm.pose(tau=0.01, **F.Reachy.AWAKE)
    rm.step(1.0, 0.0)
    mujoco.mj_forward(m, d)
    cam.azimuth = 150
    r.update_scene(d, camera=cam)
    frames.append(r.render().copy())
    sheet = np.concatenate([np.concatenate(frames[:2], axis=1), np.concatenate(frames[2:], axis=1)], axis=0)
    out = HERE / "still_set.png"
    imageio.imwrite(out, sheet)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    if a.still:
        still()
        sys.exit()
    todo = a.only.split(",") if a.only else ["head", "body", "peck", "fall"]
    for k in todo:
        {"head": probe_head, "body": probe_body, "peck": probe_peck, "fall": probe_fall}[k]()
