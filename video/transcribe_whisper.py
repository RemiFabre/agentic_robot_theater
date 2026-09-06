import json, sys
from faster_whisper import WhisperModel
model = WhisperModel("medium", device="cpu", compute_type="int8")
def run(path, prompt=None):
    segs, info = model.transcribe(path, language="en", beam_size=5, word_timestamps=True,
                                  condition_on_previous_text=False, initial_prompt=prompt)
    words = []
    for s in segs:
        for w in s.words:
            words.append([w.word.strip(), round(w.start, 3), round(w.end, 3), round(w.probability, 2)])
    return words
out = {}
out["video"] = run("samples/audio16k.wav", "Hey, Microduck! Look, I have to talk to you. But why? Are you scared?")
SCENE = "/Users/remi/reachy_mini_apps/agentic_robot_theater/scenes/lake/audio"
for n in ["hey", "talk", "bad_news", "excuse", "not_scared"]:
    out[n] = run(f"{SCENE}/{n}.wav")
json.dump(out, open("whisper_words.json", "w"), indent=1)
for k, v in out.items():
    print("==", k); print(" ".join(f"{w}[{s}]" for w, s, e, p in v))
