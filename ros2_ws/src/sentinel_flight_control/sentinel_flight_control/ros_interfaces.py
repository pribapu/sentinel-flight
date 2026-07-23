"""Shared PX4/SentinelFlight ROS 2 wiring constants.

Single source of truth for the QoS profile, topic names, and the
quaternion helper used across mission_manager_node.py, safety_gate_node.py,
offboard_controller.py, and telemetry_logger_node.py, so the Phase 4 node
split doesn't end up with four copies of the same constants.
"""

from __future__ import annotations

import math

from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

PX4_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

# PX4 topics -- version-suffixed per the live SITL instance (see
# docs/roadmap.md "Phase 2 notes"): this checkout publishes v1/v4 variants
# rather than the unversioned names shown in PX4's example docs.
PX4_TOPIC_VEHICLE_LOCAL_POSITION = "/fmu/out/vehicle_local_position_v1"
PX4_TOPIC_VEHICLE_STATUS = "/fmu/out/vehicle_status_v4"
PX4_TOPIC_BATTERY_STATUS = "/fmu/out/battery_status_v1"
PX4_TOPIC_VEHICLE_ATTITUDE = "/fmu/out/vehicle_attitude"
PX4_TOPIC_OFFBOARD_CONTROL_MODE = "/fmu/in/offboard_control_mode"
PX4_TOPIC_TRAJECTORY_SETPOINT = "/fmu/in/trajectory_setpoint"
PX4_TOPIC_VEHICLE_COMMAND = "/fmu/in/vehicle_command"

# Just the nav_states relevant to this mission; anything else logs as its
# raw integer value rather than growing this map to cover PX4's full enum.
NAV_STATE_NAMES = {
    0: "MANUAL",
    14: "OFFBOARD",
    17: "AUTO_TAKEOFF",
    18: "AUTO_LAND",
}

# SentinelFlight-internal topics (docs/architecture.md).
PROPOSED_SETPOINT_TOPIC = "/sentinelflight/proposed_setpoint"
SAFE_SETPOINT_TOPIC = "/sentinelflight/safe_setpoint"
SAFETY_EVENT_TOPIC = "/sentinelflight/safety_event"
PERCEPTION_STATUS_TOPIC = "/sentinelflight/perception_status"  # no publisher until Phase 5


def quaternion_to_euler(q: list[float]) -> tuple[float, float, float]:
    """Hamilton (w, x, y, z) quaternion -> (roll, pitch, yaw) in radians."""
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw
