#!/usr/bin/env python
"""Shared building blocks for the "Microduck meets Reachy Mini" film (simulation side).

Everything the duck does goes through the SAME channels the real robot exposes to a script
(`robot.move` twist, `robot.head` 4 deltas, `robot.pose` body pose, `robot.mouth`, `robot.relax`):
the shipped ONNX policies read the 13-D command block and move the joints themselves. No direct
joint writes on the duck, except the mouth (a real servo outside every policy) and the two runtime
behaviours (relax = motors off, limp-fall + pose ramp).

Runs in /Users/remi/microduck/.venv-mjlab (mujoco 3.10, onnxruntime, bam, imageio, PIL).
"""
import math
from pathlib import Path

import mujoco, numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

WS = Path("/Users/remi/microduck")
ROBOT_XML = WS / "microduck_rl/src/mjlab_microduck/robot/microduck/robot_allcollisions.xml"   # whole-body contacts
POLICIES = {
    "walk": WS / "microduck/policies/alpha_walking.onnx",
    "stand": WS / "microduck/policies/alpha_stand.onnx",
    "sitstand": WS / "microduck/policies/alpha_sitstand.onnx",
    "kick_left": WS / "microduck/policies/ball_kick_left.onnx",
    "kick_right": WS / "microduck/policies/ball_kick_right.onnx",
    "roulade": WS / "microduck/policies/roulade.onnx",
}
FONT_COMIC = "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf"
FONT_CAPTION = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

HOME = np.array([0.0, -0.0873, -0.4579, -0.0049, 0.4530, 0.3491, 0.3491, 0.0, 0.0, 0.0, 0.0873, 0.4579, 0.0049, -0.4530], np.float32)
JOINTS = ("left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle",
          "neck_pitch", "head_pitch", "head_yaw", "head_roll",
          "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle")
HEAD_IDX = [5, 6, 7, 8]          # neck_pitch, head_pitch, head_yaw, head_roll in the 14-joint vector
N_SERVO = 14
DT = 0.005
DECIMATION = 4
CDT = DT * DECIMATION            # 50 Hz control
FPS = 25
SPAWN_Z = 0.125
KP_WALK, KP_STAND, KP_LIMP = 200.0, 160.0, 50.0     # robotd: gain 200, standing ratio 0.8, gain_limp 50
STAND_THRESHOLD = 0.3            # robotd will_stand: twist magnitude at or below this = stand net (probe-confirmed deadband)
HEAD_ALPHA = 0.2                 # robotd head_alpha: per-tick EMA on head + body-pose intents
CMD_ALPHA = 0.2                  # robotd cmd_alpha: per-tick EMA on the twist
JAW_HINGE = np.array([-0.014, 0.0, -0.012])
JAW_MAX = 0.22
G = np.array([0, 0, -1], np.float32)

