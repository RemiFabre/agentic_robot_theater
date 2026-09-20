#!/usr/bin/env python
"""Offscreen MuJoCo preview of a two-Reachy-Mini scene (couple_fight), head motion from wobbler offset files.

    /Users/remi/microduck/.venv-mjlab/bin/python robot/render_duo.py scenes/couple_fight --wobbler v5 \
        [--out scenes/couple_fight/preview_v5.mp4] [--until BEAT_ID] [--fake-offsets] [--still 3.0]
    /Users/remi/microduck/.venv-mjlab/bin/python robot/render_duo.py scenes/couple_fight --side-by-side v0,v5

Python: the mjlab venv above (mujoco 3.10, imageio, PIL, numpy). ffmpeg on the PATH for the audio mix.

What it does
- Two kinematic Reachy Mini puppets built from the real MJCF meshes (body + head + antennas, the Stewart
  rods dropped): the head is a 6-DOF chain (x y z slides, yaw pitch roll hinges) around the neutral head
  frame, plus a body yaw hinge and the two antenna hinges. qpos is written directly, mj_forward, render.
  Loretta stands on the left, the husband on the right, each turned 45 deg toward the camera (three quarters).
- Per beat (scene.json): the speaker replays its `emotions` chain (recorded moves of the HF emotions library,
  head 4x4 + antennas + body_yaw at 50 Hz), the other robot replays `listener_emotions` or breathes slowly.
  Beat length = max(hold, say_at + wav + tail, emotion chain (cut at `cap`), 0.3) then `gap`, like skit.py.
- While a line plays, the speaker's head pose is composed with the wobbler offsets of the chosen version:
  `audio/offsets/<beat_id>.<version>.json` (FORMATS.md: t, pitch, yaw, roll in rad, x, y, z in mm).
  Missing file: the line plays without wobble (warned). `--fake-offsets`: a 2 Hz nod, 0.06 rad, only where
  the wav is loud, to test the pipeline end to end.
- Output: 25 fps, 1280x720 (2560x720 side by side), line wavs mixed at their beat times, a caption strip with
  the speaker, the wobbler version and the line (tags stripped). `--still T` writes one PNG at t = T s.
- `--audio-fallback DIR`: beats whose wav is missing borrow the wavs of DIR (in order), to test before the
  voice renders exist.
"""
import argparse, glob, json, math, re, subprocess, sys, time, wave
from pathlib import Path

import imageio, mujoco, numpy as np
from PIL import Image, ImageDraw, ImageFont

REACHY_XML = Path("/Users/remi/reachy_mini_apps/reachy_mini/src/reachy_mini/descriptions/reachy_mini/mjcf/reachy_mini.xml")
EMO_GLOB = "/Users/remi/.cache/huggingface/hub/datasets--pollen-robotics--reachy-mini-emotions-library/snapshots/*"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
SIZE = (1280, 720)
FPS = 25
EMOTION_CAP_S = 20.0
HEAD_Z = 0.1496                       # neutral head frame height above the base (the MJCF "head" site at qpos0)
# Staging: Loretta left, husband right, 0.52 m apart, each facing the other, turned FACE_TURN toward the camera (-y side).
FACE_TURN = math.radians(38)
ACTORS = {
    "loretta": dict(x=-0.26, y=0.0, yaw=-FACE_TURN, label="Loretta", color=(255, 150, 120)),
    "husband": dict(x=0.26, y=0.0, yaw=math.pi + FACE_TURN, label="Husband", color=(140, 200, 255)),
}
# Off-screen voices (no puppet): the line plays, the caption shows the name, both robots listen.
OFFSCREEN = {
    "larry": dict(label="Larry", color=(255, 225, 120)),
}
CAMERA = dict(lookat=[0.0, 0.0, 0.15], distance=0.82, azimuth=90, elevation=-8)
TAU_MOVE, TAU_REST = 0.06, 0.5        # pose easing: tracking a recorded move / returning to neutral


