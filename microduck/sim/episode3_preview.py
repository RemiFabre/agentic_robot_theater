#!/usr/bin/env python
"""Simulated preview of a two-robot scene (episode 3): the same scene.json the real player runs,
with the sim duck playing the duck cues and the kinematic Reachy Mini puppet playing the lines.

    /Users/remi/microduck/.venv-mjlab/bin/python microduck/sim/episode3_preview.py scenes/episode3 [--out FILE.mp4] [--until BEAT_ID]

Duck cues: `"duck": <emotion>` plays the emotion picked in the emotions repo
(/Users/remi/microduck/notes/emotions/motion/<emotion>/<emotion>.py::pick(), the same motion + wav
that ships on the pad); `"duck_skill"` runs the shipped skill policy (ground_pick / sit_toggle /
roulade / kicks); `"duck_sound"` plays a bank sound; `"duck_move"` a twist for `for` seconds.
`"wait": "key"` beats are Rémi's hand-piloted moments: the preview stands the duck up itself
(init ramp + sit-stand rise) and turns it to face Reachy. Reachy's lines are the rendered wavs
(head bob while talking) and its emotion names map to a few puppet gestures.
"""
import argparse, importlib.util, json, math, subprocess, sys, wave
from pathlib import Path

import imageio, mujoco, numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, "/Users/remi/microduck/notes/reachy-encounter")
sys.path.insert(0, "/Users/remi/microduck/notes/emotions/motion/episode3")
import duckfilm as F  # noqa: E402
import lib as L  # noqa: E402

EMO = Path("/Users/remi/microduck/notes/emotions")
F.POLICIES["ground_pick"] = F.WS / "microduck/policies/alpha_ground_pick.onnx"
GP_PERIOD, GP_END = 4.0, 0.7          # robotd: phase += dt / 4 s, done at 0.7
SIZE = (1280, 720)
FPS = 25
DUCK_AT, REACHY_AT = (0.0, 0.0, 0.0), (0.62, 0.0, math.pi)


class SceneDuck(L.Duck3):
    """The film duck plus the ground pick (phase-encoded twist, as robotd drives it)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gp_phase = None

    def _policy_tick(self):
        if self.skill == "ground_pick":
            if self.gp_phase is None:
                self.gp_phase = 0.0
            if self.gp_phase < GP_END:
                ang = 2 * math.pi * self.gp_phase
                c = np.zeros(13, np.float32)
                c[0], c[1] = math.cos(ang), math.sin(ang)
                self.net, self.kp = "ground_pick", F.KP_WALK
                self.command[:] = c
                self.bam.model.actuator.kp = self.kp
                act = F.policy("ground_pick")(self.obs())
                self.last_action = act
                self.bam.q_target[:] = F.HOME + act
                self.gp_phase += F.CDT / GP_PERIOD
                return
            self.skill = None
        else:
            self.gp_phase = None
        super()._policy_tick()


# ---------------------------------------------------------------------------------------------------------------
def load_pick(emotion):
    """(lib.Motion, wav Path) of the emotion's pick, from the emotions repo; None if not designed yet."""
    mod_path = EMO / "motion" / emotion / f"{emotion}.py"
    if not mod_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"emo_{emotion}", mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.argv, argv = [str(mod_path)], sys.argv      # the emotion scripts parse argv at import
    try:
        spec.loader.exec_module(mod)
        m, wav, _ = mod.pick()
    except Exception as e:                      # still being designed: no PICK.json yet
        print(f"!! {emotion}: pick() failed ({e})")
        return None
    finally:
        sys.argv = argv
    return m, Path(wav)


def curious_pick():
    """Curious as shipped (roll only, two chirps at 0.6 / 1.2 s), from padd/src/expressions.rs."""
    r = L.ramp
    def fn(t):
        back = 1.0 - r(t - 2.1, 0.5)
        roll = 0.35 * r(t - 0.4, 0.35) if t < 1.0 else 0.35 + (-0.44 - 0.35) * r(t - 1.0, 0.35)
        return dict(head_roll=roll * back)
    return L.Motion("curious", "curious (Y)", 3.0, fn, quacks=[0.6, 1.2]), EMO / "sounds/robot/curious_a.wav"


PICK_NAMES = {"closed_quack": "closed_quack", "play_dead": "playdead"}


