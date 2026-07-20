#!/usr/bin/env bash
# Build the ROS 2 workspace and launch the SentinelFlight mission stack
# (mission planner + safety gate + offboard controller + telemetry logger)
# against a running PX4 SITL instance. Requires ROS 2 Humble.
#
# NOT YET WIRED UP — nodes referenced here are design stubs until the
# Phase 2/3/6 roadmap items are implemented. See docs/roadmap.md.
set -euo pipefail

cd "$(dirname "$0")/../ros2_ws"
colcon build --symlink-install
source install/setup.bash

ros2 launch sentinel_flight_control mission.launch.py
