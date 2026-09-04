#!/usr/bin/env python3
"""Drive the REAL Microduck from this Mac with the same intents the film uses (no gamepad, no retraining).

robotd listens on /run/robotd.sock (newline-delimited JSON-RPC 2.0, api_version 16). We reach it through
`ssh microduck` (ControlMaster alias, see ~/.ssh/config) and `socat`/`nc -U` on the robot. Continuous intents
(move, head, pose, mouth) are notifications (no id) that expire after 150 ms, so a Ticker resends them at 25 Hz.

    python3 duck_rpc.py check                     # read-only: hello + robot.health + one robot.state
    python3 duck_rpc.py say inquire               # one bank sound
    python3 duck_rpc.py look 0.5                  # head yaw 0.5 rad for 2 s (through the policy)
    python3 duck_rpc.py --dry play                # print the encounter timeline instead of sending it
    python3 duck_rpc.py play                      # the whole scene on the robot (be next to it!)

Stdlib only (runs with the system python3). Everything is logged with timestamps to stdout.
"""
import argparse, json, math, socket, subprocess, sys, threading, time

API_VERSION = 16
HOST = "microduck"
SOCK = "/run/robotd.sock"


class Robot:
    def __init__(self, dry=False, transport=None, local_socket=None):
        self.dry = dry
        self.next_id = 1
        self.lock = threading.Lock()
        self.proc = None
        self.sock = None
        if dry:
            return
        if local_socket:                                   # test against a local fake daemon
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(local_socket)
            self.rd = self.sock.makefile("r")
            self.wr = self.sock.makefile("w")
        else:
            cmd = transport or ["ssh", "-o", "ConnectTimeout=8", HOST, f"socat - UNIX-CONNECT:{SOCK} || nc -U {SOCK}"]
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            self.rd, self.wr = self.proc.stdout, self.proc.stdin
        r = self.call("hello", {"api_version": API_VERSION})
        print("hello ->", r)

    # --- wire ---
    def _send(self, obj):
        line = json.dumps(obj, separators=(",", ":"))
        if self.dry:
            print(f"{time.time() % 1000:8.3f}  {line}")
            return
        with self.lock:
            self.wr.write(line + "\n")
            self.wr.flush()

    def notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def call(self, method, params=None, timeout=5.0):
        if self.dry:
            self._send({"jsonrpc": "2.0", "id": 0, "method": method, **({"params": params} if params is not None else {})})
            return None
        rid = self.next_id
        self.next_id += 1
        req = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            req["params"] = params
        self._send(req)
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self.rd.readline()
            if not line:
                raise RuntimeError("connection closed")
            msg = json.loads(line)
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result")
            # notifications (robot.state ...) are ignored here
        raise TimeoutError(method)

    # --- intents ---
    def move(self, vx=0.0, vy=0.0, vyaw=0.0):
        self.notify("robot.move", {"vx": vx, "vy": vy, "vyaw": vyaw})

    def head(self, neck_pitch=0.0, head_pitch=0.0, head_yaw=0.0, head_roll=0.0):
        self.notify("robot.head", {"neck_pitch": neck_pitch, "head_pitch": head_pitch, "head_yaw": head_yaw, "head_roll": head_roll})

    def pose(self, z=0.0, roll=0.0, pitch=0.0, active=True):
        self.notify("robot.pose", {"z": z, "roll": roll, "pitch": pitch, "active": active})

    def mouth(self, open_=0.0):
        self.notify("robot.mouth", {"open": open_})

    def sound(self, tag, hold=None):
        p = {"tag": tag}
        if hold is not None:
            p["hold"] = hold
        return self.call("robot.sound", p)

    def do(self, skill):
        return self.call("robot.do", {"skill": skill})

    def stop(self):
        return self.call("robot.stop")

    def enable(self, on=True):
        return self.call("robot.enable", {"on": on})

    def init(self):
        return self.call("robot.init", timeout=15)

    def relax(self):
        return self.call("robot.relax")

    def health(self):
        return self.call("robot.health")

    def close(self):
        if self.proc:
            self.proc.stdin.close()
            self.proc.terminate()
        if self.sock:
            self.sock.close()


