"""Mux the scene's spoken lines under a record_windows.py video, at the times the player started them.

    python robot/mux_lines.py <video.mp4> <timeline.jsonl> <out.mp4>

video.mp4.json (sidecar from record_windows.py) gives the epoch of frame 0 and the real capture rate; the
timeline (skit_duo.py --timeline-out) gives each line's wav and epoch start. The video is re-timed to the real
capture rate first (ffmpeg stamps the raw frames at the asked rate), then each wav is delayed and mixed.
"""
import json, os, subprocess, sys


def main():
    video, timeline, out = sys.argv[1:4]
    side = json.load(open(video + ".json"))
    lines = [json.loads(l) for l in open(timeline) if l.strip()]
    lines = [l for l in lines if 0 <= l["epoch"] - side["epoch0"] < side["seconds"]]
    speed = side["fps_real"] / side["fps_asked"]  # < 1: frames were captured slower than stamped
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video]
    fc = [f"[0:v]setpts=PTS/{speed:.6f}[v]"]
    for i, l in enumerate(lines, start=1):
        cmd += ["-i", l["wav"]]
        ms = int(round((l["epoch"] - side["epoch0"]) * 1000))
        fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=mono,adelay={ms}|{ms}[a{i}]")
    if lines:
        fc.append("".join(f"[a{i}]" for i in range(1, len(lines) + 1)) + f"amix=inputs={len(lines)}:normalize=0:duration=longest[a]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-filter_complex", fc[0], "-map", "[v]"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-t", f"{side['seconds']:.2f}", out]
    subprocess.run(cmd, check=True)
    print(f"muxed {len(lines)} lines ({', '.join(l['id'] for l in lines)}) -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
