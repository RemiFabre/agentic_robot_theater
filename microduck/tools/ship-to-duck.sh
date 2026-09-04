#!/usr/bin/env bash
# Build the robot daemons for the board and install them on the duck WITHOUT the signed updater.
#
#   /Users/remi/microduck/notes/reachy-encounter/ship-to-duck.sh [microduck@192.168.1.29] [--no-build]
#
# What it does, step by step (each step is also runnable by hand):
#   1. Builds robotd, padd, robotctl and btd in Docker, natively for arm64 (this Mac is arm64, so no
#      emulation), against the board's own Debian userland, from the checkout in
#      /Users/remi/microduck/microduck (whatever branch is checked out there).
#   2. Copies the four binaries to ~/duck-sideload/ on the robot over ssh.
#   3. On the robot: stops robotd and padd, replaces the binaries inside the current release
#      directory (/opt/robot/daemon/releases/<version>/bin/, owned by root: sudo asks the password),
#      keeping a .orig copy of each, then starts the services again.
#   4. Prints `robotctl version` and the padd journal line so you can see the new mapping is live.
#
# Why not `scripts/dev-push.sh`: the updater only installs artifacts signed by a trusted key, and the
# team dev secret key is not on this Mac. This script bypasses the updater instead. Consequences:
# the robot's `update status` still says 0.10.0; a future `robotctl update apply` overwrites these
# binaries (that is fine); and `update rollback` would not know about them.
#
# To undo: ssh in and `sudo mv <bin>.orig <bin>` for each, then restart the services.
set -euo pipefail

BOARD="${1:-microduck@192.168.1.29}"
BUILD=yes
[ "${2:-}" = "--no-build" ] && BUILD=no
REPO=/Users/remi/microduck/microduck
BINS="robotd padd robotctl btd"
OUT="$REPO/target/docker/aarch64-unknown-linux-gnu/release"

cd "$REPO"
echo "==> branch $(git branch --show-current) @ $(git rev-parse --short HEAD)"

if [ "$BUILD" = yes ]; then
    echo "==> building $BINS for arm64 in Docker (first build takes minutes, then ~1 min)"
    docker version >/dev/null 2>&1 || { echo "Docker is not running: open -a Docker" >&2; exit 1; }
    docker build -q -t duck-dev-build -f scripts/dev-build.Dockerfile scripts/ >/dev/null
    docker run --rm --platform linux/arm64 \
        -v "$PWD:/src" -w /src \
        -v duck-dev-cargo-registry:/usr/local/cargo/registry \
        -e CARGO_TARGET_DIR=/src/target/docker \
        -e DUCK_REVISION="$(git rev-parse --short HEAD)-local" \
        duck-dev-build \
        cargo build --release --target aarch64-unknown-linux-gnu $(for b in $BINS; do printf -- '-p %s ' "$b"; done)
fi

for b in $BINS; do
    file "$OUT/$b" | grep -q "ARM aarch64" || { echo "$OUT/$b is not an arm64 binary" >&2; exit 1; }
done

echo "==> copying to $BOARD:~/duck-sideload/"
ssh "$BOARD" 'mkdir -p ~/duck-sideload'
scp -q $(for b in $BINS; do printf '%s ' "$OUT/$b"; done) "$BOARD:duck-sideload/"

echo "==> installing on the robot (sudo will ask for the robot's password)"
# -t: a terminal for sudo's password prompt. The release dir is resolved on the board from the
# `current` symlink, so this follows whatever release is installed.
ssh -t "$BOARD" 'set -e
REL=$(readlink -f /opt/robot/daemon/current)
SRC=$HOME/duck-sideload
echo "release dir: $REL"
sudo sh -c "set -e
  systemctl stop padd robotd
  for b in '"$BINS"'; do
    [ -f $REL/bin/\$b.orig ] || cp -p $REL/bin/\$b $REL/bin/\$b.orig
    install -m 0755 -o root -g root $SRC/\$b $REL/bin/\$b
  done
  systemctl start robotd
  sleep 2
  systemctl start padd
  systemctl restart btd"
sleep 2
robotctl version | head -3
systemctl is-active robotd padd btd
journalctl -u padd -b --no-pager | tail -2'
echo "==> done. Press Start on the pad as usual; Select = soft release; LB curious; RB peck."
