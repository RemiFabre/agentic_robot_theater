"""Two-Reachy scene player (couple_fight): one scene.json, two daemons, a selectable head wobbler.

    python robot/skit_duo.py scenes/couple_fight --wobbler v5
    python robot/skit_duo.py scenes/couple_fight --dry-run          # timeline only, no robots
    python robot/skit_duo.py scenes/couple_fight --wobbler daemon   # daemon-side wobbler (needs MEDIA=1 daemons)

Run it with the SDK venv's python (it needs reachy_mini + numpy):
    /Users/remi/reachy_mini_apps/reachy_mini/.venv/bin/python robot/skit_duo.py scenes/couple_fight

Per beat, `speaker` picks the robot (loretta = port 8000, husband = 8001 by default). The speaker plays its
`emotions` chain (never cut short, except by `cap`), and while its line plays the head offsets of
audio/offsets/<id>.<wobbler>.json are composed on top of the move's head pose exactly like the daemon composes
the live wobbler: offset = create_head_pose(x_m, y_m, z_m, roll, pitch, yaw), pose = compose_world_offset(pose, offset)
(translations add in world, R_final = R_off @ R_abs). The other robot plays `listener_emotions` if present (not
awaited: its chain is dropped when it has to speak). Audio: afplay on the Mac at `say_at` (the sim has no speaker).
One clock for everything (time.monotonic); offsets index = round((now - line_t0) / hop). Loop at 100 Hz per robot.
Ctrl+C aborts: motion stops, both robots go back to a neutral pose.

--wobbler daemon: no offsets; the lines go through mini.media.play_sound() with mini.enable_wobbling(), i.e. the SDK's
LOCAL audio path (GStreamer to the Mac's speakers, the v0 tapper on the SDK side sending offsets to the daemon).
The daemons must run with media (MEDIA=1 robot/run_sim_duo.sh). --wobbler none = no wobble at all (control).
"""
import argparse, json, os, subprocess, sys, threading, time, wave

import numpy as np

EMOTION_CAP_S = 20.0
LINGER_S = 3.0
AFPLAY_LATENCY_S = 0.08   # afplay starts playing about this long after Popen; the offsets clock starts then
TICK = 0.01
ZERO6 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
stop_ev = threading.Event()
T0 = time.monotonic()


class Stopped(Exception):
    pass


def now():
    return time.monotonic()


def log(msg):
    print(f"[{now() - T0:7.2f}] {msg}", flush=True)


def isleep(s):
    if stop_ev.wait(max(s, 0.0)):
        raise Stopped()


def wav_seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


class OffsetTrack:
    """One <beat>.<version>.json: per-hop head offsets, indexed from the line's start time."""

    def __init__(self, path):
        d = json.load(open(path))
        self.path, self.hop = path, d["hop_ms"] / 1000.0
        self.placeholder = bool(d.get("placeholder", False))
        mm = 1.0 / 1000.0
        # daemon order: (x_m, y_m, z_m, roll_rad, pitch_rad, yaw_rad)
        self.rows = np.stack([np.asarray(d["x"]) * mm, np.asarray(d["y"]) * mm, np.asarray(d["z"]) * mm,
                              np.asarray(d["roll"]), np.asarray(d["pitch"]), np.asarray(d["yaw"])], axis=1)
        self.t0 = None

    def start(self, t0):
        self.t0 = t0

    def at(self, t):
        if self.t0 is None:
            return None
        i = int(round((t - self.t0) / self.hop))
        if 0 <= i < len(self.rows):
            return tuple(float(v) for v in self.rows[i])
        return None

    @property
    def duration(self):
        return len(self.rows) * self.hop


