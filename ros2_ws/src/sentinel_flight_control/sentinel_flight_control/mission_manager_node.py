"""Mission planner node -- thin ROS 2 wrapper around MissionManager.

Subscribes to PX4 vehicle position directly (read-only telemetry) and to
/sentinelflight/perception_status (no publisher exists until Phase 5, so
this node runs with PerceptionResult(target_detected=False, confidence=0.0)
forever in real runs today -- see mission_manager.py's module docstring).
Publishes *proposed* setpoints only -- it never touches a /fmu/in/* topic
(see docs/architecture.md, "mission planner proposes, safety gate disposes").
"""

from __future__ import annotations

import rclpy
from px4_msgs.msg import VehicleLocalPosition
from rclpy.node import Node
from sentinel_flight_msgs.msg import Setpoint as SetpointMsg

from sentinel_flight_control.mission_manager import MissionManager, PerceptionResult
from sentinel_flight_control.ros_interfaces import (
    PROPOSED_SETPOINT_TOPIC,
    PX4_QOS,
    PX4_TOPIC_VEHICLE_LOCAL_POSITION,
)


class MissionManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_mission_manager")

        self.manager = MissionManager()
        self.proposed_pub = self.create_publisher(SetpointMsg, PROPOSED_SETPOINT_TOPIC, 10)
        self.create_subscription(
            VehicleLocalPosition, PX4_TOPIC_VEHICLE_LOCAL_POSITION, self._on_local_position, PX4_QOS
        )
        # TODO(phase-5): subscribe PERCEPTION_STATUS_TOPIC once a publisher exists.

        self.vehicle_local_position = VehicleLocalPosition()
        self.latest_perception = PerceptionResult(target_detected=False, confidence=0.0)

        self.create_timer(0.1, self._tick)  # 10 Hz, matches safety_gate_node/offboard_controller

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.vehicle_local_position = msg

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
