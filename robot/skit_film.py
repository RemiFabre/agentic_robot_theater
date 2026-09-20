"""Two real Reachy Minis, one scene (couple_fight): the filming player. Runs on the Mac.

    robot/run_film.sh                                  # full motion, wobbler v6 (see scenes/couple_fight/FILMING.md)
    robot/run_film.sh --motion none                    # no head motion at all
    robot/run_film.sh --motion wobbler --wobbler main  # daemon's own live wobbler (what ships on main), no emotions
    robot/run_film.sh --motion full --wobbler v6       # emotions + the v6 offsets

Robots: Loretta = the wireless (its daemon runs on the robot, `--loretta reachy-mini.local:8000`), the husband = the
Lite on USB (its daemon runs on this Mac, started by hand: `--husband localhost:8000`).

What happens: both daemons are checked, the SDK connects, the emotion moves are loaded, every line's wav is made
available to the daemon that will play it (the Lite daemon reads the file from this disk; the wireless gets it
uploaded over REST, or copied with scp if the daemon is too old for the upload endpoint), motors on, wake-up. Then:
    >>> ENTER to start, ESC to abort <<<
ENTER starts beat 0 at once (`--start-delay S` waits S seconds first). ESC (or q, or Ctrl+C) at any time stops the
motion and the sound, puts both robots to sleep (unless `--no-sleep`) and exits. Run it again for the next take.

Motion modes (`--motion`):
    none     the robots stay awake and still; the lines play.
    wobbler  head wobble only, no recorded moves (the listener does nothing).
    full     recorded emotion moves (`emotions` for the speaker, `listener_emotions` for the other) + head wobble.
Wobbler (`--wobbler`):
    main     the daemon's own live wobbler on the audio it plays (whatever version is installed on that robot;
             on main that is v0). `enable_wobbling()` on both robots, nothing else.
    v0|v4|v5|v6  offline offsets from audio/offsets/<beat>.<version>.json, streamed to the daemon at the file's hop
             rate as speech offsets (SetSpeechOffsetsCmd: x y z in metres, roll pitch yaw in radians); the daemon
             composes them on the current head target before IK, exactly like the live wobbler's offsets. The sound
             is started over REST (POST /api/media/play_sound) and the offsets clock starts `--audio-latency` later.
             `--offsets local` composes the offsets on the SDK side instead (for a daemon without that command).
Timing keys per beat (scene.json): `say_at`, `tail`, `cap` (cut the move chain there), `hold`, `gap`, `pre`.
"""
import argparse, json, os, select, signal, subprocess, sys, termios, threading, time, tty, wave

import numpy as np
import requests

EMOTION_CAP_S = 20.0
LINGER_S = 3.0
TICK = 0.01
REST_S = 0.35            # the antenna rest pose used between beats
ZERO6 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
start_ev, stop_ev = threading.Event(), threading.Event()
T0 = time.monotonic()


class Stopped(Exception):
    pass


def now():
    return time.monotonic()


def say(msg):
    print(f"[{now() - T0:7.2f}] {msg}", end="\r\n", flush=True)     # raw tty needs an explicit CR


def isleep(s):
    if stop_ev.wait(max(s, 0.0)):
        raise Stopped()


def key_listener():
    """ENTER -> start_ev, ESC / q / Ctrl+C -> stop_ev. Restores the tty on exit."""
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        return                                            # no tty (tests): --auto-start does the ENTER
    try:
        tty.setcbreak(fd)
        while not stop_ev.is_set():
            if select.select([fd], [], [], 0.1)[0]:
                ch = os.read(fd, 1)
                if ch in (b"\r", b"\n"):
                    start_ev.set()
                elif ch in (b"\x1b", b"\x03", b"q"):
                    stop_ev.set()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def wav_seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


