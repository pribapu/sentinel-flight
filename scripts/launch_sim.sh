#!/usr/bin/env bash
# Launch PX4 SITL + Gazebo. Requires Ubuntu 22.04 / WSL2 with ROS 2 Humble
# and PX4-Autopilot cloned as a sibling directory. See docs/roadmap.md
# Phase 1 for the full setup sequence.
#
# NOT YET WIRED UP — placeholder for the Phase 1 milestone.
set -euo pipefail

PX4_DIR="${PX4_DIR:-../PX4-Autopilot}"

if [ ! -d "$PX4_DIR" ]; then
  echo "PX4-Autopilot not found at $PX4_DIR. Clone it first:" >&2
  echo "  git clone https://github.com/PX4/PX4-Autopilot.git --recursive" >&2
  exit 1
fi

cd "$PX4_DIR"
make px4_sitl gazebo
