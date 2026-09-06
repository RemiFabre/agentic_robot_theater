"""Scene player. Runs ON the Reachy Mini over `ssh -t` (see run_on_robot.sh).

Usage: skit.py <scene_dir> [--start-delay S] [--from-beat K] [--no-wake] [--no-sleep] [--no-duck]
Setup first (load emotions, connect, motors on, wake-up move, ping the duck), then ENTER waits
--start-delay and starts beat 0; ESC/q/Ctrl+C aborts at any point (motion + audio stop, robot
goes back to sleep, the duck's expression is stopped). Spoken beats need <scene_dir>/audio/<id>.wav.

Timing keys (episode 3 v3): `say_at` delays the line inside the beat (the duck cue fires at the beat start);
`cap` cuts the Reachy move chain at that many seconds (moves are otherwise never cut short); `body_yaw`
turns Reachy's WHOLE robot (radians, 1 s) at the beat start and keeps it until a later beat sets another
value (0 = facing front). The daemon's automatic body yaw keeps the head pointing where it was while the
body turns, so the turn rotates the head target too, and while an offset is active the recorded moves
are played by our own loop with their head poses rotated and their body yaw offset by the same angle
(the head and the moves follow the body, as Rémi wants).

Two robots (episode 3): a beat may also carry ONE duck cue — `"duck": "excited"` (an emotion of
the film build, see microduck/EMOTIONS.md), `"duck_skill": "ground_pick"`, `"duck_sound": "chirp"`
or `"duck_move": [vx, vy, wz], "for": 1.5` — sent to the duck's pad daemon over TCP (duck_cue.py,
`DUCK_CUE=host:port`). The duck's cue runs in parallel with the Reachy's line / emotions of the
same beat, and the beat lasts at least as long as the duck needs (the daemon answers with the
emotion's length). The gamepad stays alive between cues. `"wait": "key"` makes a beat wait for
ENTER before it runs (for the moments Rémi pilots the duck by hand: standing it up, turning it).
"""
import argparse, json, math, os, select, sys, termios, threading, time, tty

import numpy as np

from duck_cue import Duck, beat_cue, has_cue

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_mini.media.gstreamer_utils import audio_duration_seconds

EMOTION_CAP_S = 20.0
LINGER_S = 10.0  # stay awake after the last beat before sleeping
start_ev, stop_ev = threading.Event(), threading.Event()


class Stopped(Exception):
    pass


def key_listener():
    fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not stop_ev.is_set():
            if select.select([fd], [], [], 0.1)[0]:
                ch = os.read(fd, 1)
                if ch in (b"\r", b"\n"): start_ev.set()
                elif ch in (b"\x1b", b"\x03", b"q"): stop_ev.set()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def isleep(s):
    if stop_ev.wait(max(s, 0.0)):
        raise Stopped()


def say(msg):
    print(msg, end="\r\n", flush=True)  # raw tty needs explicit CR


def rot_z(yaw):
    c, s_ = math.cos(yaw), math.sin(yaw)
    m = np.eye(4); m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s_, s_, c
    return m