# --- the cream colourway (official website variant) -----------------------------------------------------------
def _h(x):
    return [int(x[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]

AMBER, ORANGE, CLEAN_Y = _h("f5a30a"), _h("f2760e"), _h("f4cd49")
DARK, GRAY, WARM_GRAY, LENS = _h("1d1d1f"), _h("8b8b90"), _h("9b9892"), _h("101018")
CREAM = dict(dome=_h("f7e6cb"), face=WARM_GRAY, trim=ORANGE, bu=AMBER, bl=ORANGE, tg=AMBER,
             eye=AMBER, body=_h("f7e6cb"), legs=_h("f7e6cb"), feet=ORANGE, soles=CLEAN_Y)
SLOT_MATS = {"top_head_shell_material": "dome", "face_part_material": "face", "bottom_head_shell_material": "trim",
             "soft_mouth_top_material": "bu", "jaw_material": "bl", "jaw_soft_material": "tg", "noenoeil_material": "eye",
             "trunk_base_material": "body", "left_shell_material": "body", "right_shell_material": "body",
             "upper_leg_left_material": "legs", "upper_leg_right_material": "legs",
             "foot_left_material": "feet", "foot_right_material": "feet",
             "ankle_left_material": "feet", "ankle_right_material": "feet",
             "sole_left_material": "soles", "sole_right_material": "soles"}
FIXED_MATS = {"lens_material": LENS, "hip_l_material": GRAY, "xl330_material": DARK,
              "seeed_bearing__configuration_default_material": DARK, "yaw2roll_material": DARK, "bearing_roll_material": DARK,
              "np_f970_material": DARK, "pcb__raspberry_pi_zero_2_w_material": DARK, "elec_rpi_robot_hat_pcb_material": DARK,
              "banana_pcb_locker_material": DARK, "speaker_material": DARK, "m12_lens_holder_material": DARK,
              "leg_material": GRAY, "neck_material": GRAY, "neck_pitch_material": GRAY, "motor_support_material": GRAY,
              "power_support_material": GRAY, "upper_leg_rigidity_plate_material": GRAY, "yaw_roll_motion_material": GRAY,
              "seeed_bearing__configuration__22x16x4_material": GRAY}


def qrotinv(q, v):
    w, xyz = q[0], q[1:4]
    t = np.cross(xyz, v) * 2
    return v - w * t + np.cross(xyz, t)


def yaw_quat(yaw):
    return np.array([math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)])


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def smooth(x, k=1.0):
    """0..1 -> 0..1 ease in-out."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


class Policy:
    def __init__(self, path):
        self.sess = ort.InferenceSession(str(path))
        self.iname = self.sess.get_inputs()[0].name
        self.name = Path(path).stem

    def __call__(self, obs):
        return self.sess.run(None, {self.iname: obs[None].astype(np.float32)})[0][0].astype(np.float32)


_POL = {}
def policy(name):
    if name not in _POL:
        _POL[name] = Policy(POLICIES[name])
    return _POL[name]


# ---------------------------------------------------------------------------------------------------------------
class Duck:
    """One BAM-actuated microduck driven like robotd drives the real one.

    Intent inputs (set every control tick, all optional):
      twist (vx, vy, wz), head (4 deltas from HOME, rad), body (z, roll, pitch, ... 6), mouth 0..1,
      skill: None | 'kick_left' | 'kick_right' | 'roulade' | 'sit' | 'rise', relax: motors off.
    The net is picked like robotd: skill > sit/rise > stand (|twist| <= threshold) > walk.
    """
    def __init__(self, model, data, prefix="duck_"):
        self.m, self.d, self.prefix = model, data, prefix
        m = model
        self.trunk = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, prefix + "trunk_base")
        self.head_body = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, prefix + "jaw_soft")
        self.beak_site = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, prefix + "beak_tip")
        fj = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, prefix + "trunk_base_freejoint")
        self.fa, self.fv = int(m.jnt_qposadr[fj]), int(m.jnt_dofadr[fj])
        jj = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, prefix + "jaw_open")
        self.jaw_q, self.jaw_v = int(m.jnt_qposadr[jj]), int(m.jnt_dofadr[jj])
        self.act_names = [prefix + n for n in JOINTS]
        self.act_ids = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in self.act_names]
        self.qpos_idx = [int(m.jnt_qposadr[m.actuator_trnid[i, 0]]) for i in self.act_ids]
        self.qvel_idx = [int(m.jnt_dofadr[m.actuator_trnid[i, 0]]) for i in self.act_ids]
        self.gyro_adr = int(m.sensor_adr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SENSOR, prefix + "imu_ang_vel")])
        self.bam = None
        self.command = np.zeros(13, np.float32)
        self.last_action = np.zeros(N_SERVO, np.float32)
        self.kp = KP_STAND
        # intents (what a client would send)
        self.twist = np.zeros(3)
        self.head = np.zeros(4)
        self.body = np.zeros(6)
        self.mouth = 0.0
        self.skill = None
        self.relax = False
        self.ramp = None            # (t0, dur, q_from): the runtime's pose ramp back to HOME (init / limp-fall recovery)
        self.limp_fall = True       # robotd default: go limp when a fall is detected, ramp back to standing on rest
        self.limp_state = None      # None | 'limp' | 'ramp'
        self.limp_since = 0.0
        self._down_ticks = 0
        # smoothed intents (robotd EMAs)
        self.twist_s = np.zeros(3)
        self.head_s = np.zeros(4)
        self.body_s = np.zeros(6)
        self.net = "stand"
        self.jaw_open = 0.0
        self.t = 0.0
        self.yaw_acc, self.yaw_prev = 0.0, 0.0
        self.fell_at = None
        self.log = []

    def make_bam(self):
        from bam.model import load_model
        from bam.mujoco import MujocoController
        m = self.m
        bm = load_model(motor_name="xl330", model="m6")
        bm.actuator.kp = KP_STAND
        bm.actuator.vin = 7.5
        ids = self.act_ids
        m.actuator_gainprm[ids, :] = 0.0
        m.actuator_gainprm[ids, 0] = 1.0
        m.actuator_biasprm[ids, :] = 0.0
        m.actuator_ctrllimited[ids] = 0
        m.actuator_forcelimited[ids] = 0
        try:
            self.bam = MujocoController(bm, self.act_names, m, self.d, vin_drop_resistance=0.04, vin_min=6.0)
        except TypeError:
            self.bam = MujocoController(bm, self.act_names, m, self.d)

    def spawn(self, x, y, yaw):
        d = self.d
        d.qpos[self.fa:self.fa + 3] = [x, y, SPAWN_Z + 0.003]
        d.qpos[self.fa + 3:self.fa + 7] = yaw_quat(yaw)
        d.qvel[self.fv:self.fv + 6] = 0
        d.qpos[self.qpos_idx] = HOME
        d.qvel[self.qvel_idx] = 0
        self.last_action[:] = 0
        self.yaw_acc, self.yaw_prev = yaw, yaw
        self.fell_at = None
        if self.bam is not None:
            self.bam.q_target[:] = d.qpos[self.qpos_idx]
            self.bam._prev_motor_torque[:] = 0.0
            self.bam.last_ts = d.time

    # --- state ---
    def pos(self):
        return self.d.qpos[self.fa:self.fa + 3].copy()

    def quat(self):
        return self.d.qpos[self.fa + 3:self.fa + 7].copy()

    def yaw(self):
        q = self.quat()
        return math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2))

    def head_pos(self):
        return self.d.xpos[self.head_body].copy()

    def beak_pos(self):
        return self.d.site_xpos[self.beak_site].copy()

    def grav(self):
        return qrotinv(self.d.xquat[self.trunk].astype(np.float32), G)

    def fallen(self):
        return self.grav()[2] > -0.7

    def upright(self):
        g = self.grav()
        return math.hypot(g[0], g[1]) < 0.25 and self.pos()[2] > 0.10

    def q(self):
        return self.d.qpos[self.qpos_idx].copy()

    def bearing_to(self, p):
        """Angle (rad, signed) from the duck's heading to the point p (xy)."""
        v = np.asarray(p)[:2] - self.pos()[:2]
        return wrap(math.atan2(v[1], v[0]) - self.yaw())

    def dist_to(self, p):
        v = np.asarray(p)[:2] - self.pos()[:2]
        return float(np.hypot(v[0], v[1]))

    def obs(self):
        d = self.d
        gyro = d.sensordata[self.gyro_adr:self.gyro_adr + 3].astype(np.float32)
        jpos = d.qpos[self.qpos_idx].astype(np.float32) - HOME
        jvel = d.qvel[self.qvel_idx].astype(np.float32)
        return np.concatenate([gyro, self.grav(), jpos, jvel, self.last_action, self.command]).astype(np.float32)

    # --- control (50 Hz) ---
    def control_tick(self, t):
        self.t = t
        # robotd EMAs on intents
        self.twist_s += CMD_ALPHA * (np.asarray(self.twist, float) - self.twist_s)
        self.head_s += HEAD_ALPHA * (np.asarray(self.head, float) - self.head_s)
        self.body_s += HEAD_ALPHA * (np.asarray(self.body, float) - self.body_s)
        # the runtime's limp-fall: gains drop while going down, ramp back to standing once at rest
        # robotd limp_fall: tilted past limp_fall_tilt_z (-0.90) AND the 300 ms extrapolation of gravity z lands past
        # limp_fall_predict_z (-0.5), debounced 60 ms. A static lean of 30 deg does not trigger it; a fall in progress does.
        gz = float(self.grav()[2])
        dgz = (gz - self._gz_prev) / CDT if hasattr(self, "_gz_prev") else 0.0
        self._gz_prev = gz
        going_down = gz > -0.90 and gz + 0.3 * dgz > -0.5
        self._down_ticks = self._down_ticks + 1 if going_down else 0
        if self.limp_fall and self.limp_state is None and not self.relax and self.ramp is None and self._down_ticks >= 3:
            self.limp_state, self.limp_since = "limp", t
        if self.limp_state == "limp":
            still = np.abs(self.d.qvel[self.fv:self.fv + 6]).max() < 0.5 and t - self.limp_since > 0.4
            if still or t - self.limp_since > 3.0:
                self.limp_state = "ramp"
                self.ramp = (t, 0.6, self.q())
        if self.relax:
            self.net = "relax"
            self.kp = 0.0
            self.limp_state = None
            self.ramp = None
        elif self.limp_state == "limp":
            self.net = "limp"
            self.kp = KP_LIMP
            self.bam.model.actuator.kp = self.kp
            self.bam.q_target[:] = self.q()          # follow wherever it is pushed
        elif self.ramp is not None:
            t0, dur, q0 = self.ramp
            a = min(1.0, (t - t0) / dur)
            self.net = "ramp"
            self.kp = KP_STAND
            self.bam.model.actuator.kp = self.kp
            self.bam.q_target[:] = q0 + (HOME - q0) * a
            if a >= 1.0:
                self.ramp, self.limp_state = None, None
                self.last_action[:] = 0
        else:
            self._policy_tick()
        # mouth: a real servo, outside every policy
        self.jaw_open += 0.5 * (JAW_MAX * float(self.mouth) - self.jaw_open)

    def _policy_tick(self):
        c = np.zeros(13, np.float32)
        sk = self.skill
        if sk == "roulade":
            net, kp = "roulade", KP_WALK
        elif sk in ("kick_left", "kick_right"):
            net, kp = sk, KP_STAND
        elif sk == "sit":
            net, kp = "sitstand", KP_WALK
            c[0] = 1.0
            c[3:7] = self.head_s
            c[7:13] = self.body_s
        elif sk == "rise":
            net, kp = "sitstand", KP_STAND
            c[3:7] = self.head_s
            c[7:13] = self.body_s
        else:
            tw = self.twist_s
            mag = float(np.linalg.norm(tw))
            body_active = bool(np.any(np.abs(self.body_s) > 1e-4))
            if body_active or mag <= STAND_THRESHOLD:
                net, kp = "stand", KP_STAND
            else:
                net, kp = "walk", KP_WALK
                c[0:3] = tw
            c[3:7] = self.head_s
            c[7:13] = self.body_s
        self.net, self.kp = net, kp
        self.command[:] = c
        self.bam.model.actuator.kp = kp
        act = policy(net)(self.obs())
        self.last_action = act
        self.bam.q_target[:] = HOME + act

    def physics_substep(self):
        d = self.d
        if self.relax:
            d.ctrl[self.act_ids] = 0.0
        else:
            self.bam.update()
        d.qpos[self.jaw_q] = self.jaw_open
        d.qvel[self.jaw_v] = 0

    def after_step(self, t):
        y = self.yaw()
        self.yaw_acc += wrap(y - self.yaw_prev)
        self.yaw_prev = y
        if self.fell_at is None and self.fallen():
            self.fell_at = t


# ---------------------------------------------------------------------------------------------------------------
# Scene: floor, the duck (with a visual beak hinge), Reachy Mini asleep
# ---------------------------------------------------------------------------------------------------------------
def add_duck(spec, prefix="duck_", variant=CREAM):
    spec.attach(mujoco.MjSpec.from_file(str(ROBOT_XML)), prefix=prefix, frame=spec.worldbody.add_frame())
    for mat in spec.materials:
        if not mat.name.startswith(prefix):
            continue
        base = mat.name[len(prefix):]
        if base in SLOT_MATS:
            mat.rgba = variant[SLOT_MATS[base]]
        elif base in FIXED_MATS:
            mat.rgba = FIXED_MATS[base]
    head = spec.body(prefix + "jaw_soft")
    jaw = head.add_body(name=prefix + "jaw", pos=JAW_HINGE, mass=0.005, inertia=[2e-7, 2e-7, 2e-7], explicitinertial=True)
    jaw.add_joint(name=prefix + "jaw_open", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 1, 0], range=[-0.05, 0.6],
                  damping=0.01, stiffness=0.5, armature=1e-5)
    for g in list(head.geoms):
        if g.meshname in (prefix + "jaw", prefix + "jaw_soft", prefix + "soft_mouth_top") and g.classname.name == prefix + "visual":
            jaw.add_geom(type=mujoco.mjtGeom.mjGEOM_MESH, meshname=g.meshname, material=g.material,
                         pos=np.array(g.pos) - JAW_HINGE, quat=g.quat, contype=0, conaffinity=0, group=2)
            spec.delete(g)
    # beak tip marker (head frame: x = up, -z = forward)
    head.add_site(name=prefix + "beak_tip", pos=[-0.045, 0.0, -0.075], size=[0.004, 0, 0], rgba=[1, 0, 0, 0])


