"""Telemetry logger node.

Subscribes to PX4 telemetry directly plus all three SentinelFlight topics
(proposed/safe setpoint, safety event) and writes one CSV row per 10 Hz
tick from the cached latest value of each -- same cadence/schema as the
in-process logger it replaces (Phase 3).
"""

from __future__ import annotations

import time

import rclpy
from px4_msgs.msg import VehicleAttitude, VehicleLocalPosition, VehicleStatus
from rclpy.node import Node
from sentinel_flight_msgs.msg import SafetyEvent as SafetyEventMsg
from sentinel_flight_msgs.msg import Setpoint as SetpointMsg

from sentinel_flight_control.ros_interfaces import (
    NAV_STATE_NAMES,
    PROPOSED_SETPOINT_TOPIC,
    PX4_QOS,
    PX4_TOPIC_VEHICLE_ATTITUDE,
    PX4_TOPIC_VEHICLE_LOCAL_POSITION,
    PX4_TOPIC_VEHICLE_STATUS,
    SAFE_SETPOINT_TOPIC,
    SAFETY_EVENT_TOPIC,
    quaternion_to_euler,
)
from sentinel_flight_telemetry.telemetry_logger import TelemetryLogger

# SafetyEvent.msg uint8 -> the exact strings safety_gate.SafetyStatus.value
# uses. Duplicated by hand (rather than importing safety_gate.SafetyStatus)
# so sentinel_flight_telemetry doesn't gain a dependency cycle back onto
# sentinel_flight_control's runtime logic -- see docs/roadmap.md "Phase 4
# notes" for why. Must be kept in sync with sentinel_flight_msgs/msg/SafetyEvent.msg.
_STATUS_NAMES = {
    SafetyEventMsg.STATUS_APPROVED: "APPROVED",
    SafetyEventMsg.STATUS_REJECTED_LOW_CONFIDENCE: "REJECTED_LOW_CONFIDENCE",
    SafetyEventMsg.STATUS_REJECTED_ALTITUDE_LIMIT: "REJECTED_ALTITUDE_LIMIT",
    SafetyEventMsg.STATUS_REJECTED_GEOFENCE: "REJECTED_GEOFENCE",
    SafetyEventMsg.STATUS_REJECTED_MAX_VELOCITY: "REJECTED_MAX_VELOCITY",
    SafetyEventMsg.STATUS_REJECTED_OBSTACLE_PROXIMITY: "REJECTED_OBSTACLE_PROXIMITY",
    SafetyEventMsg.STATUS_FAILSAFE_HOVER: "FAILSAFE_HOVER",
    SafetyEventMsg.STATUS_FAILSAFE_LAND: "FAILSAFE_LAND",
    SafetyEventMsg.STATUS_MISSION_ABORT: "MISSION_ABORT",
}


class TelemetryLoggerNode(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_telemetry_logger")

        self.declare_parameter("csv_path", "logs/mission.csv")
        csv_path = self.get_parameter("csv_path").get_parameter_value().string_value
        self.telemetry = TelemetryLogger(csv_path)

        self.create_subscription(
            VehicleLocalPosition, PX4_TOPIC_VEHICLE_LOCAL_POSITION, self._on_local_position, PX4_QOS
        )
        self.create_subscription(VehicleStatus, PX4_TOPIC_VEHICLE_STATUS, self._on_vehicle_status, PX4_QOS)
        self.create_subscription(VehicleAttitude, PX4_TOPIC_VEHICLE_ATTITUDE, self._on_attitude, PX4_QOS)
        self.create_subscription(SetpointMsg, PROPOSED_SETPOINT_TOPIC, self._on_proposed, 10)
        self.create_subscription(SetpointMsg, SAFE_SETPOINT_TOPIC, self._on_safe, 10)
        self.create_subscription(SafetyEventMsg, SAFETY_EVENT_TOPIC, self._on_safety_event, 10)

        self.vehicle_local_position = VehicleLocalPosition()
        self.vehicle_status = VehicleStatus()
        self.vehicle_attitude = VehicleAttitude()
        self.vehicle_attitude.q = [1.0, 0.0, 0.0, 0.0]  # identity until the first message arrives
        self.latest_proposed = SetpointMsg()
        self.latest_safe = SetpointMsg()
        self.latest_safety_event = SafetyEventMsg()

        self.create_timer(0.1, self._tick)  # 10 Hz

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.vehicle_local_position = msg

    def _on_vehicle_status(self, msg: VehicleStatus) -> None:
        self.vehicle_status = msg

    def _on_attitude(self, msg: VehicleAttitude) -> None:
        self.vehicle_attitude = msg

    def _on_proposed(self, msg: SetpointMsg) -> None:
        self.latest_proposed = msg

    def _on_safe(self, msg: SetpointMsg) -> None:
        self.latest_safe = msg

    def _on_safety_event(self, msg: SafetyEventMsg) -> None:
        self.latest_safety_event = msg

    def _tick(self) -> None:
        roll, pitch, yaw = quaternion_to_euler(list(self.vehicle_attitude.q))
        self.telemetry.log(
            {
                "timestamp": time.time(),
                "x": self.vehicle_local_position.x,
                "y": self.vehicle_local_position.y,
                "z": -self.vehicle_local_position.z,
                "vx": self.vehicle_local_position.vx,
                "vy": self.vehicle_local_position.vy,
                "vz": -self.vehicle_local_position.vz,
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw,
                "flight_mode": NAV_STATE_NAMES.get(
                    self.vehicle_status.nav_state, self.vehicle_status.nav_state
                ),
                "armed_status": self.vehicle_status.arming_state == VehicleStatus.ARMING_STATE_ARMED,
                "proposed_x": self.latest_proposed.x,
                "proposed_y": self.latest_proposed.y,
                "proposed_z": self.latest_proposed.z,
                "approved_x": self.latest_safe.x,
                "approved_y": self.latest_safe.y,
                "approved_z": self.latest_safe.z,
                "ai_confidence": self.latest_safety_event.ai_confidence,
                "safety_status": _STATUS_NAMES.get(self.latest_safety_event.status, ""),
                "rejection_reason": self.latest_safety_event.reason,
                "failsafe_active": self.latest_safety_event.failsafe_active,
            }
        )


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TelemetryLoggerNode()
    try:
        rclpy.spin(node)
    finally:
        node.telemetry.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
