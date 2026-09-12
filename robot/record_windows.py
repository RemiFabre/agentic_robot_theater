"""Record the two MuJoCo windows side by side, even when they overlap on screen.

macOS puts both sim windows at the same spot and moving them needs assistive access (osascript cannot without it),
so a plain screen recording shows one robot. This grabs each window by its CGWindowID (Quartz captures the backing
store, occluded or not), lays them side by side (loretta left, husband right) and pipes raw frames to ffmpeg.
Needs pyobjc-framework-Quartz (a scratch venv: `uv venv qz && uv pip install --python qz/bin/python
pyobjc-framework-Quartz`) and Screen Recording permission for the terminal.

    qz/bin/python robot/record_windows.py --seconds 20 --fps 15 --out scenes/couple_fight/sim_v5.mp4 --label "wobbler v5"

Window ids: auto (the mjpython windows named "MuJoCo : scene", ordered by owner pid = launch order, loretta first)
or --left ID --right ID. --audio FILE muxes a wav (e.g. the scene mix) under the video.
"""
import argparse, os, subprocess, sys, time

import Quartz
from Quartz import CoreGraphics as CG


def mujoco_windows():
    wl = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
    ws = [w for w in wl if str(w.get("kCGWindowOwnerName", "")) == "mjpython" and "MuJoCo" in str(w.get("kCGWindowName", ""))]
    ws.sort(key=lambda w: w["kCGWindowOwnerPID"])
    return [(int(w["kCGWindowNumber"]), int(w["kCGWindowOwnerPID"]), dict(w["kCGWindowBounds"])) for w in ws]


def grab(wid):
    return CG.CGWindowListCreateImage(CG.CGRectNull, CG.kCGWindowListOptionIncludingWindow, wid,
                                      CG.kCGWindowImageBoundsIgnoreFraming | CG.kCGWindowImageNominalResolution
                                      | CG.kCGWindowImageShouldBeOpaque)


class Canvas:
    def __init__(self, w, h, label=""):
        self.w, self.h, self.label = w, h, label
        cs = CG.CGColorSpaceCreateDeviceRGB()
        self.ctx = CG.CGBitmapContextCreate(None, w, h, 8, w * 4, cs,
                                            CG.kCGImageAlphaPremultipliedFirst | CG.kCGBitmapByteOrder32Little)
        CG.CGContextSelectFont(self.ctx, b"Helvetica-Bold", 34, CG.kCGEncodingMacRoman)
        CG.CGContextSetTextDrawingMode(self.ctx, CG.kCGTextFill)

    def frame(self, left, right):
        ctx = self.ctx
        CG.CGContextSetRGBFillColor(ctx, 0, 0, 0, 1); CG.CGContextFillRect(ctx, CG.CGRectMake(0, 0, self.w, self.h))
        lw, lh = CG.CGImageGetWidth(left), CG.CGImageGetHeight(left)
        rw, rh = CG.CGImageGetWidth(right), CG.CGImageGetHeight(right)
        CG.CGContextDrawImage(ctx, CG.CGRectMake(0, self.h - lh, lw, lh), left)
        CG.CGContextDrawImage(ctx, CG.CGRectMake(self.w // 2, self.h - rh, rw, rh), right)
        for x, text in ((20, f"LORETTA  {self.label}"), (self.w // 2 + 20, f"HUSBAND  {self.label}")):
            CG.CGContextSetRGBFillColor(ctx, 0, 0, 0, 0.6)
            CG.CGContextFillRect(ctx, CG.CGRectMake(x - 10, self.h - 70, 20 * len(text) + 20, 52))
            CG.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
            CG.CGContextShowTextAtPoint(ctx, x, self.h - 56, text.encode("mac_roman"), len(text))
        img = CG.CGBitmapContextCreateImage(ctx)
        return bytes(CG.CGDataProviderCopyData(CG.CGImageGetDataProvider(img)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--fps", type=float, default=12.0, help="window capture costs ~30 ms each, so ~12 fps is the ceiling")
    ap.add_argument("--out", required=True)
    ap.add_argument("--left", type=int); ap.add_argument("--right", type=int)
    ap.add_argument("--label", default="")
    ap.add_argument("--audio", default=None, help="wav to mux under the video (trimmed to the recording)")
    a = ap.parse_args()
    if a.left and a.right:
        ids = [a.left, a.right]
    else:
        ws = mujoco_windows()
        if len(ws) < 2:
            print(f"!!! need two MuJoCo windows, found {ws}"); return 1
        ids = [ws[0][0], ws[1][0]]
        print(f"windows: left {ws[0]} right {ws[1]}")
    li, ri = grab(ids[0]), grab(ids[1])
    w1 = max(CG.CGImageGetWidth(li), CG.CGImageGetWidth(ri))
    h = max(CG.CGImageGetHeight(li), CG.CGImageGetHeight(ri))
    w1 -= w1 % 2; h -= h % 2
    canvas = Canvas(2 * w1, h, a.label)
    vf = "format=yuv420p"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{2 * w1}x{h}", "-r", f"{a.fps}", "-i", "-"]
    if a.audio:
        cmd += ["-i", a.audio, "-shortest", "-c:a", "aac"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n, t0, period = 0, time.monotonic(), 1.0 / a.fps
    epoch0 = time.time()
    try:
        while time.monotonic() - t0 < a.seconds:
            li, ri = grab(ids[0]), grab(ids[1])
            if li is None or ri is None:
                print("!!! a window vanished"); break
            ff.stdin.write(canvas.frame(li, ri)); n += 1
            d = t0 + n * period - time.monotonic()
            if d > 0:
                time.sleep(d)
    finally:
        ff.stdin.close(); ff.wait()
    el = time.monotonic() - t0
    print(f"{n} frames in {el:.1f}s (asked {a.fps} fps, got {n / el:.1f}); wrote {a.out} ({os.path.getsize(a.out) / 1e6:.1f} MB)")
    # sidecar for mux_lines.py: when frame 0 was grabbed, and the real frame rate (frames are timestamped at a.fps
    # by ffmpeg, so a slow capture plays back sped up by fps_asked / fps_real; the sidecar carries both)
    import json
    json.dump({"epoch0": epoch0, "fps_asked": a.fps, "fps_real": n / el, "frames": n, "seconds": el},
              open(a.out + ".json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