# Reachy Mini, asleep: a white cylinder body, a head that sinks onto it face-down, antennas folded.
# Real sizes: 28 cm tall awake, ~23 cm asleep, 16 cm wide, 1.5 kg.
RM_BODY_R, RM_BODY_H = 0.08, 0.15         # cylinder radius, height
RM_HEAD_R = 0.075
WHITE = [0.94, 0.94, 0.92, 1]
OFFW = [0.86, 0.86, 0.84, 1]
BLACK = [0.08, 0.08, 0.09, 1]


def add_reachy(spec, x, y, yaw, mobile=True):
    root = spec.worldbody.add_body(name="rm_body", pos=[x, y, 0.0], quat=yaw_quat(yaw))
    if mobile:
        root.add_joint(name="rm_free", type=mujoco.mjtJoint.mjJNT_FREE)
    # body: cylinder + a rounded shoulder, low centre of mass so pecks only rock it
    root.add_geom(name="rm_can", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[RM_BODY_R, RM_BODY_H / 2, 0],
                  pos=[0, 0, RM_BODY_H / 2], rgba=WHITE, mass=1.2, friction=[0.9, 0.005, 0.0001])
    root.add_geom(name="rm_base", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[RM_BODY_R + 0.004, 0.006, 0],
                  pos=[0, 0, 0.006], rgba=BLACK, mass=0.2)
    root.add_geom(name="rm_shoulder", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID, size=[RM_BODY_R, RM_BODY_R, 0.03],
                  pos=[0, 0, RM_BODY_H], rgba=WHITE, mass=0.05)
    # head: slides up (z), yaws, pitches. Driven kinematically by the film.
    head = root.add_body(name="rm_head", pos=[0, 0, RM_BODY_H + 0.015])
    # the head joints are stiff springs whose rest position the film moves (a kinematic puppet that stays
    # inside the physics: no direct qpos writes, which pumped momentum into the free body)
    head.add_joint(name="rm_head_z", type=mujoco.mjtJoint.mjJNT_SLIDE, axis=[0, 0, 1], range=[-0.01, 0.09], stiffness=2000, damping=40)
    head.add_joint(name="rm_head_yaw", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 0, 1], range=[-2.6, 2.6], stiffness=30, damping=1.5)
    head.add_joint(name="rm_head_pitch", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 1, 0], range=[-0.6, 1.3], stiffness=30, damping=1.5)
    head.add_geom(name="rm_skull", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID, size=[RM_HEAD_R, RM_HEAD_R * 0.95, 0.055],
                  pos=[0, 0, 0.03], rgba=WHITE, mass=0.25)
    # the neck: a dark column that stays inside the body when asleep and shows when the head rises
    head.add_geom(name="rm_neck", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.028, 0.08, 0], pos=[0, 0, -0.06],
                  rgba=[0.12, 0.12, 0.13, 1], contype=0, conaffinity=0, mass=0.05)
    # the black face plate, slightly forward, with two big round eyes (camera + light)
    head.add_geom(name="rm_face", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID, size=[0.05, 0.062, 0.042],
                  pos=[0.036, 0, 0.028], rgba=BLACK, mass=0.02)
    for s, r in ((1, 0.020), (-1, 0.014)):
        head.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[r, 0.004, 0], pos=[0.081, s * 0.028, 0.030],
                      quat=[0.7071, 0, 0.7071, 0], rgba=WHITE, contype=0, conaffinity=0, mass=0.001)
        head.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[r * 0.55, 0.005, 0], pos=[0.084, s * 0.028, 0.030],
                      quat=[0.7071, 0, 0.7071, 0], rgba=[0.05, 0.05, 0.08, 1], contype=0, conaffinity=0, mass=0.001)
    # antennas: two thin rods on hinges at the back of the skull; folded flat when asleep
    for s in (1, -1):
        ant = head.add_body(name=f"rm_ant_{'l' if s > 0 else 'r'}", pos=[-0.045, s * 0.04, 0.06])
        ant.add_joint(name=f"rm_ant_{'l' if s > 0 else 'r'}", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 1, 0],
                      range=[-3.14, 0.7], stiffness=2.0, damping=0.05)
        ant.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, size=[0.004, 0.05, 0], pos=[0, 0, 0.05],
                     rgba=[0.15, 0.15, 0.17, 1], contype=0, conaffinity=0, mass=0.005)
        ant.add_geom(type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[0.008, 0, 0], pos=[0, 0, 0.105],
                     rgba=[0.15, 0.15, 0.17, 1], contype=0, conaffinity=0, mass=0.003)


