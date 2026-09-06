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
sys.path.insert(0, "/Users/remi/microduck/notes/emotions/motion/playdead")
import duckfilm as F  # noqa: E402
import lib as L  # noqa: E402
from pdduck3 import PDDuck3  # noqa: E402  (robot.poseJoints in simulation: head servos free, legs posed)

EMO = Path("/Users/remi/microduck/notes/emotions")
F.POLICIES["ground_pick"] = F.WS / "microduck/policies/alpha_ground_pick.onnx"
GP_PERIOD, GP_END = 4.0, 0.7          # robotd: phase += dt / 4 s, done at 0.7
SIZE = (1280, 720)
FPS = 25
# Three-quarter staging (Rémi): each actor faces the other turned 45 deg toward the camera, which sits on the -y side.
DUCK_AT, REACHY_AT = (0.0, 0.0, -math.pi / 4), (0.62, 0.0, math.pi + math.pi / 4)


class SceneDuck(PDDuck3):
    """The film duck plus the ground pick (phase-encoded twist, as robotd drives it) and the scripted joint pose."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gp_phase = None
        self.hold_home = False        # after `robot.init`: torque on, holding the home pose, no policy (until the second Start)

    def wake(self, t):
        """robot.init out of the dead pose / a relax: torque on everywhere, a 2 s ramp home, then hold."""
        self.pose_at, self.posing, self.stage2, self._stage2_done, self._pose_t0 = None, False, None, False, None
        self.off = []
        self.relax, self.soften, self._soften_t0 = False, False, None
        self.ramp = (t, 2.0, self.q())
        self.hold_home = True

    def control_tick(self, t):
        if self.hold_home and self.ramp is None and not self.relax:
            self.t = t
            self.net, self.kp = "hold", F.KP_STAND
            self.bam.model.actuator.kp = self.kp
            self.bam.q_target[:] = F.HOME
            self.jaw_open += 0.5 * (F.JAW_MAX * float(self.mouth) - self.jaw_open)
            return
        super().control_tick(t)

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
    wav = Path(wav)
    if not wav.is_absolute():                   # some PICK.json paths are relative to the emotions repo
        wav = EMO / wav
    return m, wav


def curious_pick():
    """Curious as shipped (roll only, two chirps at 0.6 / 1.2 s), from padd/src/expressions.rs."""
    r = L.ramp
    def fn(t):
        back = 1.0 - r(t - 2.1, 0.5)
        roll = 0.35 * r(t - 0.4, 0.35) if t < 1.0 else 0.35 + (-0.44 - 0.35) * r(t - 1.0, 0.35)
        return dict(head_roll=roll * back)
    return L.Motion("curious", "curious (Y)", 3.0, fn, quacks=[0.6, 1.2]), EMO / "sounds/robot/curious_a.wav"


PICK_NAMES = {"play_dead": "playdead"}


def pick_open():
    """The ground pick with the beak opening on the way down (Kind::Pick): mouth 1 from 0.1 s, shut at 0.75 s."""
    return L.Motion("pick", "ground pick, beak open on the way down", 3.0,
                    lambda t: dict(skill="ground_pick" if t < 2.9 else None, mouth=L.pulse(t, 0.1, 0.25, 0.4, 0.25))), None


def emotion(name):
    if name == "curious":
        return curious_pick()
    if name == "pick":
        return pick_open()
    if name == "mmh":
        mod_path = EMO / "motion/mmh/render_mmh.py"
        spec = importlib.util.spec_from_file_location("emo_mmh", mod_path); mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod); m, wav, _ = mod.pick(); return m, Path(wav)
    if name in ("laugh", "mock"):
        mod_path = EMO / "motion/laugh/laugh_v2.py"
        spec = importlib.util.spec_from_file_location("emo_laugh2", mod_path); mod = importlib.util.module_from_spec(spec)
        argv, sys.argv = sys.argv, [str(mod_path)]
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.argv = argv
        m, wav, _ = mod.pick() if name == "laugh" else mod.pick_mock()
        return m, Path(wav)
    if name == "yes_fast":
        m, _ = emotion("yes")
        return L.Motion("yes_fast", m.desc, m.total, m.fn, m.beats), EMO / "sounds/yes/yes_single__Y3_synth_wak.wav"
    p = load_pick(PICK_NAMES.get(name, name))
    if p is None:
        print(f"!! {name}: no pick yet, the duck holds still")
        return L.Motion(name, "(not designed yet)", 2.0, lambda t: {}), None
    m, wav = p
    if name == "excited":
        wav = EMO / "sounds/excited/excited_wag_pump__X1_synth_rise_climb.wav"     # Rémi's sound pick
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
    ap.add_argument("--mix-only", action="store_true", help="reuse the rendered silent video, only mix the audio")
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
    rig = F.Rig(m, SIZE, lookat=[0.3, 0.0, 0.13], distance=1.15, azimuth=90, elevation=-10)
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
        cues = [dict(b, at=0.0)] + list(b.get("duck_cues", []))
        for c in cues:
            tc = t0 + float(c.get("at", 0.0))
            if "duck" in c:
                mo, wav = emotion(c["duck"])
                events.append((tc, "express", mo))
                if wav:
                    audio.append((tc, wav))
                if c["duck"] == "play_dead":          # the dead pose: robot.poseJoints stages from the pick
                    pk = json.load(open(EMO / "motion/playdead/PICK.json"))
                    events.append((tc, "dead_pose", pk["pose_joints"]))
                need = max(need, tc - t0 + mo.total)
            elif "duck_skill" in c:
                events.append((tc, "skill", c["duck_skill"]))
                need = max(need, tc - t0 + {"ground_pick": 4.0, "sit_toggle": 2.5, "roulade": 1.5}.get(c["duck_skill"], 0.6))
            elif "duck_sound" in c:
                n, every = int(c.get("repeat", 1)), float(c.get("every", 0.45))
                for i in range(n):
                    audio.append((tc + i * every, L.BANK / c["duck_sound"] / f"{c['duck_sound']}_{'ae'[i % 2]}.wav"))
                    events.append((tc + i * every, "quack", None))
                need = max(need, tc - t0 + 0.5 + every * (n - 1))
            elif "duck_move" in c:
                events.append((tc, "move", (c["duck_move"], float(c.get("for", 1.0)))))
                need = max(need, tc - t0 + float(c.get("for", 1.0)))
            elif c.get("duck_init"):
                events.append((tc, "init", None))
                need = max(need, tc - t0 + 2.5)
            elif "duck_policy" in c:
                events.append((tc, "policy", bool(c["duck_policy"])))
                if c["duck_policy"]:
                    events.append((tc + 3.0, "face", None))     # once up, the preview turns the duck to face Reachy (Rémi's stick)
                need = max(need, tc - t0 + 0.5)
        if b.get("wait") == "key":
            need = max(need, 0.5)           # Rémi's ENTER: in the preview the duck already faces Reachy (turned during the lament)
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
    if a.mix_only and out.with_suffix(".silent.mp4").exists():
        return mix(out, audio, rows)
    strip = lambda s: re.sub(r"\[[^\]]*\]\s*", "", s).strip()
    silent = out.with_suffix(".silent.mp4")
    writer = imageio.get_writer(str(silent), fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=8,
                                output_params=["-crf", "20", "-movflags", "+faststart"])
    next_frame = 0.0
    express, express_t0 = None, 0.0
    skill_until, move_until, move = 0.0, 0.0, (0, 0, 0)
    standup = None
    quack_until = 0.0
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
            elif what == "dead_pose":
                st = arg
                du.time_offset = tt
                du.set_pose_joints(st[0]["at"], st[0]["targets"], st[0]["off"], st[0]["gain"], st[0]["ramp_s"])
                du.stage2 = (st[1]["at"], st[1]["targets"], st[1]["ramp_s"]) if len(st) > 1 else None
                du._stage2_done = False
            elif what == "init":
                standup = ("ramp", tt)
                beat_label = "duck: Start (init)"
            elif what == "policy":
                standup = ("rise", tt) if arg else None
                beat_label = "duck: Start (policy on)"
            elif what == "quack":
                quack_until = tt + 0.25
            elif what == "face":
                standup = ("turn", tt)
                beat_label = "Rémi: turn the duck"
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
        env_mouth = 1.0 if tt < quack_until else 0.0
        du.mouth = float(h["mouth"]) if h["mouth"] is not None else env_mouth
        if standup is not None:
            phase, ts = standup
            if phase == "ramp":
                du.wake(tt)
                standup = None
            elif phase == "rise" and tt >= ts:
                du.hold_home = False
                du.skill = "rise"
                standup = ("stand", tt + 2.5)
            elif phase == "stand" and tt >= ts:
                du.skill = None
                standup = None
            elif phase == "turn" and tt >= ts:
                du.skill = None
                b_ = F.wrap(du.bearing_to(rm.pos()) + math.pi / 4)      # three-quarter: Reachy 45 deg to the duck's left
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
            writer.append_data(np.asarray(img))
            next_frame += 1.0 / FPS
    writer.close()
    mix(out, audio, rows)


def mix(out, audio, rows):
    silent = out.with_suffix(".silent.mp4")
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