# ---------------------------------------------------------------------------------------------------------------
# Puppets from the real MJCF
# ---------------------------------------------------------------------------------------------------------------
def quat_of(mat):
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(mat, float).reshape(9))
    return q


def yaw_quat(yaw):
    return [math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)]


class Real:
    """The compiled reachy_mini.xml at qpos0, to copy its meshes, materials and visual geoms."""
    def __init__(self):
        self.spec = mujoco.MjSpec.from_file(str(REACHY_XML))
        self.m = self.spec.compile()
        self.d = mujoco.MjData(self.m)
        mujoco.mj_forward(self.m, self.d)
        self.assets = REACHY_XML.parent / self.spec.meshdir

    def ancestors(self, b):
        out = []
        while b > 0:
            out.append(self.m.body(b).name)
            b = self.m.body_parentid[b]
        return out

    def geoms_of(self, body_name):
        b = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, body_name)
        return [g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] == b and self.m.geom_group[g] == 2]


def copy_assets(spec, real):
    spec.meshdir = str(real.assets)
    for me in real.spec.meshes:
        spec.add_mesh(name=me.name, file=me.file, scale=me.scale)
    for ma in real.spec.materials:
        spec.add_material(name=ma.name, rgba=ma.rgba, specular=ma.specular, shininess=ma.shininess, reflectance=ma.reflectance)


def _copy_geom(body, real, g, pos, quat):
    """Add the compiled geom g (mesh) to body at (pos, quat), undoing MuJoCo's mesh recentering (it is redone at compile)."""
    m = real.m
    mid = m.geom_dataid[g]
    mq_inv = m.mesh_quat[mid] * [1, -1, -1, -1]
    q = np.zeros(4)
    mujoco.mju_mulQuat(q, np.asarray(quat, float), mq_inv)
    off = np.zeros(3)
    mujoco.mju_rotVecQuat(off, m.mesh_pos[mid], q)
    body.add_geom(type=mujoco.mjtGeom.mjGEOM_MESH, meshname=m.mesh(mid).name,
                  material=m.material(m.geom_matid[g]).name if m.geom_matid[g] >= 0 else "",
                  pos=np.asarray(pos, float) - off, quat=q, contype=0, conaffinity=0, group=2)


def add_reachy(spec, real, prefix, x, y, yaw):
    """A kinematic Reachy Mini: base (foot) -> body yaw hinge -> 6-DOF head -> antenna hinges. Returns joint names."""
    m, d = real.m, real.d
    base = spec.worldbody.add_body(name=prefix + "base", pos=[x, y, 0.0], quat=yaw_quat(yaw))
    for g in real.geoms_of("body_foot_3dprint"):
        _copy_geom(base, real, g, m.geom_pos[g], m.geom_quat[g])
    bd = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "body_down_3dprint")
    trunk = base.add_body(name=prefix + "trunk", pos=m.body_pos[bd], quat=m.body_quat[bd])
    trunk.add_joint(name=prefix + "body_yaw", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 0, 1], range=[-2.79, 2.79])
    for g in real.geoms_of("body_down_3dprint"):
        _copy_geom(trunk, real, g, m.geom_pos[g], m.geom_quat[g])
    # the head: its frame is the neutral head frame (identity orientation, HEAD_Z up), expressed in the base frame;
    # the trunk frame is the base yawed by -90 deg, so the head hangs off the trunk with the inverse of that
    tq = m.body_quat[bd]
    tq_inv = np.array([tq[0], -tq[1], -tq[2], -tq[3]])
    hp = np.zeros(3)
    mujoco.mju_rotVecQuat(hp, np.array([0, 0, HEAD_Z]) - m.body_pos[bd], tq_inv)
    head = trunk.add_body(name=prefix + "head", pos=hp, quat=tq_inv)
    for n, ax in (("x", [1, 0, 0]), ("y", [0, 1, 0]), ("z", [0, 0, 1])):
        head.add_joint(name=f"{prefix}head_{n}", type=mujoco.mjtJoint.mjJNT_SLIDE, axis=ax, range=[-0.1, 0.1])
    for n, ax in (("yaw", [0, 0, 1]), ("pitch", [0, 1, 0]), ("roll", [1, 0, 0])):
        head.add_joint(name=f"{prefix}head_{n}", type=mujoco.mjtJoint.mjJNT_HINGE, axis=ax, range=[-3.0, 3.0])
    head_origin = np.array([0, 0, HEAD_Z])
    xl = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "xl_330")
    for g in range(m.ngeom):
        if m.geom_bodyid[g] == xl and m.geom_group[g] == 2:
            _copy_geom(head, real, g, d.geom_xpos[g] - head_origin, quat_of(d.geom_xmat[g]))
    for side, bname in (("right", "dc15_a01_horn_dummy_7"), ("left", "dc15_a01_horn_dummy_8")):
        b = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, bname)
        ant = head.add_body(name=f"{prefix}ant_{side}", pos=d.xpos[b] - head_origin, quat=quat_of(d.xmat[b]))
        ant.add_joint(name=f"{prefix}ant_{side}", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 0, 1])
        for g in real.geoms_of(bname):
            _copy_geom(ant, real, g, m.geom_pos[g], m.geom_quat[g])
    # a dark neck column hides the missing Stewart platform between the trunk and the head
    head.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.022, 0.045, 0], pos=[0, 0, -0.03],
                  rgba=[0.12, 0.12, 0.13, 1], contype=0, conaffinity=0, group=2)


