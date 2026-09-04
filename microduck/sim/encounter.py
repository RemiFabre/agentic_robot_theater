#!/usr/bin/env python
"""Microduck meets Reachy Mini: the film (simulation, scripted intents only).

    /Users/remi/microduck/.venv-mjlab/bin/python /Users/remi/microduck/notes/reachy-encounter/encounter.py \
        [--out /Users/remi/microduck/notes/reachy-encounter/encounter.mp4] [--size 1280x720] [--seconds N] [--no-open] [--no-sound]

Story: Reachy Mini sleeps (an egg). The duck walks up, looks, circles, pecks it three times. Reachy wakes up
and says hello; the duck screams, collapses (motors off), gets back up (sit-stand net), and the two talk:
the duck in duck language, Reachy Mini in English.

Every duck motion is an intent the real robot accepts: twist, head deltas, body pose, mouth, relax, skills.
Sound: the duck's own voice bank (peck / inquire / alarm / chirp / coo) + animalese quacks for its lines;
Reachy Mini speaks through the local Kokoro TTS. `events.json` next to the mp4 lists everything with times,
so the real-robot replay can fire the same sounds on the robot's speaker.
"""
import argparse, hashlib, json, math, subprocess, sys, wave
from pathlib import Path

import imageio, mujoco, numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckfilm as F

HERE = Path(__file__).resolve().parent
SND_BANK = Path("/Users/remi/microduck/notes/comic-video/sounds/student_bank_7")
KOKORO = "/Users/remi/local-tts-lab/.venv/bin/kokoro-say"
REACHY_VOICE = "bf_emma"
SR = 22050

RM_POS = np.array([0.0, 0.0, 0.0])
DUCK_START = np.array([-1.15, 0.35])
PECK_DIST = 0.27          # trunk -> Reachy centre when pecking (beak rest 7 cm ahead, lunge +17 cm, Reachy radius 8 cm)
LOOK_DIST = 0.42
PECK = dict(pulse=0.35, lean=0.3, hp=-0.6, neck=0.0)


