#!/bin/zsh
# Plays every voice candidate, announcing it first. Ctrl+C to stop.
cd "$(dirname "$0")"
for f in loretta_a/design_*.mp3 loretta_b/design_*.mp3 husband_a/design_*.mp3 husband_b/design_*.mp3; do
  say "${f:h} ${f:t:r:s/design_/}"; afplay "$f"
done
