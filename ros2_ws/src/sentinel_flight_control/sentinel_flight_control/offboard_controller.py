"""PX4 offboard controller node.

The ONLY node that talks to PX4 directly. Runs the standard PX4 offboard
handshake (stream setpoints, switch to OFFBOARD, arm) and, on every control
tick, routes a candidate setpoint through the already-implemented
SafetyGate (safety_gate.py) before it's published to PX4 — "mission planner
proposes, safety gate disposes" (docs/architecture.md), applied for real
against a live flight controller instead of just unit tests.

Mission source for this phase: a minimal built-in takeoff -> hold -> land
sequence, since MissionManager (Phase 6) isn't wired up to a cross-node
setpoint topic yet — that needs a custom ROS 2 message type for Setpoint
that doesn't exist yet (see docs/roadmap.md "Next steps"). AI confidence is
synthesized as a constant high value until the perception node (Phase 5) is
publishing real values.

Requires ROS 2 Humble, px4_msgs, and a running PX4 SITL/Gazebo instance
bridged to ROS 2 via the Micro XRCE-DDS Agent. See docs/roadmap.md.

Reference: PX4 ROS 2 offboard control example —
https://docs.px4.io/main/en/ros2/offboard_control

Note: PX4's uXRCE-DDS bridge publishes version-suffixed topic names
(e.g. /fmu/out/vehicle_status_v4) rather than the unversioned names shown
in the official example docs — confirmed against a running SITL instance
via `ros2 topic list`, not assumed.
"""

from __future__ import annotations

import time

import rclpy
from px4_msgs.msg import (
    BatteryStatus,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from sentinel_flight_control.safety_gate import (
    AIStatus,
    SafetyGate,
    SafetyStatus,
    Setpoint,
    VehicleState,
)

PX4_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

TAKEOFF_ALTITUDE_M = 5.0
HOLD_DURATION_S = 10.0
# PX4 requires setpoints streaming for a short period before it will accept
# a switch into OFFBOARD mode.
SETPOINTS_BEFORE_OFFBOARD = 10


class OffboardController(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_offboard_controller")

        self.offboard_control_mode_pub = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", PX4_QOS
        )
        self.trajectory_setpoint_pub = self.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", PX4_QOS
        )
        self.vehicle_command_pub = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", PX4_QOS
        )

        # Topic names carry PX4's message-version suffix (this checkout
        # publishes v1/v4 variants) — confirmed via `ros2 topic list`/`topic
        # info` against the running SITL instance rather than assumed from
        # the (unversioned) PX4 example docs.
        self.create_subscription(
            VehicleLocalPosition,
            "/fmu/out/vehicle_local_position_v1",
            self._on_local_position,
            PX4_QOS,
        )
        self.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status_v4", self._on_vehicle_status, PX4_QOS
        )
        self.create_subscription(
            BatteryStatus, "/fmu/out/battery_status_v1", self._on_battery_status, PX4_QOS
        )

        self.safety_gate = SafetyGate()
        self.vehicle_local_position = VehicleLocalPosition()
        self.vehicle_status = VehicleStatus()
        self.battery_percent = 100.0
        self.setpoint_count = 0
        self.mission_state = "TAKEOFF"
        self._hold_started_at: float | None = None

        self.create_timer(0.1, self._tick)  # 10 Hz

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.vehicle_local_position = msg

    def _on_vehicle_status(self, msg: VehicleStatus) -> None:
        self.vehicle_status = msg

    def _on_battery_status(self, msg: BatteryStatus) -> None:
        if msg.remaining >= 0.0:
            self.battery_percent = msg.remaining * 100.0

    def _tick(self) -> None:
        self._publish_offboard_heartbeat()

        if self.setpoint_count == SETPOINTS_BEFORE_OFFBOARD:
            self._engage_offboard_mode()
            self._arm()
        if self.setpoint_count < SETPOINTS_BEFORE_OFFBOARD + 1:
            self.setpoint_count += 1

        proposed = self._propose_setpoint()
        vehicle = self._current_vehicle_state()
        # TODO(phase-5): replace with real perception-derived confidence.
        ai = AIStatus(confidence=0.95, last_command_timestamp=time.time())

        decision = self.safety_gate.evaluate(proposed, vehicle, ai)
        if decision.status != SafetyStatus.APPROVED:
            self.get_logger().warn(f"safety_gate: {decision.status.value} - {decision.reason}")

        self._publish_setpoint(decision.setpoint)

    def _propose_setpoint(self) -> Setpoint:
        """Minimal built-in mission: climb to TAKEOFF_ALTITUDE_M, hold, land."""
        current_altitude = -self.vehicle_local_position.z  # PX4 NED -> altitude-up

        if self.mission_state == "TAKEOFF":
            if current_altitude >= TAKEOFF_ALTITUDE_M - 0.3:
                self.mission_state = "HOLD"
                self._hold_started_at = time.time()
            return Setpoint(x=0.0, y=0.0, z=TAKEOFF_ALTITUDE_M)

        if self.mission_state == "HOLD":
            if self._hold_started_at and time.time() - self._hold_started_at >= HOLD_DURATION_S:
                self.mission_state = "LAND"
                self._land()
            return Setpoint(x=0.0, y=0.0, z=TAKEOFF_ALTITUDE_M)

        # LAND: handed off to PX4's native AUTO_LAND mode (VEHICLE_CMD_NAV_LAND)
        # rather than commanded via offboard position setpoints. Landing needs
        # to command altitudes below SafetyLimits.min_altitude_m, which the
        # safety gate correctly refuses as a position setpoint (an early test
        # run confirmed this — safety_gate rejected sub-1m setpoints and hit
        # MISSION_ABORT after 5 rejections). PX4's own AUTO_LAND mode owns
        # touchdown detection and disarm, matching the pattern in PX4's
        # reference ROS 2 offboard control example. Hold the last approved
        # altitude as a harmless setpoint while PX4 transitions out of
        # OFFBOARD.
        return Setpoint(x=self.vehicle_local_position.x, y=self.vehicle_local_position.y, z=TAKEOFF_ALTITUDE_M)

    def _current_vehicle_state(self) -> VehicleState:
        return VehicleState(
            x=self.vehicle_local_position.x,
            y=self.vehicle_local_position.y,
            z=-self.vehicle_local_position.z,
            battery_percent=self.battery_percent,
        )

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