def emotion(name):
    if name == "curious":
        return curious_pick()
    p = load_pick(PICK_NAMES.get(name, name))
    if p is None:
        print(f"!! {name}: no pick yet, the duck holds still")
        return L.Motion(name, "(not designed yet)", 2.0, lambda t: {}), None
    m, wav = p
    if name == "closed_quack":
        m = L.Motion(m.name, m.desc, m.total, lambda t, f=m.fn: dict(f(t) or {}, mouth=0.0), m.beats)
    return m, wav


def wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


# Reachy puppet gestures by move name (crude stand-ins for the recorded moves).
def reachy_gesture(name):
    n = name.rstrip("0123456789")
    if n in ("reprimand", "no", "displeased", "contempt", "irritated", "frustrated"):
        return dict(pitch=0.15, yaw=-0.5, ant=0.6)
    if n in ("anxiety", "scared", "fear", "uncomfortable", "uncertain"):
        return dict(pitch=0.25, yaw=0.3, ant=0.3)
    if n in ("downcast", "lonely", "sad", "resigned"):
        return dict(pitch=0.6, yaw=0.4, z=0.6, ant=0.1)
    if n in ("amazed", "surprised", "enthusiastic", "relief", "cheerful"):
        return dict(pitch=-0.25, yaw=0.0, z=1.0, ant=1.0)
    if n in ("thoughtful", "attentive", "inquiring", "loving", "calming", "understanding"):
        return dict(pitch=0.05, yaw=0.25, ant=0.8)
    return dict(pitch=0.0, yaw=0.0, z=1.0, ant=1.0)