class Puppet:
    """Writes a head pose (x y z m, roll pitch yaw rad), antennas (l, r) and body yaw into qpos."""
    def __init__(self, m, d, prefix):
        self.m, self.d = m, d
        j = lambda n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, prefix + n)]
        self.q_pose = [j("head_x"), j("head_y"), j("head_z"), j("head_roll"), j("head_pitch"), j("head_yaw")]
        self.q_ant = [j("ant_left"), j("ant_right")]
        self.q_body = j("body_yaw")
        self.headb = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, prefix + "head")

    def set(self, pose6, antennas=(0.0, 0.0), body_yaw=0.0):
        for a, v in zip(self.q_pose, pose6):
            self.d.qpos[a] = v
        self.d.qpos[self.q_ant[0]], self.d.qpos[self.q_ant[1]] = antennas
        self.d.qpos[self.q_body] = body_yaw

    def head_pos(self):
        return self.d.xpos[self.headb].copy()


def build_scene(size=SIZE):
    real = Real()
    spec = mujoco.MjSpec()
    spec.compiler.degree = False
    spec.visual.global_.offwidth, spec.visual.global_.offheight = size
    spec.visual.headlight.diffuse, spec.visual.headlight.ambient = [0.45, 0.45, 0.45], [0.4, 0.4, 0.4]
    spec.visual.headlight.specular = [0.1, 0.1, 0.1]
    spec.visual.quality.shadowsize = 4096
    spec.visual.map.shadowclip = 1.0
    spec.add_texture(name="sky", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX, builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT,
                     rgb1=[0.55, 0.62, 0.72], rgb2=[0.92, 0.94, 0.97], width=512, height=3072)
    spec.worldbody.add_light(name="sun", pos=[0.3, -1.2, 2.5], dir=[-0.1, 0.45, -1], type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
                             castshadow=True, diffuse=[0.6, 0.6, 0.6])
    spec.add_texture(name="floor", type=mujoco.mjtTexture.mjTEXTURE_2D, builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                     rgb1=[0.62, 0.6, 0.58], rgb2=[0.55, 0.53, 0.51], mark=mujoco.mjtMark.mjMARK_NONE, width=300, height=300)
    spec.add_material(name="floor", texrepeat=[4, 4], texuniform=True, reflectance=0.04).textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = "floor"
    spec.worldbody.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[0, 0, 0.05], material="floor")
    copy_assets(spec, real)
    for name, a in ACTORS.items():
        add_reachy(spec, real, name + "_", a["x"], a["y"], a["yaw"])
    m = spec.compile()
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    return m, d, {name: Puppet(m, d, name + "_") for name in ACTORS}