class Ticker(threading.Thread):
    """Resends the continuous intents at 25 Hz (they expire after 150 ms). Set .twist/.head/.pose/.mouth."""
    def __init__(self, robot, hz=25.0):
        super().__init__(daemon=True)
        self.r, self.dt = robot, 1.0 / hz
        self.twist = [0.0, 0.0, 0.0]
        self.headv = [0.0, 0.0, 0.0, 0.0]
        self.posev = None            # None = not active
        self.mouthv = 0.0
        self.alive = True

    def run(self):
        while self.alive:
            self.r.move(*self.twist)
            self.r.head(*self.headv)
            if self.posev is not None:
                self.r.pose(*self.posev)
            self.r.mouth(self.mouthv)
            time.sleep(self.dt)


# ---------------------------------------------------------------------------------------------------------------
# The scene, open loop (no localisation on the robot): durations come from the sim run (v4).
# The sim's closed-loop approach took 5.5 s at 0.4 m/s from 1.15 m; the circle 7 s; the close-in 2.8 s.
# Start the duck ~1 m in front of Reachy Mini, facing it.
# ---------------------------------------------------------------------------------------------------------------
def play(r, log):
    T = Ticker(r)
    tk = T if not r.dry else T           # in dry mode the ticker prints a lot: keep it silent
    t0 = time.time()

    def at(s):
        return time.time() - t0 >= s

    def hold(seconds, twist=None, head=None, pose=None, mouth=None, note=""):
        if twist is not None: T.twist = list(twist)
        if head is not None: T.headv = list(head)
        if pose is not None: T.posev = None if pose is False else list(pose)
        if mouth is not None: T.mouthv = mouth
        log(f"{time.time() - t0:6.2f}s  {note or ''}  twist={T.twist} head={T.headv} pose={T.posev} mouth={T.mouthv}")
        if r.dry:
            r.move(*T.twist); r.head(*T.headv)
            if T.posev is not None: r.pose(*T.posev)
            r.mouth(T.mouthv)
            time.sleep(min(seconds, 0.05))
        else:
            time.sleep(seconds)

    if not r.dry:
        T.start()
    r.enable(True)
    hold(1.0, twist=(0, 0, 0), head=(0, 0, 0, 0), note="stand")
    # 1. approach, curious head-bob, then look at it
    r.sound("chirp")
    for k in range(11):                                   # 5.5 s at 0.4 m/s with a 1.6 Hz nod
        hold(0.5, twist=(0.4, 0, 0), head=(0, -0.25 * (k % 2), 0, 0), note="approach")
    hold(0.6, twist=(0, 0, 0), head=(-0.8, 0, 0, 0), note="stop, look down at it")
    r.sound("inquire")
    hold(1.4, head=(-0.8, 0, 0, 0.3), note="head tilt ?")
    hold(1.0, head=(-0.8, 0, 0, -0.3), note="head tilt other side")
    # 2. circle it clockwise (strafe right + a yaw to keep facing it)
    hold(7.0, twist=(0, -0.5, -0.5), head=(-0.6, 0, 0, 0), note="circle")
    hold(0.5, twist=(0, 0, 0), note="stop")
    r.sound("inquire")
    hold(1.2, head=(-0.8, 0.3, 0, -0.3), note="??")
    # 3. close in and peck three times (bows through the stand policy)
    hold(2.0, twist=(0.3, 0, 0), head=(0, 0, 0, 0), note="close in")
    hold(0.5, twist=(0, 0, 0), note="stop")
    for k in range(3):
        r.sound("peck")
        hold(0.35, pose=(0, 0, 0.3), head=(0, -0.6, 0, 0), note=f"peck {k + 1}")
        hold(0.6, pose=(0, 0, 0), head=(0, 0, 0, 0), note="up")
    hold(0.4, pose=False, note="pecks done")
    # 4. (Reachy Mini wakes up here: chime + line from the Mac, see encounter.events.json)
    log("REACHY WAKES: play the chime + 'Oh. Hello.' now")
    hold(2.4, note="wait for Reachy")
    # 5. scream, jump back, collapse
    r.sound("alarm")
    hold(0.45, mouth=1.0, head=(0, 1.0, 0, 0), pose=(0, 0, -0.25), note="scream")
    hold(1.1, twist=(-0.8, 0, 0), pose=False, note="jump back")
    hold(0.05, twist=(0, 0, 0), head=(0, 0, 0, 0), mouth=0.0)
    r.relax()
    log("RELAXED (motors off): collapsed")
    hold(3.5, note="lies there; Reachy: 'Sorry. Did I scare you?'")
    # 6. get up: power on then the sit-stand rise
    r.init()
    log("init done (ramp to home)")
    hold(0.5)
    r.do("sit_toggle")                                    # if the robot thinks it stands, this SITS; toggle again to rise
    hold(3.5, note="rise")
    for k in range(4):                                    # shake it off
        hold(0.17, head=(0, 0, 0.6 * (1 if k % 2 == 0 else -1) * (1 - k / 5), 0), note="shake")
    hold(1.6, twist=(-0.35, 0, 0.22), head=(0, 0, 0, 0), note="wary step back")
    hold(0.6, twist=(0, 0, 0), head=(-0.3, 0, 0, 0), note="look at it")
    # 7. dialogue (Reachy lines from the Mac; the duck quacks are its own chirps)
    for _ in range(4):
        r.sound("chirp"); hold(0.25)
    r.sound("inquire")
    hold(0.9, head=(-0.3, 0, 0, 0.28), note="head tilt")
    hold(0.9, head=(-0.3, 0, 0, 0), note="")
    hold(2.6, note="Reachy: 'I am Reachy Mini. I was sleeping.'")
    r.sound("coo")
    hold(1.5, head=(-1.0, 0, 0, 0), note="sheepish, look down")
    hold(2.3, note="Reachy: 'You pecked me. Three times.'")
    r.sound("coo")
    hold(1.3, note="...quack")
    hold(3.4, head=(-0.3, 0, 0, 0), note="Reachy: 'It's okay. I'm a robot too. Nice legs, by the way.'")
    r.sound("greet")
    for k in range(2):
        hold(0.25, head=(0, 0.8, 0, 0), note="happy nod")
        hold(0.25, head=(0, 0.0, 0, 0))
    hold(0.3, head=(0, 0, 0, 0))
    r.do("kick_right")
    hold(1.3, note="kick (show off)")
    hold(1.5, head=(-0.3, 0, 0, 0), note="Reachy: 'Show-off.'")
    r.sound("wheee", hold=True)
    for _ in range(20):
        r.sound("wheee", hold=True); hold(0.05)
    r.sound("wheee", hold=False)
    hold(1.0, note="end")
    T.alive = False
    r.stop()


