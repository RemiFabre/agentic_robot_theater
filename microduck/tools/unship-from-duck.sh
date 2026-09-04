#!/usr/bin/env bash
# Put the robot back to the shipped release binaries after ship-to-duck.sh.
#
#   /Users/remi/microduck/notes/reachy-encounter/unship-from-duck.sh [microduck@192.168.1.29]
#
# ship-to-duck.sh keeps a `<bin>.orig` beside every binary it replaces, inside the release directory
# (/opt/robot/daemon/releases/<version>/bin/). This moves them back and restarts the services.
# Nothing else on the board was touched by the ship, so this IS the default state again.
#
# If ssh is impossible for some reason, the same lines run on the robot's own shell as root.
set -euo pipefail
BOARD="${1:-microduck@192.168.1.29}"
ssh -t "$BOARD" 'set -e
REL=$(readlink -f /opt/robot/daemon/current)
echo "release dir: $REL"
sudo sh -c "set -e
  systemctl stop padd robotd
  for b in robotd padd robotctl btd; do
    if [ -f $REL/bin/\$b.orig ]; then mv -f $REL/bin/\$b.orig $REL/bin/\$b; echo restored \$b; else echo \"no backup for \$b (already original)\"; fi
  done
  systemctl start robotd
  sleep 2
  systemctl start padd
  systemctl restart btd"
sleep 2
robotctl version | head -3
systemctl is-active robotd padd btd'