class Actor:
    """One robot: a 100 Hz loop that plays queued moves and composes the active offsets on the head pose."""

    def __init__(self, name, mini, moves, compose):
        self.name, self.mini, self.moves, self.compose = name, mini, moves, compose
        self.lock = threading.Lock()
        self.queue, self.move, self.move_t0 = [], None, 0.0
        self.base = np.eye(4)          # last commanded head pose without offsets
        self.track = None               # active OffsetTrack (speaker only)
        self.chain_done = threading.Event(); self.chain_done.set()
        self.sent_offset = False
        self.ticks = self.late = 0
        self.t_start = None
        self.th = threading.Thread(target=self.loop, daemon=True)

    def start(self):
        self.th.start()

    def play(self, names):
        """Queue a chain; anything still playing is dropped (blend into the first new move)."""
        with self.lock:
            self.queue = [self.moves.get(n) for n in names]
            self.move, self.blend = None, True
            if self.queue:
                self.chain_done.clear()

    def cancel(self):
        with self.lock:
            self.queue, self.move = [], None
            self.chain_done.set()

    def set_track(self, track):
        with self.lock:
            self.track = track

    def loop(self):
        next_t = self.t_start = now()
        while not stop_ev.is_set():
            t = now()
            with self.lock:
                if self.move is None and self.queue:
                    self.move = self.queue.pop(0)
                    self.move_t0 = t
                    if self.blend:
                        head, ant, byaw = self.move.evaluate(0.0)
                        self.blend = False
                        self.lock.release()
                        try:
                            self.mini.goto_target(head=head, antennas=list(ant), body_yaw=byaw, duration=0.3)
                        finally:
                            self.lock.acquire()
                        self.move_t0 = now()
                        t = self.move_t0
                move, track = self.move, self.track
            if move is not None:
                tm = t - self.move_t0
                if tm >= move.duration:
                    with self.lock:
                        self.move = None
                        if not self.queue:
                            self.chain_done.set()
                    continue
                head, ant, byaw = move.evaluate(min(tm, move.duration - 1e-2))
                self.base = head
                self.mini.set_target_body_yaw(float(byaw or 0.0))
                self.mini.set_target_antenna_joint_positions([float(a) for a in ant])
            off = track.at(t) if (track is not None and self.compose) else None
            if move is not None or off is not None or self.sent_offset:
                pose = self.base if off is None else self.compose(self.base, off)
                self.mini.set_target_head_pose(pose)
                self.sent_offset = off is not None
            self.ticks += 1
            next_t += TICK
            d = next_t - now()
            if d > 0:
                time.sleep(d)
            else:
                self.late += 1
                next_t = now()

    def wait_chain(self, timeout, started_at):
        while not self.chain_done.is_set() and now() - started_at < timeout:
            isleep(0.05)
        if not self.chain_done.is_set():
            log(f"  {self.name}: chain capped at {timeout:g}s")
            self.cancel()


def make_compose():
    from reachy_mini.utils import create_head_pose
    from reachy_mini.utils.interpolation import compose_world_offset

    def compose(pose, off):
        x, y, z, roll, pitch, yaw = off
        return compose_world_offset(pose, create_head_pose(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw, degrees=False))
    return compose


def connect(name, hostport, media):
    from reachy_mini import ReachyMini
    host, port = hostport.rsplit(":", 1)
    mode = "localhost_only" if host in ("localhost", "127.0.0.1") else "network"
    mini = ReachyMini(host=host, port=int(port), connection_mode=mode, media_backend=media)
    log(f"{name}: connected to {hostport} (media {media})")
    return mini