class Reachy:
    """Kinematic puppet: pose targets (head z 0..1, yaw, pitch, antennas 0..1) eased over time."""
    SLEEP = dict(z=0.0, yaw=0.0, pitch=0.55, ant=0.0)      # head sunk, face down, antennas hanging
    AWAKE = dict(z=1.0, yaw=0.0, pitch=0.0, ant=1.0)

    def __init__(self, model, data):
        self.m, self.d = model, data
        m = model
        self.body = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "rm_body")
        self.headb = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "rm_head")
        j = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)
        self.jz, self.jyaw, self.jpitch = j("rm_head_z"), j("rm_head_yaw"), j("rm_head_pitch")
        self.jal, self.jar = j("rm_ant_l"), j("rm_ant_r")
        self.free = j("rm_free") if j("rm_free") >= 0 else None
        self.cur = dict(self.SLEEP)
        self.tgt = dict(self.SLEEP)
        self.tau = 0.6
        self.talking = False
        self.step(1.0, 0.0)
        d = self.d
        for jj in (self.jz, self.jyaw, self.jpitch, self.jal, self.jar):
            d.qpos[m.jnt_qposadr[jj]] = m.qpos_spring[m.jnt_qposadr[jj]]

    def pose(self, tau=None, **kw):
        self.tgt.update(kw)
        if tau is not None:
            self.tau = tau

    def look_at(self, p):
        """Yaw the head toward a world point (relative to the body yaw)."""
        hp = self.d.xpos[self.headb]
        v = np.asarray(p) - hp
        q = self.d.xquat[self.body]
        vl = qrotinv(q.astype(float), v)
        self.tgt["yaw"] = math.atan2(vl[1], vl[0])
        self.tgt["pitch"] = float(np.clip(-math.atan2(vl[2], math.hypot(vl[0], vl[1])), -0.5, 1.0))

    def step(self, dt, t):
        k = 1 - math.exp(-dt / self.tau)
        for key in self.cur:
            self.cur[key] += (self.tgt[key] - self.cur[key]) * k
        d, m = self.d, self.m
        bob = 0.02 * math.sin(2 * math.pi * 5.0 * t) if self.talking else 0.0
        m.qpos_spring[m.jnt_qposadr[self.jz]] = 0.06 * self.cur["z"]
        m.qpos_spring[m.jnt_qposadr[self.jyaw]] = self.cur["yaw"]
        m.qpos_spring[m.jnt_qposadr[self.jpitch]] = self.cur["pitch"] + bob
        a = -3.05 + (0.15 + 3.05) * self.cur["ant"]      # hanging down the back when asleep, up when awake
        m.qpos_spring[m.jnt_qposadr[self.jal]] = a
        m.qpos_spring[m.jnt_qposadr[self.jar]] = a

    def head_pos(self):
        return self.d.xpos[self.headb].copy() + [0, 0, 0.03]

    def pos(self):
        return self.d.xpos[self.body].copy()