class EmotionRunner:
    def __init__(self, mini, moves):
        self.mini, self.moves, self.th = mini, moves, None
        self.yaw = 0.0        # the scene's body-yaw offset, applied to every target while it is active

    def turn(self, yaw, duration=1.0):
        """Turn the whole robot (body and head together) to `yaw` radians."""
        self.yaw = float(yaw)
        self.mini.goto_target(head=rot_z(self.yaw), body_yaw=self.yaw, duration=duration)

    def _play_turned(self, move):
        """The SDK's play loop with the yaw offset on the head pose and the body yaw (100 Hz)."""
        t0 = time.time()
        while time.time() - t0 < move.duration and not stop_ev.is_set() and not self.mini._move_cancelled:
            t = min(time.time() - t0, move.duration - 1e-2)
            head, antennas, body_yaw = move.evaluate(t)
            if head is not None:
                self.mini.set_target_head_pose(rot_z(self.yaw) @ head)
            self.mini.set_target_body_yaw((body_yaw or 0.0) + self.yaw)
            if antennas is not None:
                self.mini.set_target_antenna_joint_positions(list(antennas))
            time.sleep(max(0.001, 0.01 - (time.time() - t0 - t)))

    def start(self, names):
        def run():
            for i, n in enumerate(names):
                if stop_ev.is_set(): return
                if abs(self.yaw) > 1e-3:
                    self.mini._move_cancelled = False
                    self._play_turned(self.moves.get(n))
                else:
                    self.mini.play_move(self.moves.get(n), initial_goto_duration=0.4 if i == 0 else 0.0, sound=False)
        self.th = threading.Thread(target=run, daemon=True); self.th.start()

    def wait(self, timeout=EMOTION_CAP_S, started_at=None):
        t0 = started_at or time.time()
        while self.th and self.th.is_alive() and time.time() - t0 < timeout:
            isleep(0.05)
        if self.th and self.th.is_alive():
            self.mini.cancel_move(); self.th.join(2.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir")
    ap.add_argument("--start-delay", type=float, default=0.0)
    ap.add_argument("--from-beat", type=int, default=0)
    ap.add_argument("--no-wake", action="store_true")
    ap.add_argument("--no-sleep", action="store_true")
    ap.add_argument("--no-duck", action="store_true", help="ignore the duck cues (Reachy only)")
    ap.add_argument("--dry-duck", action="store_true", help="print the duck cues instead of sending them")
    a = ap.parse_args()
    beats = json.load(open(os.path.join(a.scene_dir, "scene.json")))
    t0 = time.time()
    moves = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
    for b in beats:
        for n in b.get("emotions", []): moves.get(n)
    threading.Thread(target=key_listener, daemon=True).start()
    duck = None
    if not a.no_duck and any(has_cue(b) for b in beats):
        duck = Duck(dry=a.dry_duck, log=say)
        try:
            duck.ping()
        except OSError as e:
            say(f"!!! the duck's cue port is not answering ({e}); running Reachy only. Set DUCK_CUE=host:port or --no-duck")
            duck = None
    with ReachyMini() as mini:
        mini.enable_motors()
        if not a.no_wake:
            say("wake up"); mini.wake_up()
        say(f"setup done in {time.time()-t0:.1f}s, robot awake. "
            f">>> ENTER to start (beat 0 after {a.start_delay:g}s), ESC to abort <<<")
        while not start_ev.is_set():
            if stop_ev.is_set():
                say("aborted")
                if not a.no_sleep: mini.goto_sleep()
                mini.disable_motors(); return 0
            time.sleep(0.05)
        em = EmotionRunner(mini, moves)
        try:
            isleep(a.start_delay)
            mini.enable_wobbling()
            for i, b in enumerate(beats):
                if i < a.from_beat: continue
                if b.get("wait") == "key":
                    start_ev.clear()
                    say(f">>> [{i}] {b['id']}: {b.get('note', 'ENTER when ready')} <<<")
                    while not start_ev.is_set():
                        isleep(0.05)
                bt = time.time()
                cue = " ".join(f"{k}={b[k]}" for k in ("duck", "duck_skill", "duck_sound", "duck_move", "duck_init", "duck_policy", "duck_cues") if k in b)
                say(f"[{i}] {b['id']}: {b.get('emotions')} {'(speaks)' if b.get('text') else ''} {cue}")
                isleep(b.get("pre", 0.0))
                need = 0.0
                if duck and cue:
                    try:
                        need = beat_cue(duck, b)
                    except (OSError, RuntimeError) as e:
                        say(f"!!! duck cue failed: {e}")
                if "body_yaw" in b:
                    em.turn(float(b["body_yaw"]))
                em.start(b.get("emotions", []))
                if b.get("text"):
                    isleep(b.get("say_at", 0.0))
                    p = os.path.join(a.scene_dir, "audio", f"{b['id']}.wav")
                    mini.media.play_sound(os.path.abspath(p))
                    isleep(audio_duration_seconds(p) + b.get("tail", 0.3))
                em.wait(timeout=b.get("cap", EMOTION_CAP_S), started_at=bt)
                isleep(max(b.get("hold", 0.0), need) - (time.time() - bt))
                isleep(b.get("gap", 0.0))
            say(f"end, lingering {LINGER_S}s (ESC to sleep now)"); isleep(LINGER_S)
        except Stopped:
            say("!!! stopping"); mini.cancel_move(); em.wait(timeout=2.0)
            if duck:
                try:
                    duck.stop()
                except (OSError, RuntimeError):
                    pass
        finally:
            stop_ev.set(); mini.disable_wobbling()
            if not a.no_sleep:
                say("going to sleep"); mini.goto_sleep(); mini.disable_motors()
    if duck:
        duck.close()
    say("done"); return 0


if __name__ == "__main__":
    sys.exit(main())
