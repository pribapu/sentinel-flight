#!/usr/bin/env bash
# Launch PX4 SITL + Gazebo. Requires Ubuntu 22.04 / WSL2 with PX4-Autopilot
# cloned as a sibling directory and its setup script run (see
# docs/roadmap.md "Phase 1 notes" for WSL2-specific gotchas: distro version,
# skipping the NuttX toolchain, and why HEADLESS=1 is used below).
#
# Verified working — see docs/evidence/phase1_sitl_gazebo_boot.log for a
# captured boot of this exact command.
set -euo pipefail

PX4_DIR="${PX4_DIR:-../PX4-Autopilot}"
MODEL="${MODEL:-gz_x500}"

if [ ! -d "$PX4_DIR" ]; then
  echo "PX4-Autopilot not found at $PX4_DIR. Clone it first:" >&2
  echo "  git clone https://github.com/PX4/PX4-Autopilot.git --recursive" >&2
  echo "  cd PX4-Autopilot && bash ./Tools/setup/ubuntu.sh --no-nuttx" >&2
  exit 1
fi

cd "$PX4_DIR"
HEADLESS=1 make px4_sitl "$MODEL"