class OffsetTrack:
    """One <beat>.<version>.json: per-hop head offsets (x y z m, roll pitch yaw rad), indexed from the line start."""

    def __init__(self, path):
        d = json.load(open(path))
        self.path, self.hop = path, d["hop_ms"] / 1000.0
        mm = 1.0 / 1000.0
        self.rows = np.stack([np.asarray(d["x"]) * mm, np.asarray(d["y"]) * mm, np.asarray(d["z"]) * mm,
                              np.asarray(d["roll"]), np.asarray(d["pitch"]), np.asarray(d["yaw"])], axis=1)
        self.t0 = None

    def start(self, t0):
        self.t0 = t0

    def index(self, t):
        if self.t0 is None:
            return None
        i = int(round((t - self.t0) / self.hop))
        return i if 0 <= i < len(self.rows) else None

    def at(self, i):
        return tuple(float(v) for v in self.rows[i])


class Robot:
    """One robot: REST helpers, the SDK connection, a 100 Hz loop that plays queued moves and streams offsets."""

    def __init__(self, name, hostport, a, moves):
        self.name, self.a, self.moves = name, a, moves
        self.host, port = hostport.rsplit(":", 1)
        self.port = int(port)
        self.local = self.host in ("localhost", "127.0.0.1")
        self.url = f"http://{self.host}:{self.port}/api"
        self.mini = None
        self.sounds = {}            # beat id -> the `file` string the daemon plays
        self.lock = threading.Lock()
        self.queue, self.move, self.move_t0, self.blend = [], None, 0.0, False
        self.track, self.last_idx, self.sent_offset = None, None, False
        self.base = np.eye(4)
        self.chain_done = threading.Event(); self.chain_done.set()
        self.ticks = self.late = 0
        self.t_start = None
        self.th = threading.Thread(target=self.loop, daemon=True)
        self.compose = None

    # ---- REST
    def status(self):
        r = requests.get(f"{self.url}/daemon/status", timeout=4)
        r.raise_for_status()
        return r.json()

    def post(self, path, **kw):
        r = requests.post(f"{self.url}{path}", timeout=kw.pop("timeout", 6), **kw)
        r.raise_for_status()
        return r

    def prepare_sound(self, beat_id, wav):
        """Make the wav playable by this daemon; remember the `file` to send to play_sound."""
        if self.local:
            self.sounds[beat_id] = os.path.abspath(wav)
            return "local path"
        name = f"{self.a.scene_name}_{beat_id}.wav"
        try:
            with open(wav, "rb") as f:
                r = self.post("/media/sounds/upload", files={"file": (name, f, "audio/wav")}, timeout=20)
            self.sounds[beat_id] = r.json().get("path") or name
            return "uploaded"
        except requests.RequestException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code not in (404, 405):
                raise
        # old daemon without the upload endpoint: scp to the robot, play by absolute path
        user = self.a.ssh_user
        dest = f"/tmp/reachy_mini_sounds/{name}"
        subprocess.run(["ssh", "-o", "BatchMode=yes", f"{user}@{self.host}", "mkdir -p /tmp/reachy_mini_sounds"], check=True)
        subprocess.run(["scp", "-q", wav, f"{user}@{self.host}:{dest}"], check=True)
        self.sounds[beat_id] = dest
        return "scp"

    def play_sound(self, beat_id):
        self.post("/media/play_sound", json={"file": self.sounds[beat_id]})

    def stop_sound(self):
        try:
            self.post("/media/stop_sound", timeout=2)
        except requests.RequestException:
            pass

    def set_volume(self, v):
        self.post("/volume/set", json={"volume": int(v)})

    # ---- SDK
    def connect(self):
        from reachy_mini import ReachyMini
        mode = "localhost_only" if self.local else "network"
        self.mini = ReachyMini(host=self.host, port=self.port, connection_mode=mode, media_backend="no_media")
        if self.a.offsets == "local":
            from reachy_mini.utils import create_head_pose
            from reachy_mini.utils.interpolation import compose_world_offset

            def compose(pose, off):
                x, y, z, roll, pitch, yaw = off
                return compose_world_offset(pose, create_head_pose(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw, degrees=False))
            self.compose = compose

    def send_offsets(self, off):
        if self.compose is not None:
            return                                        # composed on the pose in loop()
        from reachy_mini.io.protocol import SetSpeechOffsetsCmd
        self.mini.client.send_command(SetSpeechOffsetsCmd(offsets=list(off)))

    def rest_pose(self, duration=1.0):
        self.mini.goto_target(head=np.eye(4), antennas=[-REST_S, REST_S], body_yaw=0.0, duration=duration)

    # ---- motion
    def play(self, names):
        """Queue a move chain; anything still playing is dropped (0.3 s blend into the first new move)."""
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
            self.track, self.last_idx = track, None

    def loop(self):
        next_t = self.t_start = now()
        while not stop_ev.is_set():
            t = now()
            with self.lock:
                if self.move is None and self.queue:
                    self.move, self.move_t0 = self.queue.pop(0), t
                    if self.blend:
                        head, ant, byaw = self.move.evaluate(0.0)
                        self.blend = False
                        self.lock.release()
                        try:
                            self.mini.goto_target(head=head, antennas=list(ant), body_yaw=byaw, duration=0.3)
                        finally:
                            self.lock.acquire()
                        self.move_t0 = t = now()
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
                self.mini.set_target_antenna_joint_positions([float(x) for x in ant])
            off = None
            if track is not None:
                i = track.index(t)
                if i is not None:
                    off = track.at(i)
            if self.compose is None:
                # daemon-side composition: send a new offset per hop, zeros once when the track ends
                if off is not None:
                    if i != self.last_idx:
                        self.send_offsets(off); self.last_idx = i; self.sent_offset = True
                elif self.sent_offset:
                    self.send_offsets(ZERO6); self.sent_offset = False
                if move is not None:
                    self.mini.set_target_head_pose(head)
            else:
                if move is not None or off is not None or self.sent_offset:
                    self.mini.set_target_head_pose(self.base if off is None else self.compose(self.base, off))
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
            self.cancel()


