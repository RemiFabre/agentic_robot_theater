#!/usr/bin/env python3
"""Cue the Microduck from a scene: emotions, skills, sounds, short walks — as gamepad presses.

The duck's pad daemon (`padd`, film build `pad-expressions`) listens on TCP 7777 for one JSON
line per cue and answers one JSON line (`{"ok": true, "duration": 8.5}`). The pad stays alive
underneath: Rémi can still turn the duck with the stick between cues; only an expression locks
the sticks while it plays. Stdlib only, so it runs on the Reachy Mini, the Mac, anywhere.

    python3 duck_cue.py ping                      # is padd there, which expressions it knows
    python3 duck_cue.py express excited           # play an emotion, prints its duration
    python3 duck_cue.py skill ground_pick         # a one-shot skill (sit_toggle, kick_left, roulade...)
    python3 duck_cue.py sound chirp               # a bank sound
    python3 duck_cue.py move 0.3 0 0 --for 1.5    # walk forward 1.5 s
    python3 duck_cue.py stop                      # end the expression / the scripted walk now

`DUCK_CUE=host:port` (default 192.168.1.29:7777). Every cue is logged with a timestamp.
"""
import argparse, json, os, socket, sys, time

DEFAULT = "192.168.1.29:7777"


class Duck:
    """One connection, one line per cue, one answer per line."""
    def __init__(self, addr=None, timeout=3.0, dry=False, log=print):
        self.addr = addr or os.environ.get("DUCK_CUE", DEFAULT)
        self.dry, self.log, self.timeout = dry, log, timeout
        self.sock = None

    def connect(self):
        if self.dry or self.sock:
            return
        host, port = self.addr.rsplit(":", 1)
        self.sock = socket.create_connection((host, int(port)), timeout=self.timeout)
        self.rd = self.sock.makefile("r")

    def cue(self, **obj):
        line = json.dumps(obj, separators=(",", ":"))
        if self.dry:
            self.log(f"{time.strftime('%H:%M:%S')} duck (dry) {line}")
            return {"ok": True, "duration": obj.get("for", 0.0)}
        self.connect()
        self.sock.sendall((line + "\n").encode())
        answer = self.rd.readline()
        if not answer:
            raise ConnectionError("padd closed the cue connection")
        r = json.loads(answer)
        self.log(f"{time.strftime('%H:%M:%S')} duck {line} -> {answer.strip()}")
        if not r.get("ok"):
            raise RuntimeError(f"duck refused {line}: {r.get('error')}")
        return r

    # the cues
    def ping(self):
        return self.cue(ping=True)

    def express(self, kind):
        """Start an emotion; returns its length in seconds."""
        return float(self.cue(express=kind).get("duration", 0.0))

    def skill(self, name):
        return float(self.cue(skill=name).get("duration", 0.0))

    def sound(self, tag):
        self.cue(sound=tag)
        return 0.5

    def move(self, vx, vy, wz, seconds):
        return float(self.cue(move=[vx, vy, wz], **{"for": seconds}).get("duration", seconds))

    def stop(self):
        self.cue(stop=True)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None


# The duck cues a scene beat may carry, in the order they are looked up. A beat holds for the
# returned duration (or its own `hold`, whichever is longer).
BEAT_KEYS = ("duck", "duck_skill", "duck_sound", "duck_move")


def beat_cue(duck, beat):
    """Send the beat's duck cue, if any. Returns the seconds the duck needs, 0.0 for none."""
    if "duck" in beat:
        return duck.express(beat["duck"])
    if "duck_skill" in beat:
        return duck.skill(beat["duck_skill"])
    if "duck_sound" in beat:
        return duck.sound(beat["duck_sound"])
    if "duck_move" in beat:
        vx, vy, wz = beat["duck_move"]
        return duck.move(vx, vy, wz, float(beat.get("for", 1.0)))
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ping", "express", "skill", "sound", "move", "stop"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--for", dest="for_", type=float, default=1.0)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--addr", default=None)
    a = ap.parse_args()
    d = Duck(a.addr, dry=a.dry)
    try:
        if a.cmd == "ping":
            print(d.ping())
        elif a.cmd == "express":
            print("duration", d.express(a.args[0]))
        elif a.cmd == "skill":
            print("duration", d.skill(a.args[0]))
        elif a.cmd == "sound":
            d.sound(a.args[0])
        elif a.cmd == "move":
            vx, vy, wz = (float(x) for x in a.args[:3])
            d.move(vx, vy, wz, a.for_)
        elif a.cmd == "stop":
            d.stop()
    finally:
        d.close()


if __name__ == "__main__":
    sys.exit(main())
