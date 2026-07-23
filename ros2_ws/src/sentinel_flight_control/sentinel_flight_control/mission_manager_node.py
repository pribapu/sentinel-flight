"""Mission planner node -- thin ROS 2 wrapper around MissionManager.

Subscribes to PX4 vehicle position directly (read-only telemetry) and to
/sentinelflight/perception_status (published by landing_pad_detector_node,
Phase 5). Publishes *proposed* setpoints only -- it never touches a
/fmu/in/* topic (see docs/architecture.md, "mission planner proposes,
safety gate disposes"). Also publishes:
  - a latched /sentinelflight/mission_land_requested bool once
    MissionManager reaches MissionState.LAND, so offboard_controller can
    trigger a real perception-driven AUTO_LAND instead of only its
    hold-duration fallback timer;
  - /sentinelflight/mission_trusting_perception, true only in
    APPROACH_TARGET/ALIGN/DESCEND/LAND, so safety_gate_node knows when a
    proposed setpoint actually depends on the AI's perception claim (see
    docs/roadmap.md "Phase 5 notes" -- forwarding raw perception confidence
    at all times, including while SEARCH is safely holding and not acting
    on a faint/low-confidence detection, caused false MISSION_ABORTs).
"""

from __future__ import annotations

import rclpy
from px4_msgs.msg import VehicleLocalPosition
from rclpy.node import Node
from sentinel_flight_msgs.msg import PerceptionStatus
from sentinel_flight_msgs.msg import Setpoint as SetpointMsg
from std_msgs.msg import Bool

from sentinel_flight_control.mission_manager import MissionManager, MissionState, PerceptionResult
from sentinel_flight_control.ros_interfaces import (
    MISSION_LAND_REQUESTED_TOPIC,
    MISSION_TRUSTING_PERCEPTION_TOPIC,
    PERCEPTION_STATUS_TOPIC,
    PROPOSED_SETPOINT_TOPIC,
    PX4_QOS,
    PX4_TOPIC_VEHICLE_LOCAL_POSITION,
)

_PERCEPTION_DEPENDENT_STATES = (
    MissionState.APPROACH_TARGET,
    MissionState.ALIGN,
    MissionState.DESCEND,
    MissionState.LAND,
)


class MissionManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_mission_manager")

        self.manager = MissionManager()
        self.proposed_pub = self.create_publisher(SetpointMsg, PROPOSED_SETPOINT_TOPIC, 10)
        self.land_requested_pub = self.create_publisher(Bool, MISSION_LAND_REQUESTED_TOPIC, 10)
        self.trusting_perception_pub = self.create_publisher(Bool, MISSION_TRUSTING_PERCEPTION_TOPIC, 10)
        self.create_subscription(
            VehicleLocalPosition, PX4_TOPIC_VEHICLE_LOCAL_POSITION, self._on_local_position, PX4_QOS
        )
        self.create_subscription(PerceptionStatus, PERCEPTION_STATUS_TOPIC, self._on_perception, 10)

        self.vehicle_local_position = VehicleLocalPosition()
        self.latest_perception = PerceptionResult(target_detected=False, confidence=0.0)

        self.create_timer(0.1, self._tick)  # 10 Hz, matches safety_gate_node/offboard_controller

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.vehicle_local_position = msg

    def _on_perception(self, msg: PerceptionStatus) -> None:
        self.latest_perception = PerceptionResult(
            target_detected=msg.target_detected,
            confidence=msg.confidence,
            center_x_offset=msg.center_x_offset,
            center_y_offset=msg.center_y_offset,
        )

    def _tick(self) -> None:
        vehicle_x = self.vehicle_local_position.x
        vehicle_y = self.vehicle_local_position.y
        vehicle_z = -self.vehicle_local_position.z  # PX4 NED -> altitude-up

        proposed = self.manager.step(vehicle_x, vehicle_y, vehicle_z, self.latest_perception)

        msg = SetpointMsg()
        msg.x = proposed.x
        msg.y = proposed.y
        msg.z = proposed.z
        msg.vx = proposed.vx
        msg.vy = proposed.vy
        msg.vz = proposed.vz
        self.proposed_pub.publish(msg)

        self.land_requested_pub.publish(Bool(data=self.manager.state is MissionState.LAND))
        self.trusting_perception_pub.publish(Bool(data=self.manager.state in _PERCEPTION_DEPENDENT_STATES))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MissionManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
