"""Safety gate node -- the sole authority deciding what reaches PX4.

Subscribes to the mission planner's proposed setpoints, PX4 vehicle state
directly (position + battery), and perception status + mission_trusting_
perception (Phase 5) to build each tick's AIStatus.confidence (see
NO_TARGET_AI_CONFIDENCE below). Evaluates on its own 10 Hz timer (rather
than only when a proposal arrives) so failsafe behavior -- stale command,
low battery -- keeps firing even if the mission planner stalls or dies.
Publishes the approved/downgraded setpoint and a SafetyEvent describing
the decision.
"""

from __future__ import annotations

import time

import rclpy
from px4_msgs.msg import BatteryStatus, VehicleLocalPosition
from rclpy.node import Node
from sentinel_flight_msgs.msg import PerceptionStatus
from sentinel_flight_msgs.msg import SafetyEvent as SafetyEventMsg
from sentinel_flight_msgs.msg import Setpoint as SetpointMsg
from std_msgs.msg import Bool

from sentinel_flight_control.mission_manager import TAKEOFF_ALTITUDE_M
from sentinel_flight_control.ros_interfaces import (
    MISSION_TRUSTING_PERCEPTION_TOPIC,
    PERCEPTION_STATUS_TOPIC,
    PROPOSED_SETPOINT_TOPIC,
    PX4_QOS,
    PX4_TOPIC_BATTERY_STATUS,
    PX4_TOPIC_VEHICLE_LOCAL_POSITION,
    SAFE_SETPOINT_TOPIC,
    SAFETY_EVENT_TOPIC,
)
from sentinel_flight_control.safety_gate import (
    AIStatus,
    SafetyGate,
    SafetyState,
    SafetyStatus,
    Setpoint,
    VehicleState,
)

# AIStatus.confidence to report when the mission planner isn't currently
# depending on perception (MissionState outside APPROACH_TARGET/ALIGN/
# DESCEND/LAND -- see mission_manager_node.py's mission_trusting_perception
# publisher). A SEARCH-phase hover doesn't depend on any AI claim about a
# target, so there's nothing target-dependent to distrust yet.
#
# This is NOT just "confidence when target_detected is False" -- an early
# live-testing run found forwarding raw perception confidence *whenever a
# marker was merely visible* (even faint/distant, e.g. 0.4 while still
# climbing, well before MissionManager's own 0.80 threshold would ever act
# on it) tripped land_confidence_threshold repeatedly and escalated to a
# permanent MISSION_ABORT during ordinary startup hover -- the gate was
# punishing a proposal the mission planner wasn't even conditioning on that
# data. See docs/roadmap.md "Phase 5 notes".
NO_TARGET_AI_CONFIDENCE = 0.95

# SafetyStatus/SafetyState enum -> SafetyEvent.msg uint8 constant. Kept in
# sync by hand with safety_gate.py and sentinel_flight_msgs/msg/SafetyEvent.msg.
_STATUS_TO_MSG = {
    SafetyStatus.APPROVED: SafetyEventMsg.STATUS_APPROVED,
    SafetyStatus.REJECTED_LOW_CONFIDENCE: SafetyEventMsg.STATUS_REJECTED_LOW_CONFIDENCE,
    SafetyStatus.REJECTED_ALTITUDE_LIMIT: SafetyEventMsg.STATUS_REJECTED_ALTITUDE_LIMIT,
    SafetyStatus.REJECTED_GEOFENCE: SafetyEventMsg.STATUS_REJECTED_GEOFENCE,
    SafetyStatus.REJECTED_MAX_VELOCITY: SafetyEventMsg.STATUS_REJECTED_MAX_VELOCITY,
    SafetyStatus.REJECTED_OBSTACLE_PROXIMITY: SafetyEventMsg.STATUS_REJECTED_OBSTACLE_PROXIMITY,
    SafetyStatus.FAILSAFE_HOVER: SafetyEventMsg.STATUS_FAILSAFE_HOVER,
    SafetyStatus.FAILSAFE_LAND: SafetyEventMsg.STATUS_FAILSAFE_LAND,
    SafetyStatus.MISSION_ABORT: SafetyEventMsg.STATUS_MISSION_ABORT,
}
_STATE_TO_MSG = {
    SafetyState.NORMAL: SafetyEventMsg.STATE_NORMAL,
    SafetyState.CAUTION: SafetyEventMsg.STATE_CAUTION,
    SafetyState.FAILSAFE_HOVER: SafetyEventMsg.STATE_FAILSAFE_HOVER,
    SafetyState.FAILSAFE_LAND: SafetyEventMsg.STATE_FAILSAFE_LAND,
    SafetyState.MISSION_ABORT: SafetyEventMsg.STATE_MISSION_ABORT,
}


