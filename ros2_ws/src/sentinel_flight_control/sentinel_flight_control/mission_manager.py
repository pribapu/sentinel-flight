"""Mission planner node (interface stub).

Status: NOT YET IMPLEMENTED. This defines the intended state machine and
node contract; the logic body is left as TODOs so this can be built out in
Week 6 of the roadmap (see docs/roadmap.md) once ROS 2 / PX4 are available.

Design contract (see docs/architecture.md):
    - Subscribes to AI perception output and current vehicle odometry.
    - Publishes *proposed* setpoints only — it MUST NOT talk to PX4 directly.
    - Every proposed setpoint is validated by safety_gate.SafetyGate before
      it can become a real command. "Mission planner proposes, safety gate
      disposes."

Planned ROS 2 topics:
    Subscribes:
        /sentinelflight/perception_status   (perception result + confidence)
        /px4/vehicle_odometry
    Publishes:
        /sentinelflight/proposed_setpoint
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sentinel_flight_control.safety_gate import Setpoint


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


class MissionManager:
    """State machine skeleton: SEARCH -> APPROACH_TARGET -> ALIGN -> DESCEND -> LAND.

    TODO(week-6): implement each state's transition + setpoint logic per
    docs/roadmap.md Phase 6. Suggested thresholds from the design doc:
        - APPROACH_TARGET entered when confidence > 0.80
        - DESCEND entered only when centered AND confidence > 0.85
        - Any state may fall back to SEARCH if the target is lost.
    """

    def __init__(self):
        self.state = MissionState.INIT

    def step(self, vehicle_x: float, vehicle_y: float, vehicle_z: float, perception: PerceptionResult) -> Setpoint:
        """Return a *proposed* setpoint for the current mission state.

        TODO: implement transition table described in the class docstring.
        Currently holds position and never progresses past INIT so that any
        integration that imports this module fails safe rather than silently
        commanding an unimplemented mission.
        """
        raise NotImplementedError(
            "MissionManager.step is a design stub — implement per docs/roadmap.md Phase 6"
        )

    def abort(self) -> None:
        self.state = MissionState.ABORT
