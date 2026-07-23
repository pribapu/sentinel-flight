"""PX4 offboard controller node.

The ONLY node that talks to PX4 directly. Runs the standard PX4 offboard
handshake (stream setpoints, switch to OFFBOARD, arm) and forwards whatever
setpoint safety_gate_node last approved on /sentinelflight/safe_setpoint
straight to PX4 -- "mission planner proposes, safety gate disposes"
(docs/architecture.md), now true across real ROS 2 node boundaries rather
than a single in-process call chain (Phase 4).

Landing trigger: lands on whichever comes first of (a) mission_manager_node
reporting MissionState.LAND on /sentinelflight/mission_land_requested (real,
perception-driven landing, Phase 5) or (b) the pragmatic hold-duration
timer inherited from Phase 2/3 (a fallback so the vehicle doesn't hover
forever if no landing target is ever found) -- see docs/roadmap.md
"Phase 5 notes".

Requires ROS 2 Humble, px4_msgs, sentinel_flight_msgs, and a running PX4
SITL/Gazebo instance bridged to ROS 2 via the Micro XRCE-DDS Agent. See
docs/roadmap.md.

Reference: PX4 ROS 2 offboard control example --
https://docs.px4.io/main/en/ros2/offboard_control
"""

from __future__ import annotations

import time

import rclpy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleLocalPosition
from rclpy.node import Node
from sentinel_flight_msgs.msg import Setpoint as SetpointMsg
from std_msgs.msg import Bool

from sentinel_flight_control.mission_manager import TAKEOFF_ALTITUDE_M, TAKEOFF_ALTITUDE_TOLERANCE_M
from sentinel_flight_control.ros_interfaces import (
    MISSION_LAND_REQUESTED_TOPIC,
    PX4_QOS,
    PX4_TOPIC_OFFBOARD_CONTROL_MODE,
    PX4_TOPIC_TRAJECTORY_SETPOINT,
    PX4_TOPIC_VEHICLE_COMMAND,
    PX4_TOPIC_VEHICLE_LOCAL_POSITION,
    SAFE_SETPOINT_TOPIC,
)
from sentinel_flight_control.safety_gate import Setpoint

HOLD_DURATION_S = 10.0
# PX4 requires setpoints streaming for a short period before it will accept
# a switch into OFFBOARD mode.
SETPOINTS_BEFORE_OFFBOARD = 10


class OffboardController(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_offboard_controller")

        self.offboard_control_mode_pub = self.create_publisher(
            OffboardControlMode, PX4_TOPIC_OFFBOARD_CONTROL_MODE, PX4_QOS
        )
        self.trajectory_setpoint_pub = self.create_publisher(
            TrajectorySetpoint, PX4_TOPIC_TRAJECTORY_SETPOINT, PX4_QOS
        )
        self.vehicle_command_pub = self.create_publisher(VehicleCommand, PX4_TOPIC_VEHICLE_COMMAND, PX4_QOS)

        self.create_subscription(
            VehicleLocalPosition, PX4_TOPIC_VEHICLE_LOCAL_POSITION, self._on_local_position, PX4_QOS
        )
        self.create_subscription(SetpointMsg, SAFE_SETPOINT_TOPIC, self._on_safe_setpoint, 10)
        self.create_subscription(Bool, MISSION_LAND_REQUESTED_TOPIC, self._on_mission_land_requested, 10)

        self.vehicle_local_position = VehicleLocalPosition()
        # Safe default before safety_gate_node's first message arrives --
        # PX4 ignores it anyway pre-OFFBOARD, same as today's pre-offboard streaming.
        self.latest_safe_setpoint = Setpoint(x=0.0, y=0.0, z=0.0)
        self.setpoint_count = 0
        self._hold_started_at: float | None = None
        self._land_commanded = False
        self._mission_land_requested = False

        self.create_timer(0.1, self._tick)  # 10 Hz

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.vehicle_local_position = msg

    def _on_safe_setpoint(self, msg: SetpointMsg) -> None:
        self.latest_safe_setpoint = Setpoint(x=msg.x, y=msg.y, z=msg.z, vx=msg.vx, vy=msg.vy, vz=msg.vz)

    def _on_mission_land_requested(self, msg: Bool) -> None:
        self._mission_land_requested = msg.data

    def _tick(self) -> None:
        self._publish_offboard_heartbeat()

        if self.setpoint_count == SETPOINTS_BEFORE_OFFBOARD:
            self._engage_offboard_mode()
            self._arm()
        if self.setpoint_count < SETPOINTS_BEFORE_OFFBOARD + 1:
            self.setpoint_count += 1

        self._publish_setpoint(self.latest_safe_setpoint)
        self._maybe_trigger_land()

    def _maybe_trigger_land(self) -> None:
        if self._land_commanded:
            return

        if self._mission_land_requested:
            self._land()
            self._land_commanded = True
            return

        # Fallback: no landing target ever found, land anyway rather than
        # hover forever draining battery.
        current_altitude = -self.vehicle_local_position.z  # PX4 NED -> altitude-up
        if self._hold_started_at is None:
            if current_altitude >= TAKEOFF_ALTITUDE_M - TAKEOFF_ALTITUDE_TOLERANCE_M:
                self._hold_started_at = time.time()
            return
        if time.time() - self._hold_started_at >= HOLD_DURATION_S:
            self._land()
            self._land_commanded = True

    def _publish_offboard_heartbeat(self) -> None:
        msg = OffboardControlMode()
        msg.position = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_pub.publish(msg)

    def _publish_setpoint(self, setpoint: Setpoint) -> None:
        msg = TrajectorySetpoint()
        msg.position = [setpoint.x, setpoint.y, -setpoint.z]  # altitude-up -> PX4 NED
        msg.yaw = 0.0
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.trajectory_setpoint_pub.publish(msg)

    def _arm(self) -> None:
        self._send_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=1.0)
        self.get_logger().info("Arm command sent")

    def _engage_offboard_mode(self) -> None:
        self._send_vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, param1=1.0, param2=6.0)
        self.get_logger().info("Switching to offboard mode")

    def _land(self) -> None:
        # Handed off to PX4's native AUTO_LAND mode (VEHICLE_CMD_NAV_LAND)
        # rather than commanded via offboard position setpoints -- landing
        # needs to command altitudes below SafetyLimits.min_altitude_m,
        # which safety_gate_node correctly refuses as a position setpoint
        # (the Phase 2 landing-altitude bug). PX4's own AUTO_LAND mode owns
        # touchdown detection and disarm, matching PX4's reference ROS 2
        # offboard control example.
        self._send_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.get_logger().info("Switching to land mode")

    def _send_vehicle_command(self, command: int, **params: float) -> None:
        msg = VehicleCommand()
        msg.command = command
        msg.param1 = params.get("param1", 0.0)
        msg.param2 = params.get("param2", 0.0)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.vehicle_command_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = OffboardController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