class SafetyGateNode(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_safety_gate")

        self.gate = SafetyGate()
        self.safe_setpoint_pub = self.create_publisher(SetpointMsg, SAFE_SETPOINT_TOPIC, 10)
        self.safety_event_pub = self.create_publisher(SafetyEventMsg, SAFETY_EVENT_TOPIC, 10)
        self.create_subscription(SetpointMsg, PROPOSED_SETPOINT_TOPIC, self._on_proposed, 10)
        self.create_subscription(
            VehicleLocalPosition, PX4_TOPIC_VEHICLE_LOCAL_POSITION, self._on_local_position, PX4_QOS
        )
        self.create_subscription(BatteryStatus, PX4_TOPIC_BATTERY_STATUS, self._on_battery, PX4_QOS)
        self.create_subscription(PerceptionStatus, PERCEPTION_STATUS_TOPIC, self._on_perception, 10)
        self.create_subscription(
            Bool, MISSION_TRUSTING_PERCEPTION_TOPIC, self._on_trusting_perception, 10
        )

        # Safe default before mission_manager_node's first message arrives --
        # matches MissionManager's own INIT/ARMING/TAKEOFF proposal.
        self.latest_proposed = Setpoint(x=0.0, y=0.0, z=TAKEOFF_ALTITUDE_M)
        self.last_proposed_received_at: float | None = None
        self.vehicle_local_position = VehicleLocalPosition()
        self.battery_percent = 100.0
        self.perception_confidence = 0.0
        self.mission_trusting_perception = False

        self.create_timer(0.1, self._tick)  # 10 Hz

    def _on_proposed(self, msg: SetpointMsg) -> None:
        self.latest_proposed = Setpoint(x=msg.x, y=msg.y, z=msg.z, vx=msg.vx, vy=msg.vy, vz=msg.vz)
        self.last_proposed_received_at = time.time()

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.vehicle_local_position = msg

    def _on_battery(self, msg: BatteryStatus) -> None:
        if msg.remaining >= 0.0:
            self.battery_percent = msg.remaining * 100.0

    def _on_perception(self, msg: PerceptionStatus) -> None:
        self.perception_confidence = msg.confidence

    def _on_trusting_perception(self, msg: Bool) -> None:
        self.mission_trusting_perception = msg.data

    def _tick(self) -> None:
        vehicle = VehicleState(
            x=self.vehicle_local_position.x,
            y=self.vehicle_local_position.y,
            z=-self.vehicle_local_position.z,
            battery_percent=self.battery_percent,
        )
        last_ts = self.last_proposed_received_at if self.last_proposed_received_at is not None else time.time()
        confidence = self.perception_confidence if self.mission_trusting_perception else NO_TARGET_AI_CONFIDENCE
        ai = AIStatus(confidence=confidence, last_command_timestamp=last_ts)

        decision = self.gate.evaluate(self.latest_proposed, vehicle, ai)
        if decision.status != SafetyStatus.APPROVED:
            self.get_logger().warn(f"safety_gate: {decision.status.value} - {decision.reason}")

        sp = decision.setpoint
        safe_msg = SetpointMsg()
        safe_msg.x = sp.x
        safe_msg.y = sp.y
        safe_msg.z = sp.z
        safe_msg.vx = sp.vx
        safe_msg.vy = sp.vy
        safe_msg.vz = sp.vz
        self.safe_setpoint_pub.publish(safe_msg)

        event_msg = SafetyEventMsg()
        event_msg.timestamp = time.time()
        event_msg.status = _STATUS_TO_MSG[decision.status]
        event_msg.state = _STATE_TO_MSG[decision.state]
        event_msg.reason = decision.reason
        event_msg.ai_confidence = ai.confidence
        event_msg.failsafe_active = decision.state in (
            SafetyState.FAILSAFE_HOVER,
            SafetyState.FAILSAFE_LAND,
            SafetyState.MISSION_ABORT,
        )
        self.safety_event_pub.publish(event_msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SafetyGateNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