class Film:
    def __init__(self, size, render=True, sound=True):
        self.size, self.render_on = size, render
        self.m, self.d = F.build_scene(size, reachy_at=(RM_POS[0], RM_POS[1], math.pi))
        self.duck = F.Duck(self.m, self.d, "duck_")
        self.duck.make_bam()
        self.duck.spawn(DUCK_START[0], DUCK_START[1], 0.0)
        self.rm = F.Reachy(self.m, self.d)
        mujoco.mj_forward(self.m, self.d)
        self.rm.step(1.0, 0.0)
        mujoco.mj_forward(self.m, self.d)
        self.duck.bam.last_ts = self.d.time
        self.rig = F.Rig(self.m, size, lookat=[-0.5, 0.15, 0.12], distance=1.9, azimuth=150, elevation=-12)
        self.renderer = mujoco.Renderer(self.m, size[1], size[0]) if render else None
        self.overlay = F.Overlay(size)
        self.frames = []
        self.t = 0.0
        self.bubbles = []      # (t0, t1, who, text, scale)
        self.captions = []     # (t0, t1, text)
        self.post = []         # (t0, t1, fn(img, draw, tau))
        self.events = []       # sound design: dict(t, kind, ...)
        self.gaze_target = None
        self.gaze_pitch_bias = 0.0
        self.ctrl = None
        self.log = []
        self.slowmo = 1

    # --- bookkeeping -------------------------------------------------------------------------------------------
    def ev(self, kind, **kw):
        self.events.append(dict(t=round(self.t, 3), kind=kind, **kw))

    def say(self, who, text, dur, scale=1.0, sound=True):
        self.bubbles.append((self.t, self.t + dur, who, text, scale))
        if sound:
            self.ev("say", who=who, text=text, dur=dur)

    def caption(self, text, dur):
        self.captions = [(a, min(b, self.t), x) for (a, b, x) in self.captions]
        self.captions.append((self.t, self.t + dur, text))

    def fx(self, fn, dur):
        self.post.append((self.t, self.t + dur, fn))

    def mid(self):
        return 0.5 * (self.duck.pos() + self.rm.pos()) + [0, 0, 0.12]

    def two_shot(self, distance=1.15, elevation=-10, tau=1.4, side=None):
        """Camera on the side of the duck-Reachy line, both in frame (the side nearest the current camera)."""
        if side is None:
            v = self.rm.pos()[:2] - self.duck.pos()[:2]
            a0 = math.degrees(math.atan2(v[1], v[0]))
            cur = self.rig.cur["azimuth"]
            side = min((1, -1), key=lambda s_: abs(F.wrap(math.radians(a0 - 90 * s_ - cur))))

        def az():
            v = self.rm.pos()[:2] - self.duck.pos()[:2]
            a = math.degrees(math.atan2(v[1], v[0])) - 90 * side
            return a
        self.rig.shot(track=self.mid, distance=distance, elevation=elevation, tau=tau)
        self._az_fn = az

    # --- duck gaze through the command block ------------------------------------------------------------------
    def apply_gaze(self):
        tgt = self.gaze_target
        if tgt is None:
            return
        p = tgt() if callable(tgt) else np.asarray(tgt, float)
        hp = self.duck.head_pos()
        v = F.qrotinv(self.duck.quat().astype(float), p - hp)
        yaw = math.atan2(v[1], v[0])
        pitch = math.atan2(v[2], math.hypot(v[0], v[1]))
        self.duck.head[2] = float(np.clip(yaw, -1.0, 1.0))
        # neck only tracks downward (about half the command): command twice the wanted dip
        want = pitch + self.gaze_pitch_bias
        self.duck.head[0] = float(np.clip(2.0 * min(0.0, want), -1.0, 0.0))

    # --- main loop ----------------------------------------------------------------------------------------------
    def run(self, seconds, fn=None, until=None):
        """Advance the film. fn(tau) sets intents each control tick; until() stops early when true."""
        n = int(round(seconds / F.CDT))
        t0 = self.t
        for k in range(n):
            tau = self.t - t0
            if fn is not None:
                fn(tau)
            self.apply_gaze()
            self.duck.control_tick(self.t)
            for _ in range(F.DECIMATION):
                self.duck.physics_substep()
                self.rm.step(F.DT, self.t)
                mujoco.mj_step(self.m, self.d)
            self.duck.after_step(self.t)
            if hasattr(self, "_az_fn"):
                self.rig.tgt["azimuth"] = self._az_fn()
            every = max(1, round(1.0 / (F.FPS * F.CDT)))
            if self.slowmo > 1:
                for _ in range(self.slowmo // 2):
                    self.render_frame()
            elif k % every == 0:
                self.render_frame()
            self.t += F.CDT
            self.log.append((round(self.t, 2), self.duck.net, round(float(self.duck.grav()[2]), 2)))
            if until is not None and until():
                return True
        return False

    def render_frame(self):
        self.rig.step(1.0 / F.FPS)
        if not self.render_on:
            return
        self.renderer.update_scene(self.d, camera=self.rig.cam)
        img = Image.fromarray(self.renderer.render())
        draw = ImageDraw.Draw(img)
        t = self.t
        for (t0, t1, who, text, scale) in self.bubbles:
            if t0 <= t < t1:
                head = self.duck.head_pos() if who == "duck" else self.rm.head_pos() + [0, 0, 0.06]
                a = self.rig.project(head + [0, 0, 0.03])
                pop = 0.6 + 0.4 * min(1.0, (t - t0) / 0.12)
                side = "left" if a[0] > self.size[0] / 2 else "right"
                self.overlay.bubble(draw, text, a, side, pop=pop, scale=scale,
                                    font=F.FONT_COMIC if who == "duck" else F.FONT_CAPTION)
        for (t0, t1, text) in self.captions:
            if t0 <= t < t1:
                self.overlay.caption(draw, text)
        for (t0, t1, fn) in self.post:
            if t0 <= t < t1:
                img2 = fn(img, draw, t - t0)
                if img2 is not None:
                    img = img2
                    draw = ImageDraw.Draw(img)
        self.frames.append(np.asarray(img))

    # --- duck behaviours (closed loop, intents only) -----------------------------------------------------------
    def walk_to(self, target, stop, v=0.35, timeout=12.0, look=True, bob=0.25):
        target = np.asarray(target, float)
        du = self.duck

        def fn(tau):
            b = du.bearing_to(target)
            dist = du.dist_to(target)
            du.head[1] = -bob * 0.5 * (1 - math.cos(2 * math.pi * 1.6 * tau))     # curious head-bob while stepping
            if abs(b) > 0.35:
                du.twist[:] = (0.0, 0.0, 1.2 if b > 0 else -1.2)
            else:
                du.twist[:] = (v if dist > stop + 0.15 else 0.3, 0.0, float(np.clip(1.5 * b, -0.6, 0.6)))
        r = self.run(timeout, fn, until=lambda: du.dist_to(target) < stop)
        du.head[1] = 0.0
        return r

    def stand(self, seconds, fn=None):
        du = self.duck
        du.twist[:] = 0

        def f(tau):
            du.twist[:] = 0
            if fn is not None:
                fn(tau)
        return self.run(seconds, f)

    def orbit(self, center, seconds, direction=1, wz0=0.3):
        """Strafe sideways around `center` while facing it (walk net, sideways command + a yaw servo)."""
        center = np.asarray(center, float)
        du = self.duck

        def fn(tau):
            b = du.bearing_to(center)
            dist = du.dist_to(center)
            vx = 0.0
            if dist > LOOK_DIST + 0.12:
                vx = 0.3
            du.twist[:] = (vx, 0.5 * direction, float(np.clip(wz0 * direction + 1.6 * b, -0.9, 0.9)))
        return self.run(seconds, fn)

    def head_tilt(self, seconds, roll=0.3, pitch=0.0):
        du = self.duck

        def fn(tau):
            du.twist[:] = 0
            du.head[3] = roll * F.smooth(min(1.0, tau / 0.4))
            du.head[1] = pitch * F.smooth(min(1.0, tau / 0.4))
        self.run(seconds, fn)

    def peck(self, n=3, period=0.95, pulse=None, lean=None, hp=None, neck=None):
        du = self.duck
        fired = set()
        pulse = PECK["pulse"] if pulse is None else pulse
        lean = PECK["lean"] if lean is None else lean
        hp = PECK["hp"] if hp is None else hp
        neck = PECK["neck"] if neck is None else neck
        saved_gaze, self.gaze_target = self.gaze_target, None

        def fn(tau):
            du.twist[:] = 0
            k = int(tau // period)
            ph = tau - k * period
            on = ph < pulse and k < n
            du.body[2] = lean if on else 0.0
            du.head[1] = hp if on else 0.0
            du.head[0] = neck if on else 0.0
            if on and k not in fired:
                fired.add(k)
                self.ev("bank", tag="peck", at=self.t + 0.22, gain=1.0)
        self.run(n * period + 0.3, fn)
        du.body[:] = 0
        du.head[:] = 0
        self.gaze_target = saved_gaze


# ---------------------------------------------------------------------------------------------------------------
def big_text(film, text, color=(230, 30, 30), dur=0.9, jitter=True):
    def fn(img, draw, tau):
        s = 0.6 + 0.4 * min(1.0, tau / 0.08)
        cx, cy = film.rig.project(film.duck.head_pos() + [0, 0, 0.12])
        if jitter:
            cx += 6 * math.sin(60 * tau)
            cy += 6 * math.cos(47 * tau)
        film.overlay.big(draw, text, (cx, cy - 60 * film.overlay.s), color=color, scale=s)
    film.fx(fn, dur)


def story(film, seconds_cap=None):
    du, rm = film.duck, film.rm
    film.caption("MuJoCo simulation. The duck is driven only through the commands the real robot accepts.", 5.0)
    film.gaze_target = lambda: rm.head_pos()
    film.rig.shot(track=film.mid, distance=1.9, azimuth=150, elevation=-12, tau=2.5)

    # 1. approach: a curious duck, head on the egg all along
    film.ev("bank", tag="chirp", at=film.t + 0.6, gain=0.5)
    film.walk_to(RM_POS, stop=LOOK_DIST, v=0.4, timeout=10)
    film.rig.shot(track=film.mid, distance=1.25, elevation=-11, tau=2.5)
    film.stand(0.6)
    film.ev("bank", tag="inquire", at=film.t + 0.1, gain=0.8)
    film.say("duck", "?", 1.4, scale=1.3, sound=False)
    film.head_tilt(1.4, roll=0.3)
    film.head_tilt(1.0, roll=-0.3)

    # 2. circle it
    film.rig.shot(track=film.mid, distance=1.35, elevation=-14, tau=2.5)
    film.orbit(RM_POS, 7.0, direction=-1)      # clockwise: the duck passes between Reachy and the camera
    film.stand(0.5)
    film.ev("bank", tag="inquire", at=film.t + 0.1, gain=0.8)
    film.say("duck", "??", 1.2, scale=1.3, sound=False)
    film.head_tilt(1.2, roll=-0.3, pitch=0.3)
    du.head[3] = 0
    du.head[1] = 0

    # 3. get close and peck
    film.walk_to(RM_POS, stop=PECK_DIST, v=0.3, timeout=6)
    film.two_shot(distance=0.95, elevation=-8, tau=2.0)
    film.stand(0.5)
    film.caption("A peck = body pitch +0.3 and head pitch -0.6 for 0.35 s (the stand policy does the rest).", 4.0)
    film.peck(3)
    film.stand(0.4)
    if getattr(film, "stop_after_peck", False):
        return

    # 4. Reachy wakes up
    film.ev("chime", at=film.t + 0.1)
    rm.pose(tau=0.18, ant=1.0)
    film.stand(0.35)
    rm.pose(tau=0.5, z=1.0, pitch=0.0)
    film.stand(0.6)
    rm.look_at(du.head_pos())
    film.stand(0.4)
    film.say("reachy", "Oh. Hello.", 1.5)
    rm.talking = True
    film.stand(0.35)

    # 5. scream, collapse
    film.ev("bank", tag="alarm", at=film.t, gain=1.0)
    film.say("duck", "QUAAACK!", 1.0, scale=1.2, sound=False)
    big_text(film, "!!!", dur=0.6)
    film.gaze_target = None
    film.slowmo = 1

    def scream(tau):
        du.twist[:] = 0
        du.mouth = 1.0
        du.head[:] = (0.0, 1.0, 0.0, 0.0)          # head thrown back
        du.body[2] = -0.25                          # recoil
    film.run(0.45, scream)
    rm.talking = False

    def jump_back(tau):
        du.twist[:] = (-0.8, 0.0, 0.0)
        du.mouth = 1.0
        du.head[:] = (0.0, 1.0, 0.0, 0.0)
        du.body[:] = 0
    film.run(1.1, jump_back)
    du.twist[:] = 0
    du.body[:] = 0
    du.head[:] = 0
    du.relax = True
    du.limp_fall = False
    film.rig.shot(track=lambda: du.pos() + [0.1, 0, 0.05], distance=1.0, elevation=-14, tau=1.0)
    film.run(0.7, lambda tau: setattr(du, "mouth", max(0.0, 1.0 - tau)))
    film.caption("Scared = motors off (robot.relax). The runtime does the same when it detects a fall.", 3.5)
    film.run(1.3)
    rm.look_at(du.head_pos())
    film.say("reachy", "Sorry. Did I scare you?", 2.2)
    rm.talking = True
    film.run(1.6)
    rm.talking = False

    # 6. get up: the sit-stand network rises from the heap
    du.relax = False
    du.skill = "rise"
    film.caption("Getting up = the sit-to-stand policy (robot.do sit_toggle), from wherever it lies.", 3.5)
    film.run(3.2, until=lambda: du.upright() and film.t > 0)  # rise until upright
    du.skill = None
    film.stand(0.8)

    # shake it off, then look at Reachy
    def shake(tau):
        du.twist[:] = 0
        du.head[2] = 0.6 * math.sin(2 * math.pi * 3.0 * tau) * (1 - tau / 0.9)
    film.run(0.9, shake)
    du.head[:] = 0
    film.gaze_target = lambda: rm.head_pos()
    film.two_shot(distance=1.1, elevation=-9, tau=1.6)
    film.run(1.6, lambda tau: du.twist.__setitem__(slice(None), (-0.35, 0.0, 0.22)))   # a wary step back
    film.stand(0.6)

    # 7. dialogue
    film.say("duck", "Quack quack quack?!", 1.8)
    film.stand(0.9, lambda tau: du.head.__setitem__(3, 0.28 * F.smooth(tau / 0.4)))
    film.stand(0.9, lambda tau: du.head.__setitem__(3, 0.28 * (1 - F.smooth(tau / 0.4))))
    rm.talking = True
    film.say("reachy", "I am Reachy Mini. I was sleeping.", 2.6)
    film.stand(2.6)
    rm.talking = False
    film.gaze_pitch_bias = -0.5           # sheepish: look down
    film.ev("bank", tag="coo", at=film.t + 0.2, gain=0.8)
    film.say("duck", "quack...", 1.4, sound=False)
    film.stand(1.5)
    rm.talking = True
    film.say("reachy", "You pecked me. Three times.", 2.3)
    film.stand(2.3)
    rm.talking = False
    film.say("duck", "...quack.", 1.2, scale=0.85)
    film.stand(1.3)
    film.gaze_pitch_bias = 0.0
    rm.talking = True
    film.say("reachy", "It's okay. I'm a robot too. Nice legs, by the way.", 3.4)
    film.stand(3.4)
    rm.talking = False
    film.ev("bank", tag="greet", at=film.t + 0.1, gain=0.9)
    film.say("duck", "QUACK!", 1.0, scale=1.2, sound=False)

    def happy(tau):
        du.twist[:] = 0
        du.head[1] = 0.8 * math.sin(2 * math.pi * 2.2 * tau) ** 2
    film.run(1.0, happy)
    du.head[1] = 0
    # show off the legs: a kick (a real robot skill)
    film.gaze_target = None
    du.head[:] = 0
    film.stand(0.3)
    du.skill = "kick_right"
    film.run(1.0)
    du.skill = None
    film.stand(0.3)
    film.gaze_target = lambda: rm.head_pos()
    rm.talking = True
    film.say("reachy", "Show-off.", 1.4)
    film.stand(1.5)
    rm.talking = False
    film.ev("bank", tag="wheee", at=film.t + 0.1, gain=0.7)
    film.say("duck", "Wheee!", 1.2, sound=False)
    film.rig.shot(track=film.mid, distance=1.6, elevation=-12, tau=2.5)
    if hasattr(film, "_az_fn"):
        del film._az_fn
    film.stand(2.5)


# ---------------------------------------------------------------------------------------------------------------
# Sound: the duck's bank, animalese for its lines, Kokoro for Reachy, a boot chime
# ---------------------------------------------------------------------------------------------------------------
def load_wav(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        n = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        if n > 1:
            x = x.reshape(-1, n).mean(axis=1)
    if sr != SR:
        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)), np.arange(len(x)), x).astype(np.float32)
    return x