def build_scene(size=(1280, 720), reachy_at=(0.0, 0.0, 0.0), reachy_mobile=True):
    spec = mujoco.MjSpec()
    spec.compiler.degree = False          # every angle in this file is in radians (joint ranges!)
    spec.visual.global_.offwidth, spec.visual.global_.offheight = size
    spec.visual.headlight.diffuse, spec.visual.headlight.ambient = [0.5, 0.5, 0.5], [0.35, 0.35, 0.35]
    spec.visual.headlight.specular = [0.0, 0.0, 0.0]
    spec.visual.quality.shadowsize = 8192
    spec.visual.map.shadowclip = 1.0
    spec.add_texture(name="sky", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX, builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT,
                     rgb1=[0.3, 0.5, 0.7], rgb2=[0.85, 0.92, 1.0], width=512, height=3072)
    spec.worldbody.add_light(name="sun", pos=[0.5, -1.0, 3.5], dir=[-0.15, 0.3, -1],
                             type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL, castshadow=True)
    spec.add_texture(name="groundplane", type=mujoco.mjtTexture.mjTEXTURE_2D, builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                     rgb1=[0.2, 0.3, 0.4], rgb2=[0.1, 0.2, 0.3], mark=mujoco.mjtMark.mjMARK_EDGE, markrgb=[0.8, 0.8, 0.8], width=300, height=300)
    spec.add_material(name="groundplane", texrepeat=[5, 5], texuniform=True, reflectance=0.2).textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = "groundplane"
    spec.worldbody.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[0, 0, 0.05], material="groundplane",
                            solref=[0.04, 1.0], solimp=[0.85, 0.95, 0.001, 0.5, 2.0])
    add_duck(spec, "duck_")
    if reachy_at is not None:
        add_reachy(spec, *reachy_at, mobile=reachy_mobile)
    m = spec.compile()
    m.opt.timestep = DT
    m.stat.center = np.array([0.0, 0.0, 0.15])
    m.stat.extent = 2.5
    return m, mujoco.MjData(m)


