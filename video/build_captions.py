"""Build captions.json / captions.srt for the lake episode.
Robot lines: start = cross-correlation line start (line_times.json) + whisper word offsets inside the TTS wav.
Human lines: whisper on the footage. All times converted to the trimmed timeline (source - TRIM)."""
import json
TRIM = 2.0
lt = json.load(open("line_times.json")); ww = json.load(open("whisper_words.json"))
def wt(line, i):  # (start,end) of word i of a TTS line, in source time
    w = ww[line][i]; s0 = lt[line]["start"]; return s0 + w[1], s0 + w[2]
PAD = 0.45  # linger after the last word of a chunk
caps = []
def robot(line, i0, i1, text, end_pad=PAD):
    s = wt(line, i0)[0]; e = wt(line, i1)[1] + end_pad
    caps.append({"who": "Reachy Mini", "text": text, "start": s, "end": e})
def human(text, s, e):
    caps.append({"who": "The Human", "text": text, "start": s, "end": e})
robot("hey", 0, 1, "Hey, Microduck!", 0.6)
robot("talk", 0, 6, "Look, I have to talk to you.")
robot("bad_news", 0, 10, "I know you were very excited to go to the lake.")
robot("bad_news", 11, 18, "But we won't be able to go today.")
robot("bad_news", 19, 20, "I'm sorry.", 0.6)
human("But why?", 30.86, 32.6)
robot("excuse", 0, 1, "Because, well...")
robot("excuse", 2, 5, "the meteorological conditions are...")
robot("excuse", 6, 9, "not optimal right now.")
human("But...", 42.3, 43.5)
human("Are you scared?", 48.76, 51.0)
robot("not_scared", 0, 3, "No. I'm not scared.", 0.6)
robot("not_scared", 4, 10, "I'm just optimizing our long-term survivability.")
caps.sort(key=lambda c: c["start"])
for a, b in zip(caps, caps[1:]):  # no overlap: end 50 ms before the next one starts
    if a["end"] > b["start"] - 0.05: a["end"] = b["start"] - 0.05
for c in caps:
    c["start"] = round(c["start"] - TRIM, 3); c["end"] = round(c["end"] - TRIM, 3)
json.dump(caps, open("captions.json", "w"), indent=1)
def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
with open("captions.srt", "w") as f:
    for i, c in enumerate(caps, 1):
        f.write(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['who']}: {c['text']}\n\n")
for c in caps: print(f"{c['start']:6.2f} {c['end']:6.2f}  {c['who']}: {c['text']}")
