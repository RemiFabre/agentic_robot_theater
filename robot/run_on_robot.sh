#!/bin/zsh
# Sync the player + a scene (scene.json + audio/) to the robot and run it interactively.
# Usage: robot/run_on_robot.sh scenes/<name> [--start-delay N] [--from-beat K] [--no-sleep]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SCENE="$1"; shift
NAME="$(basename "$SCENE")"
ROBOT="${ROBOT:-pollen@reachy-mini.local}"
ssh "$ROBOT" "mkdir -p ~/theater/scenes/$NAME/audio"
scp -q "$HERE/skit.py" "$ROBOT:~/theater/"
scp -q "$SCENE/scene.json" "$ROBOT:~/theater/scenes/$NAME/"
scp -q "$SCENE"/audio/*.wav "$ROBOT:~/theater/scenes/$NAME/audio/"
exec ssh -t "$ROBOT" "cd ~/theater && HF_HUB_OFFLINE=1 /venvs/apps_venv/bin/python skit.py scenes/$NAME $* 2>~/theater/skit.err"