# ---------------------------------------------------------------------------------------------------------------
# Motion sources: recorded moves, wobbler offsets
# ---------------------------------------------------------------------------------------------------------------
class Track:
    """Sampled 9-vector track: pose6 (x y z m, roll pitch yaw rad), antennas (l r), body_yaw. Zero outside [0, dur)."""
    def __init__(self, t, cols, name=""):
        self.t, self.cols, self.name = np.asarray(t, float), np.asarray(cols, float), name
        self.dur = float(self.t[-1]) if len(self.t) else 0.0

    def sample(self, tl):
        if tl < 0 or tl >= self.dur:
            return None
        return np.array([np.interp(tl, self.t, self.cols[:, i]) for i in range(self.cols.shape[1])])


_MOVES = {}


def load_move(name):
    if name in _MOVES:
        return _MOVES[name]
    files = glob.glob(f"{EMO_GLOB}/{name}.json")
    if not files:
        print(f"!! move {name}: not in the emotions cache, the puppet holds still for 2 s")
        _MOVES[name] = Track([0.0, 2.0], np.zeros((2, 9)), name)
        return _MOVES[name]
    j = json.load(open(files[0]))
    t = np.asarray(j["time"], float)
    rows = []
    for s in j["set_target_data"]:
        H = np.asarray(s["head"], float)
        R = H[:3, :3]
        roll, pitch, yaw = math.atan2(R[2, 1], R[2, 2]), -math.asin(max(-1.0, min(1.0, R[2, 0]))), math.atan2(R[1, 0], R[0, 0])
        ant = s.get("antennas") or [0.0, 0.0]
        rows.append([H[0, 3], H[1, 3], H[2, 3], roll, pitch, yaw, ant[0], ant[1], s.get("body_yaw") or 0.0])
    _MOVES[name] = Track(t, rows, name)
    return _MOVES[name]


def load_offsets(path):
    """Wobbler offsets file -> Track of pose6 (x y z in m, roll pitch yaw rad) plus three zero columns."""
    j = json.load(open(path))
    t = np.asarray(j["t"], float)
    cols = np.stack([np.asarray(j[k], float) / 1000.0 for k in ("x", "y", "z")] +
                    [np.asarray(j[k], float) for k in ("roll", "pitch", "yaw")] + [np.zeros(len(t))] * 3, axis=1)
    return Track(t, cols, j.get("version", Path(path).stem))