# ---------------------------------------------------------------------------------------------------------------
# Camera rig + overlays (from the comic film)
# ---------------------------------------------------------------------------------------------------------------
class Rig:
    def __init__(self, model, size, lookat, distance, azimuth, elevation):
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.size, self.fovy = size, math.radians(model.vis.global_.fovy)
        self.cur = dict(lookat=np.array(lookat, float), distance=float(distance), azimuth=float(azimuth), elevation=float(elevation))
        self.tgt = dict(self.cur)
        self.track = None
        self.tau = 1.2
        self._apply()

    def shot(self, lookat=None, distance=None, azimuth=None, elevation=None, tau=None, track=None):
        if track is not None:
            self.track = track
        elif lookat is not None:
            self.track = None
            self.tgt["lookat"] = np.array(lookat, float)
        if distance is not None: self.tgt["distance"] = float(distance)
        if azimuth is not None: self.tgt["azimuth"] = float(azimuth)
        if elevation is not None: self.tgt["elevation"] = float(elevation)
        if tau is not None: self.tau = tau

    def step(self, dt):
        if self.track is not None:
            self.tgt["lookat"] = np.asarray(self.track(), float)
        k = 1 - math.exp(-dt / self.tau)
        for key in self.cur:
            if key == "azimuth":
                self.cur[key] += wrap(math.radians(self.tgt[key] - self.cur[key])) * k * 180 / math.pi
            else:
                self.cur[key] = self.cur[key] + (self.tgt[key] - self.cur[key]) * k
        self._apply()

    def _apply(self):
        self.cam.lookat[:] = self.cur["lookat"]
        self.cam.distance, self.cam.azimuth, self.cam.elevation = self.cur["distance"], self.cur["azimuth"], self.cur["elevation"]

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