# ---------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--until", default=None)
    ap.add_argument("--start-delay", type=float, default=1.0)
    a = ap.parse_args()
    scene = Path(a.scene_dir)
    beats = json.load(open(scene / "scene.json"))
    out = Path(a.out or scene / "preview_sim.mp4")

    m, d = F.build_scene(SIZE, reachy_at=REACHY_AT, reachy_mobile=False)
    du = SceneDuck(m, d, "duck_")
    du.make_bam()
    du.spawn(*DUCK_AT)
    mujoco.mj_forward(m, d)
    du.bam.last_ts = d.time
    rm = F.Reachy(m, d)
    rm.pose(tau=0.3, **F.Reachy.AWAKE)
    rig = F.Rig(m, SIZE, lookat=[0.3, 0.0, 0.13], distance=1.15, azimuth=118, elevation=-10)
    ov = F.Overlay(SIZE)
    r = mujoco.Renderer(m, SIZE[1], SIZE[0])

    # --- the timeline: a list of events (t, what) built beat by beat ---------------------------------------
    t = a.start_delay
    events, audio, rows = [], [], []
    for b in beats:
        if a.until and b["id"] == a.until:
            break
        t += b.get("pre", 0.0)
        t0 = t
        need = 0.0
        label = b["id"]
        if "duck" in b:
            mo, wav = emotion(b["duck"])
            events.append((t0, "express", mo))
            if wav:
                audio.append((t0, wav))
            need = mo.total
        elif "duck_skill" in b:
            events.append((t0, "skill", b["duck_skill"]))
            need = {"ground_pick": 4.0, "sit_toggle": 2.5, "roulade": 1.5}.get(b["duck_skill"], 0.6)
        elif "duck_sound" in b:
            audio.append((t0, L.BANK / b["duck_sound"] / f"{b['duck_sound']}_a.wav"))
            need = 0.5
        elif "duck_move" in b:
            events.append((t0, "move", (b["duck_move"], float(b.get("for", 1.0)))))
            need = float(b.get("for", 1.0))
        if b.get("wait") == "key":
            events.append((t0, "standup", None))
            need = max(need, 7.0)           # the preview stands the duck up itself: ramp 1 s, rise 2.5 s, turn
        say = 0.0
        if b.get("text"):
            wav = scene / "audio" / f"{b['id']}.wav"
            say = wav_len(wav) + b.get("tail", 0.3)
            audio.append((t0, wav))
            events.append((t0, "say", (b["text"], wav_len(wav))))
        if b.get("emotions"):
            events.append((t0, "gesture", b["emotions"][0]))
        length = max(b.get("hold", 0.0), need, say, 0.3)
        rows.append((round(t0, 1), b["id"], round(length, 1), b.get("text", ""), b.get("note", "")))
        t = t0 + length + b.get("gap", 0.0)
    total = t + 1.5
    print(f"{len(rows)} beats, {total:.1f} s")
    for row in rows:
        print("  ", row)

    # --- run --------------------------------------------------------------------------------------------------
    import re
    strip = lambda s: re.sub(r"\[[^\]]*\]\s*", "", s).strip()
    frames = []
    next_frame = 0.0
    express, express_t0 = None, 0.0
    skill_until, move_until, move = 0.0, 0.0, (0, 0, 0)
    standup = None
    caption, caption_until = "", 0.0
    beat_label = ""
    ev = sorted(events, key=lambda e: e[0])
    n = int(round(total / F.CDT))
    for k in range(n):
        tt = k * F.CDT
        while ev and ev[0][0] <= tt:
            _, what, arg = ev.pop(0)
            if what == "express":
                express, express_t0 = arg, tt
                beat_label = f"duck: {arg.name}"
            elif what == "skill":
                du.skill = arg
                skill_until = tt + {"ground_pick": 3.0, "roulade": 1.6}.get(arg, 0.6)
                beat_label = f"duck: {arg}"
            elif what == "move":
                move, move_until = tuple(arg[0]), tt + arg[1]
            elif what == "standup":
                standup = ("ramp", tt)
                beat_label = "Rémi: Start, turn the duck"
            elif what == "say":
                caption, caption_until = strip(arg[0]), tt + arg[1] + 0.5
                rm.talking = True
                talk_until = tt + arg[1]
                beat_label = "Reachy"
            elif what == "gesture":
                rm.pose(tau=0.5, **reachy_gesture(arg))
        if rm.talking and tt >= talk_until:
            rm.talking = False
        # the duck's intents this tick
        h = dict(L.DEFAULT)
        if express is not None:
            te = tt - express_t0
            if te < express.total:
                h.update(express.fn(te) or {})
            else:
                express = None
        du.head[:] = (h["neck"], h["head_pitch"], h["head_yaw"], h["head_roll"])
        du.body[:] = 0
        du.body[0], du.body[1], du.body[2] = h["body_z"], h["body_roll"], h["body_pitch"]
        du.twist[:] = move if tt < move_until else h["twist"]
        if express is not None and h["skill"] is not None:
            du.skill = h["skill"]
        elif tt >= skill_until and du.skill in ("kick_left", "kick_right", "roulade", "sit", "rise"):
            du.skill = None
        du.soften = bool(h["soften"])
        if h["relax"]:
            du.relax = True
        env_mouth = 0.0
        du.mouth = float(h["mouth"]) if h["mouth"] is not None else env_mouth
        if standup is not None:
            phase, ts = standup
            if phase == "ramp":
                du.relax, du.soften, du._soften_t0 = False, False, None
                du.ramp = (tt, 1.0, du.q())
                standup = ("rise", tt + 1.2)
            elif phase == "rise" and tt >= ts:
                du.skill = "rise"
                standup = ("turn", tt + 2.5)
            elif phase == "turn" and tt >= ts:
                du.skill = None
                b_ = du.bearing_to(rm.pos())
                if abs(b_) > 0.15 and tt < ts + 4.0:
                    du.twist[:] = (0, 0, 1.2 * np.sign(b_))
                else:
                    standup = None
        L.step(m, d, du, tt)
        rm.step(F.CDT, tt)
        rig.step(F.CDT)
        if tt >= next_frame - 1e-9:
            r.update_scene(d, camera=rig.cam)
            img = Image.fromarray(r.render())
            dr = ImageDraw.Draw(img)
            if tt < caption_until and caption:
                ov.caption(dr, wrap(caption, 60))
            dr.text((16, 12), f"{tt:5.1f} s   {beat_label}   (duck net: {du.net})", font=ov.font(F.FONT_CAPTION, 26 * ov.s),
                    fill="white", stroke_width=2, stroke_fill="black")
            frames.append(np.asarray(img))
            next_frame += 1.0 / FPS
    silent = out.with_suffix(".silent.mp4")
    imageio.mimwrite(str(silent), frames, fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=8,
                     output_params=["-crf", "20", "-movflags", "+faststart"])
    # audio mix
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(silent)]
    parts = []
    for i, (ta, wav) in enumerate(audio):
        cmd += ["-i", str(wav)]
        parts.append(f"[{i + 1}:a]aresample=48000,adelay={int(ta * 1000)}|{int(ta * 1000)}[s{i}]")
    mixed = "".join(f"[s{i}]" for i in range(len(audio)))
    parts.append(f"{mixed}amix=inputs={len(audio)}:normalize=0[a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)]
    subprocess.run(cmd, check=True)
    silent.unlink()
    print("wrote", out)
    json.dump([dict(t=r_[0], id=r_[1], length=r_[2], text=r_[3], note=r_[4]) for r_ in rows], open(out.with_suffix(".beats.json"), "w"), indent=1)


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return "\n".join(lines)


if __name__ == "__main__":
    main()