def timeline(beats, a, scene_dir, moves_dur):
    print(f"# {scene_dir}  wobbler={a.wobbler}  from beat {a.from_beat}")
    t = a.start_delay
    for i, b in enumerate(beats):
        if i < a.from_beat:
            continue
        wav = os.path.join(scene_dir, "audio", f"{b['id']}.wav")
        line = wav_seconds(wav) if os.path.exists(wav) else 0.0
        chain = sum(moves_dur.get(n, 0.0) for n in b.get("emotions", []))
        off = os.path.join(scene_dir, "audio", "offsets", f"{b['id']}.{a.wobbler}.json")
        offs = ("real" if not json.load(open(off)).get("placeholder") else "PLACEHOLDER") if os.path.exists(off) else "missing"
        end = max(b.get("say_at", 0) + line + b.get("tail", 0.3) if line else 0.0, min(chain, b.get("cap", EMOTION_CAP_S)), b.get("hold", 0.0))
        end += b.get("pre", 0.0)
        print(f"{t:6.1f}s [{i}] {b['id']:<13} {b['speaker']:<8} line {line:4.1f}s  {b.get('emotions')} ({chain:.1f}s)"
              f"  listener {b.get('listener_emotions')}  offsets {offs}  beat {end:.1f}s")
        t += end + b.get("gap", 0.0)
    print(f"{t:6.1f}s end")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir", nargs="?", default="scenes/couple_fight")
    ap.add_argument("--wobbler", default="v5", help="v0|v4|v5|v6|... (offset files), daemon, or none")
    ap.add_argument("--loretta", default="localhost:8000")
    ap.add_argument("--husband", default="localhost:8001")
    ap.add_argument("--from-beat", type=int, default=0)
    ap.add_argument("--start-delay", type=float, default=0.0)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the timeline, no robots")
    ap.add_argument("--no-wake", action="store_true")
    ap.add_argument("--no-listener", action="store_true", help="ignore listener_emotions")
    ap.add_argument("--audio-latency", type=float, default=AFPLAY_LATENCY_S)
    a = ap.parse_args()
    scene_dir = a.scene_dir
    beats = json.load(open(os.path.join(scene_dir, "scene.json")))
    from reachy_mini.motion.recorded_move import RecordedMoves
    moves = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
    names = sorted({n for b in beats for k in ("emotions", "listener_emotions") for n in b.get(k, [])})
    moves_dur = {n: moves.get(n).duration for n in names}
    if a.dry_run:
        timeline(beats, a, scene_dir, moves_dur)
        return 0
    use_daemon = a.wobbler == "daemon"
    media = "default" if use_daemon else "no_media"
    minis = {"loretta": connect("loretta", a.loretta, media), "husband": connect("husband", a.husband, media)}
    compose = None if a.wobbler in ("daemon", "none") else make_compose()
    actors = {k: Actor(k, m, moves, compose) for k, m in minis.items()}
    players = []
    try:
        for k, m in minis.items():
            m.enable_motors()
            if not a.no_wake:
                m.wake_up()
            else:
                m.goto_target(head=np.eye(4), antennas=[-0.17, 0.17], duration=1.0)
            if use_daemon:
                m.enable_wobbling()
        for act in actors.values():
            act.start()
        log(f"setup done, wobbler={a.wobbler}; beat {a.from_beat} in {a.start_delay:g}s (Ctrl+C aborts)")
        isleep(a.start_delay)
        for i, b in enumerate(beats):
            if i < a.from_beat:
                continue
            bt = now()
            sp = b["speaker"]; li = "husband" if sp == "loretta" else "loretta"
            log(f"[{i}] {b['id']}: {sp} {b.get('emotions')}  listener {b.get('listener_emotions')}")
            isleep(b.get("pre", 0.0))
            actors[sp].play(b.get("emotions", []))
            if b.get("listener_emotions") and not a.no_listener:
                actors[li].play(b["listener_emotions"])
            if b.get("text"):
                isleep(b.get("say_at", 0.0))
                wav = os.path.abspath(os.path.join(scene_dir, "audio", f"{b['id']}.wav"))
                if not os.path.exists(wav):
                    log(f"  !!! no wav for {b['id']}, skipping the line")
                    dur = 0.0
                else:
                    dur = wav_seconds(wav)
                    track = None
                    if compose is not None:
                        p = os.path.join(scene_dir, "audio", "offsets", f"{b['id']}.{a.wobbler}.json")
                        if os.path.exists(p):
                            track = OffsetTrack(p)
                        else:
                            log(f"  !!! no offsets {p}, line plays without wobble")
                    if use_daemon:
                        minis[sp].media.play_sound(wav)
                        t_line = now()
                    elif a.no_audio:
                        t_line = now()
                    else:
                        pl = subprocess.Popen(["afplay", wav]); players.append(pl)
                        t_line = now() + a.audio_latency
                    if track is not None:
                        track.start(t_line); actors[sp].set_track(track)
                        log(f"  line {dur:.2f}s, offsets {os.path.basename(track.path)}"
                            f"{' (PLACEHOLDER)' if track.placeholder else ''} hop {track.hop*1000:.0f} ms")
                    else:
                        log(f"  line {dur:.2f}s")
                    isleep(dur + b.get("tail", 0.3))
                    actors[sp].set_track(None)
            actors[sp].wait_chain(timeout=b.get("cap", EMOTION_CAP_S), started_at=bt)
            isleep(b.get("hold", 0.0) - (now() - bt))
            log(f"  beat done in {now() - bt:.2f}s")
            isleep(b.get("gap", 0.0))
        log(f"end, lingering {LINGER_S}s"); isleep(LINGER_S)
    except (Stopped, KeyboardInterrupt):
        log("!!! stopping")
    finally:
        stop_ev.set()
        for pl in players:
            if pl.poll() is None:
                pl.terminate()
        for act in actors.values():
            act.cancel()
            if act.th.is_alive():
                act.th.join(1.0)
            if act.t_start:
                el = max(now() - act.t_start, 1e-3)
                log(f"{act.name}: loop {act.ticks / el:.0f} Hz over {el:.0f}s, {act.late} late ticks")
        for k, m in minis.items():
            try:
                if use_daemon:
                    m.disable_wobbling()
                m.goto_target(head=np.eye(4), antennas=[-0.17, 0.17], body_yaw=0.0, duration=1.0)
                m.__exit__(None, None, None)
            except Exception as e:  # noqa: BLE001
                log(f"{k}: teardown: {e}")
    log("done"); return 0


if __name__ == "__main__":
    sys.exit(main())