def wav_mono(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def fake_offsets(wav, hop_ms=20):
    """A 2 Hz nod of 0.06 rad pitch where the wav is loud (RMS above 15 % of the peak RMS), zero elsewhere."""
    sr = 16000
    x = wav_mono(wav, sr)
    hop = sr * hop_ms // 1000
    n = max(1, len(x) // hop)
    rms = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    loud = rms > 0.15 * rms.max() if rms.max() > 0 else np.zeros(n, bool)
    t = np.arange(n) * hop_ms / 1000.0
    pitch = 0.06 * np.sin(2 * math.pi * 2.0 * t) * loud
    cols = np.zeros((n, 9))
    cols[:, 4] = pitch
    return Track(t, cols, "fake")


def wav_len(p):
    try:
        with wave.open(str(p)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                    capture_output=True, text=True, check=True).stdout)


# ---------------------------------------------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------------------------------------------
def strip_tags(s):
    return re.sub(r"\s*\[[^\]]*\]\s*", " ", s).strip()


def build_timeline(scene, beats, versions, until=None, start_delay=1.0, fake=False, audio_fallback=None):
    """Returns (total_s, lines, moves, rows).
    lines: [(t_say, wav, speaker, text, wav_len, {version: Track or None})]
    moves: {actor: [(t_start, Track, t_cut)]}"""
    fallback = sorted(Path(audio_fallback).glob("*.wav")) if audio_fallback else []
    t = start_delay
    lines, rows = [], []
    moves = {a: [] for a in ACTORS}
    for i, b in enumerate(beats):
        if until and b["id"] == until:
            break
        t0 = t + float(b.get("pre", 0.0))
        spk = b.get("speaker", "loretta")
        listeners = [a for a in ACTORS if a != spk]     # an off-screen speaker: both robots listen
        need = 0.0
        if b.get("text"):
            wav = scene / "audio" / f"{b['id']}.wav"
            if not wav.exists() and fallback:
                wav = fallback[i % len(fallback)]
                print(f"   {b['id']}: no wav, borrowing {wav.name}")
            if wav.exists():
                ts = t0 + float(b.get("say_at", 0.0))
                wl = wav_len(wav)
                offs = {}
                for v in versions:
                    if fake:
                        offs[v] = fake_offsets(wav)
                    else:
                        p = scene / "audio" / "offsets" / f"{b['id']}.{v}.json"
                        offs[v] = load_offsets(p) if p.exists() else None
                        if offs[v] is None:
                            print(f"!! {b['id']}: no offsets {p.name}, the line plays without wobble")
                lines.append((ts, wav, spk, strip_tags(b["text"]), wl, offs))
                need = max(need, ts - t0 + wl + float(b.get("tail", 0.3)))
            else:
                print(f"!! {b['id']}: no wav ({wav}), silent beat of 2.5 s")
                need = max(need, 2.5)
        cap = float(b.get("cap", EMOTION_CAP_S))
        pairs = ([(spk, "emotions")] if spk in ACTORS else []) + [(l, "listener_emotions") for l in listeners]
        for actor, key in pairs:
            tc = t0
            for name in b.get(key) or []:
                mv = load_move(name)
                cut = min(tc + mv.dur, t0 + cap)
                if cut > tc:
                    moves[actor].append((tc, mv, cut))
                tc += mv.dur
            if key == "emotions":
                need = max(need, min(tc - t0, cap))
        length = max(float(b.get("hold", 0.0)), need, 0.3)
        rows.append(dict(t=round(t0, 2), id=b["id"], speaker=spk, length=round(length, 2), text=b.get("text", "")))
        t = t0 + length + float(b.get("gap", 0.0))
    return t + 1.0, lines, moves, rows


# ---------------------------------------------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------------------------------------------
class Camera:
    def __init__(self, m, size, lookat, distance, azimuth, elevation):
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.lookat[:] = lookat
        self.cam.distance, self.cam.azimuth, self.cam.elevation = distance, azimuth, elevation
        self.size, self.fovy = size, math.radians(m.vis.global_.fovy)

    def project(self, p):
        az, el = math.radians(self.cam.azimuth), math.radians(self.cam.elevation)
        fwd = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
        pos = np.array(self.cam.lookat) - self.cam.distance * fwd
        right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        v = np.asarray(p) - pos
        z = max(v @ fwd, 1e-3)
        W, H = self.size
        th = math.tan(self.fovy / 2)
        return ((v @ right) / (z * th * W / H) + 1) / 2 * W, (1 - (v @ up) / (z * th)) / 2 * H


_FONTS = {}


def font(path, px):
    if (path, px) not in _FONTS:
        _FONTS[(path, px)] = ImageFont.truetype(path, int(px))
    return _FONTS[(path, px)]


def wrap(text, width):
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    out.append(cur)
    return out


def overlay(img, cam, puppets, version, tt, line, breathing_only):
    """Caption strip (speaker, line), the version label, name tags above the heads."""
    W, H = img.size
    dr = ImageDraw.Draw(img, "RGBA")
    for name, a in ACTORS.items():
        x, y = cam.project(puppets[name].head_pos() + [0, 0, 0.11])
        f = font(FONT_BOLD, 22)
        w = dr.textlength(a["label"], font=f)
        dr.text((x - w / 2, y - 12), a["label"], font=f, fill=a["color"] + (255,), stroke_width=2, stroke_fill=(0, 0, 0, 200))
    dr.rounded_rectangle([12, 12, 12 + 250, 12 + 40], radius=8, fill=(0, 0, 0, 150))
    dr.text((22, 18), f"wobbler {version}", font=font(FONT_BOLD, 24), fill=(255, 255, 255, 255))
    dr.text((W - 90, 18), f"{tt:5.1f} s", font=font(FONT, 20), fill=(255, 255, 255, 200))
    if line is not None:
        spk, text = line
        a = ACTORS.get(spk) or OFFSCREEN[spk]
        lines = wrap(text, 72)[:3]
        band = 26 + 34 * len(lines) + 26
        dr.rectangle([0, H - band, W, H], fill=(0, 0, 0, 165))
        f_name, f_txt = font(FONT_BOLD, 26), font(FONT, 28)
        y = H - band + 22
        dr.text((30, y), a["label"].upper(), font=f_name, fill=a["color"] + (255,))
        x0 = 30 + dr.textlength(a["label"].upper(), font=f_name) + 24
        for i, l in enumerate(lines):
            dr.text((x0, y - 2 + i * 34), l, font=f_txt, fill=(255, 255, 255, 255))
    return img


class ActorState:
    """Eased 9-vector pose of one puppet (recorded moves tracked fast, return to neutral slowly)."""
    def __init__(self, phase):
        self.cur = np.zeros(9)
        self.phase = phase

    def step(self, dt, tt, target):
        tau = TAU_MOVE if target is not None else TAU_REST
        tgt = target if target is not None else np.zeros(9)
        self.cur += (tgt - self.cur) * (1 - math.exp(-dt / tau))
        out = self.cur.copy()
        out[2] += 0.0015 * math.sin(2 * math.pi * 0.22 * tt + self.phase)      # breathing: 1.5 mm at 0.22 Hz
        out[4] += 0.006 * math.sin(2 * math.pi * 0.22 * tt + self.phase + 0.8)
        return out


def frame_pose(tt, moves, lines, version):
    """Per actor: (recorded-move sample or None, wobble pose6 or None). Plus the caption line (speaker, text) or None."""
    out, caption = {}, None
    for actor in ACTORS:
        mv = None
        for (ts, tr, cut) in moves[actor]:
            if ts <= tt < cut:
                mv = tr.sample(tt - ts)
                break
        out[actor] = [mv, None]
    for (ts, wav, spk, text, wl, offs) in lines:
        if ts <= tt < ts + wl + 0.6:
            caption = (spk, text)
        tr = offs.get(version)
        if tr is not None and ts <= tt < ts + wl:
            s = tr.sample(tt - ts)
            if s is not None and spk in out:
                out[spk][1] = s[:6]
    return out, caption


def render_frame(r, m, d, cam, puppets, states, tt, dt, moves, lines, version):
    poses, caption = frame_pose(tt, moves, lines, version)
    for actor, pup in puppets.items():
        mv, wob = poses[actor]
        p = states[actor].step(dt, tt, mv)
        pose6 = p[:6] + (wob if wob is not None else 0.0)
        pup.set(pose6, antennas=p[6:8], body_yaw=p[8])
    mujoco.mj_forward(m, d)
    r.update_scene(d, camera=cam.cam)
    img = Image.fromarray(r.render())
    return overlay(img, cam, puppets, version, tt, caption, False)


def mix(silent, out, lines):
    """Mux the line wavs at their times onto the silent video (ffmpeg amix)."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(silent)]
    if not lines:
        cmd += ["-c:v", "copy", "-an", str(out)]
    else:
        parts = []
        for i, (ta, wav, *_rest) in enumerate(lines):
            cmd += ["-i", str(wav)]
            ms = int(round(ta * 1000))
            parts.append(f"[{i + 1}:a]aresample=48000,adelay={ms}|{ms}[s{i}]")
        parts.append("".join(f"[s{i}]" for i in range(len(lines))) + f"amix=inputs={len(lines)}:normalize=0,apad[a]")   # apad: the video length wins over -shortest
        cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-shortest", str(out)]
    subprocess.run(cmd, check=True)
    silent.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene_dir")
    ap.add_argument("--wobbler", default="v5", help="offsets version to use (audio/offsets/<id>.<version>.json)")
    ap.add_argument("--side-by-side", default=None, help="two versions, e.g. v0,v5: both rendered, left/right in one video")
    ap.add_argument("--out", default=None)
    ap.add_argument("--until", default=None, help="stop before this beat id")
    ap.add_argument("--start-delay", type=float, default=1.0)
    ap.add_argument("--fake-offsets", action="store_true", help="2 Hz nod where the wav is loud, instead of the offset files")
    ap.add_argument("--audio-fallback", default=None, help="dir of wavs to borrow for beats whose wav is missing")
    ap.add_argument("--still", type=float, default=None, help="render one PNG at this time (s) instead of the video")
    ap.add_argument("--clip", default=None, help="A:B seconds, render only this window (quick checks)")
    a = ap.parse_args()
    scene = Path(a.scene_dir)
    beats = json.load(open(scene / "scene.json"))
    versions = a.side_by_side.split(",") if a.side_by_side else [a.wobbler]
    tag = "_vs_".join(versions)
    out = Path(a.out) if a.out else scene / (f"preview_{tag}.mp4" if a.still is None else "preview_still.png")

    total, lines, moves, rows = build_timeline(scene, beats, versions, a.until, a.start_delay, a.fake_offsets, a.audio_fallback)
    print(f"{len(rows)} beats, {total:.1f} s, versions {versions}")
    for r_ in rows:
        print(f"   {r_['t']:6.2f}  {r_['id']:14s} {r_['speaker']:8s} {r_['length']:5.2f}  {strip_tags(r_['text'])[:60]}")

    m, d, puppets = build_scene()
    cam = Camera(m, SIZE, **CAMERA)
    r = mujoco.Renderer(m, SIZE[1], SIZE[0])
    dt = 1.0 / FPS

    def render_all(tt, states):
        imgs = [render_frame(r, m, d, cam, puppets, states[v], tt, dt, moves, lines, v) for v in versions]
        if len(imgs) == 1:
            return imgs[0]
        canvas = Image.new("RGB", (SIZE[0] * len(imgs), SIZE[1]))
        for i, im in enumerate(imgs):
            canvas.paste(im, (i * SIZE[0], 0))
        return canvas

    states = {v: {actor: ActorState(phase=i * 1.7) for i, actor in enumerate(ACTORS)} for v in versions}
    if a.still is not None:
        for k in range(int(a.still * FPS) + 1):              # run the easing up to the still's time
            img = render_all(k * dt, states)
        img.save(out)
        print("wrote", out)
        return

    t_from, t_to = 0.0, total
    if a.clip:
        t_from, t_to = (float(x) for x in a.clip.split(":"))
    silent = out.with_suffix(".silent.mp4")
    writer = imageio.get_writer(str(silent), fps=FPS, codec="libx264", pixelformat="yuv420p", macro_block_size=8,
                                output_params=["-crf", "20", "-movflags", "+faststart"])
    t0 = time.time()
    n = int(round(t_to * FPS))
    for k in range(n):
        tt = k * dt
        img = render_all(tt, states)
        if tt >= t_from:
            writer.append_data(np.asarray(img))
        if k % 250 == 0:
            print(f"   {tt:6.1f} s / {t_to:.1f}  ({time.time() - t0:.0f} s elapsed)")
    writer.close()
    shifted = [(ts - t_from, wav, spk, text, wl, offs) for (ts, wav, spk, text, wl, offs) in lines if ts - t_from > -wl]
    shifted = [l for l in shifted if l[0] >= 0]              # a line that started before the clip is dropped
    mix(silent, out, shifted)
    json.dump(rows, open(out.with_suffix(".beats.json"), "w"), indent=1)
    print(f"wrote {out}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