def timeline(beats, a, scene_dir, moves_dur):
    print(f"# {scene_dir}  motion={a.motion}  wobbler={a.wobbler}  from beat {a.from_beat}")
    t = a.start_delay
    for i, b in enumerate(beats):
        if i < a.from_beat:
            continue
        wav = os.path.join(scene_dir, "audio", f"{b['id']}.wav")
        line = wav_seconds(wav) if os.path.exists(wav) else 0.0
        chain = sum(moves_dur.get(n, 0.0) for n in b.get("emotions", [])) if a.motion == "full" else 0.0
        off = os.path.join(scene_dir, "audio", "offsets", f"{b['id']}.{a.wobbler}.json")
        offs = ("ok" if os.path.exists(off) else "MISSING") if a.wobbler not in ("main", "none") else a.wobbler
        end = max(b.get("say_at", 0) + line + b.get("tail", 0.3) if line else 0.0, min(chain, b.get("cap", EMOTION_CAP_S)), b.get("hold", 0.0))
        end += b.get("pre", 0.0)
        print(f"{t:6.1f}s [{i:2d}] {b['id']:<17} {b['speaker']:<8} line {line:4.1f}s  {b.get('emotions')} ({chain:.1f}s)"
              f"  offsets {offs}  beat {end:.1f}s")
        t += end + b.get("gap", 0.0)
    print(f"{t:6.1f}s end")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene_dir", nargs="?", default="scenes/couple_fight")
    ap.add_argument("--motion", choices=["none", "wobbler", "full"], default="full")
    ap.add_argument("--wobbler", default="v6", help="main (the daemon's live wobbler) or v0|v4|v5|v6 (offset files)")
    ap.add_argument("--loretta", default="reachy-mini.local:8000", help="the wireless: daemon on the robot")
    ap.add_argument("--husband", default="localhost:8000", help="the Lite: daemon on this Mac")
    ap.add_argument("--offsets", choices=["daemon", "local"], default="daemon", help="who composes the offsets")
    ap.add_argument("--audio-latency", type=float, default=0.10, help="s between play_sound and the first sample heard")
    ap.add_argument("--from-beat", type=int, default=0)
    ap.add_argument("--until", default=None, help="stop before this beat id (tests)")
    ap.add_argument("--start-delay", type=float, default=0.0, help="s between ENTER and beat 0")
    ap.add_argument("--volume", type=int, default=None, help="set both robots' speaker volume (0-100) at setup")
    ap.add_argument("--no-wake", action="store_true"); ap.add_argument("--no-sleep", action="store_true")
    ap.add_argument("--no-audio", action="store_true", help="no sound (motion only)")
    ap.add_argument("--no-listener", action="store_true", help="ignore listener_emotions")
    ap.add_argument("--auto-start", action="store_true", help="no ENTER prompt (tests)")
    ap.add_argument("--dry-run", action="store_true", help="print the timeline, no robots")
    ap.add_argument("--ssh-user", default="pollen")
    a = ap.parse_args()
    a.scene_name = os.path.basename(os.path.normpath(a.scene_dir))
    if a.motion == "none":
        a.wobbler = "none"
    scene_dir = a.scene_dir
    beats = json.load(open(os.path.join(scene_dir, "scene.json")))
    if a.until:
        beats = beats[:[b["id"] for b in beats].index(a.until)]
    from reachy_mini.motion.recorded_move import RecordedMoves
    moves = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
    names = sorted({n for b in beats for k in ("emotions", "listener_emotions") for n in b.get(k, [])})
    moves_dur = {n: moves.get(n).duration for n in names}
    if a.dry_run:
        timeline(beats, a, scene_dir, moves_dur)
        return 0

    use_daemon_wobbler = a.wobbler == "main"
    use_offsets = a.wobbler not in ("main", "none")
    robots = {"loretta": Robot("loretta", a.loretta, a, moves), "husband": Robot("husband", a.husband, a, moves)}
    threading.Thread(target=key_listener, daemon=True).start()
    for sg in (signal.SIGINT, signal.SIGTERM):        # Ctrl+C / kill = the same clean stop as ESC
        signal.signal(sg, lambda *_: stop_ev.set())
    ok = True
    try:
        # 1. daemons
        for r in robots.values():
            try:
                st = r.status()
                say(f"{r.name}: daemon at {r.host}:{r.port} state={st.get('state')} wlan={st.get('wlan_ip')}")
            except requests.RequestException as e:
                say(f"!!! {r.name}: no daemon at {r.host}:{r.port} ({e.__class__.__name__}). "
                    f"{'Start it: reachy-mini-daemon' if r.local else 'Is the robot on and on the Wi-Fi?'}")
                return 1
        # 2. sounds
        for b in beats:
            if not b.get("text") or a.no_audio:
                continue
            wav = os.path.join(scene_dir, "audio", f"{b['id']}.wav")
            if not os.path.exists(wav):
                say(f"!!! missing {wav}"); return 1
            r = robots.get(b["speaker"])
            if r is None:
                r = robots["husband"]                     # an off-screen voice (Larry) plays from the Lite, next to the WALL-E
            say(f"  {b['id']:<17} -> {r.name}: {r.prepare_sound(b['id'], wav)}")
        # 3. SDK, motors, wake-up (both robots at once)
        for r in robots.values():
            r.connect(); say(f"{r.name}: SDK connected")
            if a.volume is not None:
                r.set_volume(a.volume)

        def wake(r):
            r.mini.enable_motors()
            if a.no_wake:
                r.rest_pose(1.0)
            else:
                r.mini.wake_up()
            if use_daemon_wobbler:
                r.mini.enable_wobbling()
            else:
                r.mini.disable_wobbling()               # also zeroes any stale speech offsets
        ths = [threading.Thread(target=wake, args=(r,)) for r in robots.values()]
        for t in ths: t.start()
        for t in ths: t.join()
        say(f"setup done: motion={a.motion} wobbler={a.wobbler} offsets={a.offsets if use_offsets else '-'}"
            f"{' NO AUDIO' if a.no_audio else ''}, {len(beats)} beats from {a.from_beat}")
        say(f">>> ENTER to start (beat {a.from_beat} after {a.start_delay:g}s), ESC to abort <<<")
        if a.auto_start:
            start_ev.set()
        while not start_ev.is_set():
            if stop_ev.is_set():
                raise Stopped()
            time.sleep(0.05)
        for r in robots.values():
            r.th.start()
        isleep(a.start_delay)
        # 4. the scene
        for i, b in enumerate(beats):
            if i < a.from_beat:
                continue
            bt = now()
            sp = b["speaker"]
            speaker = robots.get(sp) or robots["husband"]
            listeners = [r for k, r in robots.items() if k != sp]
            say(f"[{i}] {b['id']}: {sp} {b.get('emotions') if a.motion == 'full' else ''}")
            isleep(b.get("pre", 0.0))
            if a.motion == "full":
                if sp in robots:
                    speaker.play(b.get("emotions", []))
                if b.get("listener_emotions") and not a.no_listener:
                    for r in listeners:
                        r.play(b["listener_emotions"])
            if b.get("text"):
                isleep(b.get("say_at", 0.0))
                wav = os.path.join(scene_dir, "audio", f"{b['id']}.wav")
                dur = wav_seconds(wav)
                track = None
                if use_offsets and sp in robots:
                    p = os.path.join(scene_dir, "audio", "offsets", f"{b['id']}.{a.wobbler}.json")
                    if os.path.exists(p):
                        track = OffsetTrack(p)
                    else:
                        say(f"  !!! no offsets {p}, the line plays without wobble")
                if not a.no_audio:
                    speaker.play_sound(b["id"])
                t_line = now() + a.audio_latency
                if track is not None:
                    track.start(t_line); speaker.set_track(track)
                say(f"  line {dur:.2f}s{' + ' + os.path.basename(track.path) if track else ''}")
                isleep(dur + b.get("tail", 0.3))
                if track is not None:
                    speaker.set_track(None)
            if a.motion == "full":
                if sp in robots:
                    speaker.wait_chain(timeout=b.get("cap", EMOTION_CAP_S), started_at=bt)
            isleep(b.get("hold", 0.0) - (now() - bt))
            isleep(b.get("gap", 0.0))
        say(f"end of the scene, lingering {LINGER_S}s (ESC to sleep now)")
        isleep(LINGER_S)
    except (Stopped, KeyboardInterrupt):
        say("!!! stopping (ESC)")
        ok = False
    except Exception as e:  # noqa: BLE001
        say(f"!!! error: {e!r}")
        ok = False
    finally:
        stop_ev.set()
        for r in robots.values():
            if r.mini is None:
                continue
            try:
                r.cancel()
                if r.th.is_alive():
                    r.th.join(1.0)
                if not a.no_audio:
                    r.stop_sound()
                if use_daemon_wobbler:
                    r.mini.disable_wobbling()
                elif r.compose is None and r.sent_offset:
                    r.send_offsets(ZERO6)
                if r.t_start:
                    el = max(now() - r.t_start, 1e-3)
                    say(f"{r.name}: loop {r.ticks / el:.0f} Hz over {el:.0f}s, {r.late} late ticks")
                if a.no_sleep:
                    r.rest_pose(1.0)
                else:
                    say(f"{r.name}: going to sleep")
                    r.mini.goto_sleep(); r.mini.disable_motors()
                r.mini.__exit__(None, None, None)
            except Exception as e:  # noqa: BLE001
                say(f"{r.name}: teardown: {e!r}")
    say("done" if ok else "aborted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