class Overlay:
    def __init__(self, size):
        self.W, self.H = size
        self.s = self.H / 1080
        self._cache = {}

    def font(self, path, px):
        px = max(8, int(px))
        if (path, px) not in self._cache:
            self._cache[(path, px)] = ImageFont.truetype(path, px)
        return self._cache[(path, px)]

    def bubble(self, draw, text, anchor, side, pop=1.0, scale=1.0, font=FONT_COMIC):
        s = self.s * pop * scale
        f = self.font(font, 44 * s)
        lines = text.split("\n")
        widths = [draw.textlength(l, font=f) for l in lines]
        lh = f.size * 1.25
        w, h = max(widths) + 44 * s, lh * len(lines) + 30 * s
        ax, ay = anchor
        dx = -1 if side == "left" else 1
        cx = ax + dx * (w / 2 + 40 * s)
        cy = ay - h / 2 - 90 * s
        cx = min(max(cx, w / 2 + 10), self.W - w / 2 - 10)
        cy = max(cy, h / 2 + 10)
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        tx = cx - dx * w * 0.2
        tail = [(tx - 16 * s, cy + h / 2 - 2), (tx + 16 * s, cy + h / 2 - 2), (ax, ay - 12 * s)]
        draw.polygon(tail, fill="white", outline="black")
        draw.line([tail[0], tail[2], tail[1]], fill="black", width=int(4 * s))
        draw.rounded_rectangle(box, radius=int(26 * s), fill="white", outline="black", width=int(4 * s))
        y_top = cy - (lh * len(lines)) / 2
        for i, (l, wl) in enumerate(zip(lines, widths)):
            draw.text((cx - wl / 2, y_top + i * lh), l, font=f, fill="black")

    def caption(self, draw, text, y=None, color="white"):
        f = self.font(FONT_CAPTION, 34 * self.s)
        lines = text.split("\n")
        lh = f.size * 1.3
        y0 = (self.H - 40 * self.s - lh * len(lines)) if y is None else y
        for i, l in enumerate(lines):
            w = draw.textlength(l, font=f)
            draw.text(((self.W - w) / 2, y0 + i * lh), l, font=f, fill=color, stroke_width=int(3 * self.s), stroke_fill="black")

    def big(self, draw, text, center, color=(230, 30, 30), scale=1.0):
        f = self.font("/System/Library/Fonts/Supplemental/Impact.ttf", 140 * self.s * scale)
        w = draw.textlength(text, font=f)
        draw.text((center[0] - w / 2, center[1] - f.size / 2), text, font=f, fill=color, stroke_width=int(8 * self.s), stroke_fill="black")
