"""Scene player. Runs ON the robot over `ssh -t` (see run_on_robot.sh).

Usage: skit.py <scene_dir> [--start-delay S] [--from-beat K] [--no-wake] [--no-sleep]
Setup first (load emotions, connect, motors on, wake-up move), then ENTER waits --start-delay
and starts beat 0; ESC/q/Ctrl+C aborts at any point (motion + audio stop, robot goes back to
sleep). Spoken beats need <scene_dir>/audio/<id>.wav.
"""
import argparse, json, os, select, sys, termios, threading, time, tty

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


class EmotionRunner:
    def __init__(self, mini, moves):
        self.mini, self.moves, self.th = mini, moves, None

    def start(self, names):
        def run():
            for i, n in enumerate(names):
                if stop_ev.is_set(): return
                self.mini.play_move(self.moves.get(n), initial_goto_duration=0.4 if i == 0 else 0.0, sound=False)
        self.th = threading.Thread(target=run, daemon=True); self.th.start()

    def wait(self, timeout=EMOTION_CAP_S):
        t0 = time.time()
        while self.th and self.th.is_alive() and time.time() - t0 < timeout:
            isleep(0.05)
        if self.th and self.th.is_alive():
            self.mini._move_cancelled = True; self.th.join(2.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir")
    ap.add_argument("--start-delay", type=float, default=0.0)
    ap.add_argument("--from-beat", type=int, default=0)
    ap.add_argument("--no-wake", action="store_true")
    ap.add_argument("--no-sleep", action="store_true")
    a = ap.parse_args()
    beats = json.load(open(os.path.join(a.scene_dir, "scene.json")))
    t0 = time.time()
    moves = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
    for b in beats:
        for n in b.get("emotions", []): moves.get(n)
    threading.Thread(target=key_listener, daemon=True).start()
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
                bt = time.time()
                say(f"[{i}] {b['id']}: {b.get('emotions')} {'(speaks)' if b.get('text') else ''}")
                isleep(b.get("pre", 0.0))
                em.start(b.get("emotions", []))
                if b.get("text"):
                    p = os.path.join(a.scene_dir, "audio", f"{b['id']}.wav")
                    mini.media.play_sound(os.path.abspath(p))
                    isleep(audio_duration_seconds(p) + b.get("tail", 0.3))
                em.wait()
                isleep(b.get("hold", 0.0) - (time.time() - bt))
                isleep(b.get("gap", 0.0))
            say(f"end, lingering {LINGER_S}s (ESC to sleep now)"); isleep(LINGER_S)
        except Stopped:
            say("!!! stopping"); mini.cancel_move(); em.wait(timeout=2.0)
        finally:
            stop_ev.set(); mini.disable_wobbling()
            if not a.no_sleep:
                say("going to sleep"); mini.goto_sleep(); mini.disable_motors()
    say("done"); return 0


if __name__ == "__main__":
    sys.exit(main())