def fake_daemon(path):
    """A local stand-in for robotd: answers hello/calls, swallows notifications. For testing the client."""
    import os
    if os.path.exists(path):
        os.unlink(path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)
    conn, _ = srv.accept()
    rd, wr = conn.makefile("r"), conn.makefile("w")
    n = 0
    for line in rd:
        msg = json.loads(line)
        n += 1
        if "id" in msg:
            res = {"api_version": API_VERSION} if msg["method"] == "hello" else {"ok": True, "method": msg["method"]}
            wr.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": res}) + "\n")
            wr.flush()
    print("fake daemon: received", n, "messages")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "say", "look", "play", "fake"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--local", default=None, help="unix socket of a fake daemon (fake mode creates it)")
    a = ap.parse_args()
    if a.cmd == "fake":
        fake_daemon(a.arg or "/tmp/fake_robotd.sock")
        return
    r = Robot(dry=a.dry, local_socket=a.local)
    log = lambda s: print(s, flush=True)
    try:
        if a.cmd == "check":
            print("health ->", json.dumps(r.health(), indent=1)[:1500])
        elif a.cmd == "say":
            print(r.sound(a.arg or "chirp"))
        elif a.cmd == "look":
            T = Ticker(r); T.headv = [0, 0, float(a.arg or 0.5), 0]
            T.start(); time.sleep(2.0); T.headv = [0, 0, 0, 0]; time.sleep(0.5); T.alive = False
        elif a.cmd == "play":
            play(r, log)
    finally:
        r.close()


if __name__ == "__main__":
    main()