def resample(buf, factor):
    n = max(8, int(len(buf) / factor))
    return np.interp(np.linspace(0, len(buf) - 1, n), np.arange(len(buf)), buf).astype(np.float32)


def bank(tag, variant):
    files = sorted((SND_BANK / tag).glob(f"{tag}_[a-z].wav")) or sorted((SND_BANK / tag).glob("*.wav"))
    if tag == "wheee":     # segmented ride: start + loop + end
        seg = lambda k: sorted((SND_BANK / tag).glob(f"wheee_{k}_*.wav"))[variant % 6]
        return np.concatenate([load_wav(seg("start")), load_wav(seg("loop")), load_wav(seg("loop")), load_wav(seg("end"))])
    return load_wav(files[variant % len(files)])


def animalese(text, rng):
    """Duck language: one whole chirp per syllable-ish unit, pitched by the letters; a question ends on an inquire."""
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    units = []
    for w in words:
        letters = [c for c in w.lower() if c.isalnum()]
        for i in range(0, max(1, len(letters)), 3):
            units.append(letters[i] if letters else "q")
        units.append(None)
    step = 1 / 5.5
    out = np.zeros(int(len(units) * step * SR) + SR, np.float32)
    voiced = [u for u in units if u is not None]
    vi = 0
    for k, c in enumerate(units):
        if c is None:
            continue
        vi += 1
        if vi == len(voiced) and "?" in text:
            g = bank("inquire", int(rng.integers(0, 9))).copy()
        else:
            g = bank("chirp", int(rng.integers(0, 7))).copy()
            g = resample(g, 1.0 + 0.12 * (((ord(c) * 2654435761) % 97) / 97.0 - 0.5))
        if "!" in text:
            g = resample(g, 1.08)
        a = max(8, len(g) // 20)
        g[:a] *= np.linspace(0, 1, a).astype(np.float32)
        g[-a:] *= np.linspace(1, 0, a).astype(np.float32)
        i = int(k * step * SR)
        n = min(len(g), len(out) - i)
        out[i:i + n] += g[:n]
    return out, len(units) * step


def chime():
    t = np.arange(int(0.9 * SR)) / SR
    x = np.zeros_like(t, dtype=np.float32)
    for k, (f0, t0) in enumerate(((523.25, 0.0), (659.25, 0.18), (783.99, 0.36))):
        env = np.exp(-4.5 * np.maximum(0, t - t0)) * (t >= t0)
        x += 0.25 * np.sin(2 * np.pi * f0 * (t - t0)) * env
    return x.astype(np.float32)


def kokoro(text):
    vdir = HERE / "voice"
    vdir.mkdir(exist_ok=True)
    out = vdir / (hashlib.md5((REACHY_VOICE + text).encode()).hexdigest()[:10] + ".wav")
    if not out.exists():
        subprocess.run(["bash", "-c", f"cd /Users/remi/local-tts-lab && PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/local-tts kokoro-daemon status >/dev/null 2>&1 || "
                        f"PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/local-tts kokoro-daemon start"], check=False)
        subprocess.run([KOKORO, "--lang", "en", "--voice", REACHY_VOICE, "--speed", "1.0", "--no-play", "--output", str(out), text],
                       env={"PYTORCH_ENABLE_MPS_FALLBACK": "1", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}, check=True)
    return load_wav(out)


def mix_sound(events, video_seconds, out_wav):
    rng = np.random.default_rng(7)
    mix = np.zeros(int((video_seconds + 1.0) * SR), np.float32)

    def put(x, t, gain=1.0):
        i = int(t * SR)
        n = min(len(x), len(mix) - i)
        if n > 0:
            mix[i:i + n] += x[:n] * gain
    used = {}
    for e in events:
        t = e.get("at", e["t"])
        if e["kind"] == "bank":
            v = used.get(e["tag"], 0)
            used[e["tag"]] = v + 1
            put(bank(e["tag"], v), t, e.get("gain", 1.0))
        elif e["kind"] == "chime":
            put(chime(), t, 0.9)
        elif e["kind"] == "say" and e["who"] == "duck":
            x, dur = animalese(e["text"], rng)
            cap = max(0.5, e["dur"] - 0.15)
            if dur > cap:
                x = resample(x, dur / cap)
            put(x, t + 0.05, 0.8)
        elif e["kind"] == "say" and e["who"] == "reachy":
            put(kokoro(e["text"]), t + 0.05, 0.9)
    peak = np.abs(mix).max()
    if peak > 0.95:
        mix *= 0.95 / peak
    with wave.open(str(out_wav), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "encounter.mp4"))
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-sound", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    size = tuple(int(x) for x in a.size.split("x"))
    film = Film(size, render=not a.no_render)
    if a.seconds:
        # cap: monkeypatch run to stop after the budget
        orig = film.run

        def run(seconds, fn=None, until=None):
            if film.t >= a.seconds:
                return True
            return orig(min(seconds, a.seconds - film.t), fn, until)
        film.run = run
    story(film)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    base = out.with_name(out.stem + "_base.mp4")
    if not a.no_render:
        imageio.mimwrite(str(base), film.frames, fps=F.FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=8,
                         output_params=["-profile:v", "high", "-level", "4.1", "-crf", "18", "-movflags", "+faststart"])
    json.dump(dict(fps=F.FPS, events=film.events), open(out.with_suffix(".events.json"), "w"), indent=1)
    dur = film.t
    print(f"film {dur:.1f} s, {len(film.frames)} frames, duck fell at {film.duck.fell_at}")
    nets = []
    for t, net, gz in film.log:
        if not nets or nets[-1][1] != net:
            nets.append((t, net))
    print("nets:", nets)
    if a.no_render:
        return
    if a.no_sound:
        base.replace(out)
    else:
        wav = out.with_suffix(".wav")
        mix_sound(film.events, dur, wav)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                        "-shortest", str(out)], check=True)
    print("wrote", out)
    if not a.no_open:
        subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
