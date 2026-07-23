"""Mission planner: pure state machine, zero rclpy dependency (same pattern
as safety_gate.py) so it's unit testable without ROS 2 or PX4.

Design contract (see docs/architecture.md):
    - Publishes *proposed* setpoints only — it MUST NOT talk to PX4 directly.
    - Every proposed setpoint is validated by safety_gate.SafetyGate before
      it can become a real command. "Mission planner proposes, safety gate
      disposes."

Phase 4 note: no perception node exists yet (Phase 5), so in real runs
`step()` only ever sees `PerceptionResult(target_detected=False, ...)` —
the machine reaches SEARCH and holds there, which is the honest, safe
behavior rather than a faked demo. APPROACH_TARGET/ALIGN/DESCEND/LAND are
fully implemented and unit tested with synthetic PerceptionResult inputs
for when perception lands.

LAND holds position only — it does not command PX4. Real touchdown/disarm
stays owned by PX4's native AUTO_LAND, triggered independently by
offboard_controller.py on a hold-duration timer (MissionState.LAND is
unreachable live without perception, so it can't be the landing trigger
today — see docs/roadmap.md "Phase 4 notes"). Do not "fix" this by having
MissionManager talk to PX4 — that would violate the mission-planner-never-
talks-to-PX4 rule above.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sentinel_flight_control.safety_gate import Setpoint

TAKEOFF_ALTITUDE_M = 5.0
TAKEOFF_ALTITUDE_TOLERANCE_M = 0.3
ARMING_TICKS = 10
APPROACH_CONFIDENCE_THRESHOLD = 0.80
ALIGN_CONFIDENCE_THRESHOLD = 0.85
CENTERED_OFFSET_TOLERANCE = 0.10
APPROACH_GAIN = 0.5
DESCEND_STEP_M = 0.3
# Kept safely above SafetyGate's 1.0m altitude floor (SafetyLimits.min_altitude_m)
# so a proposed DESCEND/LAND setpoint is never rejected — the Phase 2 landing
# bug was exactly this class of mistake for the old built-in mission.
DESCEND_MIN_ALTITUDE_M = 1.5


class MissionState(Enum):
    INIT = "INIT"
    ARMING = "ARMING"
    TAKEOFF = "TAKEOFF"
    SEARCH = "SEARCH"
    APPROACH_TARGET = "APPROACH_TARGET"
    ALIGN = "ALIGN"
    DESCEND = "DESCEND"
    LAND = "LAND"
    ABORT = "ABORT"


@dataclass(frozen=True)
class PerceptionResult:
    target_detected: bool
    confidence: float
    center_x_offset: float = 0.0
    center_y_offset: float = 0.0
    estimated_distance_m: float | None = None


def _is_centered(perception: PerceptionResult) -> bool:
    return (
        abs(perception.center_x_offset) < CENTERED_OFFSET_TOLERANCE
        and abs(perception.center_y_offset) < CENTERED_OFFSET_TOLERANCE
    )


class MissionManager:
    """State machine: INIT -> ARMING -> TAKEOFF -> SEARCH ->
    APPROACH_TARGET -> ALIGN -> DESCEND -> LAND, with ABORT reachable at any
    time via abort(). Any post-SEARCH state falls back to SEARCH if the
    target is lost (perception.target_detected is False).

    Thresholds (see module docstring / docs/roadmap.md "Why start with the
    safety gate" design notes): APPROACH_TARGET entered when confidence >
    0.80, DESCEND entered only when centered AND confidence > 0.85.
    """

    def __init__(self):
        self.state = MissionState.INIT
        self._arming_ticks_elapsed = 0

    def step(
        self, vehicle_x: float, vehicle_y: float, vehicle_z: float, perception: PerceptionResult
    ) -> Setpoint:
        """Advance the state machine one tick and return a *proposed* setpoint
        for the (possibly just-transitioned-to) current state."""
        self._transition(vehicle_z, perception)
        return self._setpoint_for_state(vehicle_x, vehicle_y, vehicle_z, perception)

    def _transition(self, vehicle_z: float, perception: PerceptionResult) -> None:
        if self.state is MissionState.INIT:
            self.state = MissionState.ARMING
            self._arming_ticks_elapsed = 0
        elif self.state is MissionState.ARMING:
            self._arming_ticks_elapsed += 1
            if self._arming_ticks_elapsed >= ARMING_TICKS:
                self.state = MissionState.TAKEOFF
        elif self.state is MissionState.TAKEOFF:
            if vehicle_z >= TAKEOFF_ALTITUDE_M - TAKEOFF_ALTITUDE_TOLERANCE_M:
                self.state = MissionState.SEARCH
        elif self.state is MissionState.SEARCH:
            if perception.target_detected and perception.confidence > APPROACH_CONFIDENCE_THRESHOLD:
                self.state = MissionState.APPROACH_TARGET
        elif self.state is MissionState.APPROACH_TARGET:
            if not perception.target_detected:
                self.state = MissionState.SEARCH
            elif _is_centered(perception) and perception.confidence > ALIGN_CONFIDENCE_THRESHOLD:
                self.state = MissionState.ALIGN
        elif self.state is MissionState.ALIGN:
            if not perception.target_detected:
                self.state = MissionState.SEARCH
            elif _is_centered(perception) and perception.confidence > ALIGN_CONFIDENCE_THRESHOLD:
                self.state = MissionState.DESCEND
        elif self.state is MissionState.DESCEND:
            if not perception.target_detected:
                self.state = MissionState.SEARCH
            elif vehicle_z <= DESCEND_MIN_ALTITUDE_M:
                self.state = MissionState.LAND
        # LAND and ABORT are terminal here; LAND's real handoff is owned by
        # offboard_controller/PX4 (see module docstring), and ABORT only
        # ever changes via an explicit abort() call.

    def _setpoint_for_state(
        self, vehicle_x: float, vehicle_y: float, vehicle_z: float, perception: PerceptionResult
    ) -> Setpoint:
        if self.state in (MissionState.INIT, MissionState.ARMING, MissionState.TAKEOFF, MissionState.SEARCH):
            return Setpoint(x=0.0, y=0.0, z=TAKEOFF_ALTITUDE_M)
        if self.state in (MissionState.APPROACH_TARGET, MissionState.ALIGN):
            return self._approach_setpoint(vehicle_x, vehicle_y, TAKEOFF_ALTITUDE_M, perception)
        if self.state is MissionState.DESCEND:
            target_z = max(DESCEND_MIN_ALTITUDE_M, vehicle_z - DESCEND_STEP_M)
            return self._approach_setpoint(vehicle_x, vehicle_y, target_z, perception)
        if self.state is MissionState.LAND:
            return Setpoint(x=vehicle_x, y=vehicle_y, z=DESCEND_MIN_ALTITUDE_M)
        # ABORT
        return Setpoint(x=vehicle_x, y=vehicle_y, z=vehicle_z)

    @staticmethod
    def _approach_setpoint(
        vehicle_x: float, vehicle_y: float, altitude: float, perception: PerceptionResult
    ) -> Setpoint:
        return Setpoint(
            x=vehicle_x + APPROACH_GAIN * perception.center_x_offset,
            y=vehicle_y + APPROACH_GAIN * perception.center_y_offset,
            z=altitude,
        )

    def abort(self) -> None:
        self.state = MissionState.ABORT
