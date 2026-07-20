"""PX4 offboard controller node (interface stub).

Status: NOT YET IMPLEMENTED. Requires ROS 2 Humble + PX4 SITL running
(Ubuntu 22.04 or WSL2 — see docs/roadmap.md Phase 1-2). Depends on rclpy,
which is not installable on this development machine, so this module is
intentionally import-guarded and excluded from the pytest suite.

Design contract (see docs/architecture.md):
    - The ONLY node allowed to talk to PX4.
    - Subscribes to /sentinelflight/safe_setpoint — the output of
      safety_gate.SafetyGate — never to a raw AI/mission-planner topic.
    - Responsible for the PX4 offboard handshake: stream setpoints, switch
      to OFFBOARD mode, arm, then forward each approved setpoint.

Planned ROS 2 topics:
    Subscribes:
        /sentinelflight/safe_setpoint
    Publishes:
        /fmu/in/trajectory_setpoint   (px4_msgs/TrajectorySetpoint)
        /fmu/in/vehicle_command       (px4_msgs/VehicleCommand)

Reference: PX4 ROS 2 offboard control example —
https://docs.px4.io/main/en/ros2/offboard_control
"""

from __future__ import annotations

try:
    import rclpy  # noqa: F401
except ImportError as exc:  # pragma: no cover - expected on non-ROS2 hosts
    raise ImportError(
        "offboard_controller requires ROS 2 (rclpy). Run this node from a "
        "ROS 2 Humble environment on Ubuntu 22.04 / WSL2 — see docs/roadmap.md."
    ) from exc


class OffboardController:
    """TODO(week-2): implement PX4 offboard handshake per docs/roadmap.md Phase 2.

    Required sequence (from the PX4 ROS 2 offboard control example):
        1. Wait for PX4 connection.
        2. Stream setpoints at >2Hz before switching modes (PX4 requirement).
        3. Send VehicleCommand to switch to OFFBOARD mode.
        4. Arm the vehicle.
        5. Forward each /sentinelflight/safe_setpoint message as a
           TrajectorySetpoint.
    """

    def __init__(self):
        raise NotImplementedError(
            "OffboardController is a design stub — implement per docs/roadmap.md Phase 2"
        )
