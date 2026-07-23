"""Unit tests for the mission planner state machine.

Mirrors tests/test_safety_gate.py's conventions (flat functions, factory
helpers, no mocking). No wall-clock mocking is needed here — unlike
SafetyGate, MissionManager's ARMING wait is tick-count-based, so it's fully
deterministic from repeated step() calls alone. Run with:
    pytest tests/test_mission_manager.py -v
"""

from sentinel_flight_control.mission_manager import (
    APPROACH_CONFIDENCE_THRESHOLD,
    APPROACH_GAIN,
    ARMING_TICKS,
    DESCEND_MIN_ALTITUDE_M,
    DESCEND_STEP_M,
    TAKEOFF_ALTITUDE_M,
    TAKEOFF_ALTITUDE_TOLERANCE_M,
    MissionManager,
    MissionState,
    PerceptionResult,
)
from sentinel_flight_control.safety_gate import SafetyLimits, Setpoint


def make_perception(
    target_detected=False,
    confidence=0.0,
    center_x_offset=0.0,
    center_y_offset=0.0,
    estimated_distance_m=None,
):
    return PerceptionResult(
        target_detected=target_detected,
        confidence=confidence,
        center_x_offset=center_x_offset,
        center_y_offset=center_y_offset,
        estimated_distance_m=estimated_distance_m,
    )


def drive_to_takeoff(manager):
    """INIT -> ARMING -> TAKEOFF: one tick to leave INIT, then ARMING_TICKS
    more to clear the ARMING wait."""
    p = make_perception()
    for _ in range(1 + ARMING_TICKS):
        manager.step(0.0, 0.0, 0.0, p)
    assert manager.state is MissionState.TAKEOFF


def drive_to_search(manager, vehicle_z=TAKEOFF_ALTITUDE_M):
    drive_to_takeoff(manager)
    manager.step(0.0, 0.0, vehicle_z, make_perception())
    assert manager.state is MissionState.SEARCH


def drive_to_approach(manager):
    drive_to_search(manager)
    manager.step(
        0.0, 0.0, TAKEOFF_ALTITUDE_M,
        make_perception(target_detected=True, confidence=0.9, center_x_offset=0.4),
    )
    assert manager.state is MissionState.APPROACH_TARGET


def drive_to_align(manager):
    drive_to_approach(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=True, confidence=0.9))
    assert manager.state is MissionState.ALIGN


def drive_to_descend(manager):
    drive_to_align(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=True, confidence=0.9))
    assert manager.state is MissionState.DESCEND


def test_init_then_arming_propose_climb_setpoint():
    manager = MissionManager()
    sp = manager.step(0.0, 0.0, 0.0, make_perception())
    assert manager.state is MissionState.ARMING
    assert sp.z == TAKEOFF_ALTITUDE_M
    # Never a sub-floor altitude, even fresh off the ground on tick 1 — the
    # startup MISSION_ABORT bug this design avoids (docs/roadmap.md Phase 4 notes).
    assert sp.z >= SafetyLimits().min_altitude_m


def test_arming_transitions_to_takeoff_after_arming_ticks():
    manager = MissionManager()
    manager.step(0.0, 0.0, 0.0, make_perception())  # INIT -> ARMING
    for _ in range(ARMING_TICKS - 1):
        manager.step(0.0, 0.0, 0.0, make_perception())
    assert manager.state is MissionState.ARMING
    manager.step(0.0, 0.0, 0.0, make_perception())
    assert manager.state is MissionState.TAKEOFF


def test_takeoff_stays_in_takeoff_below_altitude_tolerance():
    manager = MissionManager()
    drive_to_takeoff(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M - TAKEOFF_ALTITUDE_TOLERANCE_M - 0.1, make_perception())
    assert manager.state is MissionState.TAKEOFF


def test_takeoff_transitions_to_search_once_altitude_reached():
    manager = MissionManager()
    drive_to_takeoff(manager)
    sp = manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception())
    assert manager.state is MissionState.SEARCH
    assert sp.z == TAKEOFF_ALTITUDE_M


def test_search_holds_hover_when_no_target_detected():
    manager = MissionManager()
    drive_to_search(manager)
    sp = manager.step(1.0, 2.0, TAKEOFF_ALTITUDE_M, make_perception())
    assert sp == Setpoint(x=0.0, y=0.0, z=TAKEOFF_ALTITUDE_M)
    assert manager.state is MissionState.SEARCH


def test_search_transitions_to_approach_target_above_confidence_threshold():
    manager = MissionManager()
    drive_to_search(manager)
    manager.step(
        0.0, 0.0, TAKEOFF_ALTITUDE_M,
        make_perception(target_detected=True, confidence=0.81),
    )
    assert manager.state is MissionState.APPROACH_TARGET


def test_search_stays_at_confidence_exactly_threshold():
    manager = MissionManager()
    drive_to_search(manager)
    manager.step(
        0.0, 0.0, TAKEOFF_ALTITUDE_M,
        make_perception(target_detected=True, confidence=APPROACH_CONFIDENCE_THRESHOLD),
    )
    assert manager.state is MissionState.SEARCH


def test_approach_target_moves_toward_offset():
    manager = MissionManager()
    drive_to_approach(manager)
    sp = manager.step(
        1.0, 2.0, TAKEOFF_ALTITUDE_M,
        make_perception(target_detected=True, confidence=0.9, center_x_offset=0.4, center_y_offset=-0.2),
    )
    assert sp.x == 1.0 + APPROACH_GAIN * 0.4
    assert sp.y == 2.0 + APPROACH_GAIN * (-0.2)
    assert sp.z == TAKEOFF_ALTITUDE_M


def test_approach_target_falls_back_to_search_when_target_lost():
    manager = MissionManager()
    drive_to_approach(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=False))
    assert manager.state is MissionState.SEARCH


def test_approach_target_transitions_to_align_when_centered_and_confident():
    manager = MissionManager()
    drive_to_approach(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=True, confidence=0.9))
    assert manager.state is MissionState.ALIGN


def test_align_transitions_to_descend_when_centered_and_confident():
    manager = MissionManager()
    drive_to_align(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=True, confidence=0.9))
    assert manager.state is MissionState.DESCEND


def test_align_falls_back_to_search_when_target_lost():
    manager = MissionManager()
    drive_to_align(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=False))
    assert manager.state is MissionState.SEARCH


def test_descend_lowers_altitude_each_tick():
    manager = MissionManager()
    drive_to_descend(manager)
    sp = manager.step(
        0.0, 0.0, TAKEOFF_ALTITUDE_M,
        make_perception(target_detected=True, confidence=0.9),
    )
    assert manager.state is MissionState.DESCEND
    assert sp.z == TAKEOFF_ALTITUDE_M - DESCEND_STEP_M


def test_descend_transitions_to_land_at_min_altitude():
    manager = MissionManager()
    drive_to_descend(manager)
    sp = manager.step(
        0.0, 0.0, DESCEND_MIN_ALTITUDE_M,
        make_perception(target_detected=True, confidence=0.9),
    )
    assert manager.state is MissionState.LAND
    assert sp.z == DESCEND_MIN_ALTITUDE_M


def test_descend_falls_back_to_search_when_target_lost():
    manager = MissionManager()
    drive_to_descend(manager)
    manager.step(0.0, 0.0, TAKEOFF_ALTITUDE_M, make_perception(target_detected=False))
    assert manager.state is MissionState.SEARCH


def test_land_holds_position_above_altitude_floor():
    manager = MissionManager()
    drive_to_descend(manager)
    manager.step(0.0, 0.0, DESCEND_MIN_ALTITUDE_M, make_perception(target_detected=True, confidence=0.9))
    assert manager.state is MissionState.LAND
    sp = manager.step(3.0, 4.0, DESCEND_MIN_ALTITUDE_M, make_perception())
    assert sp == Setpoint(x=3.0, y=4.0, z=DESCEND_MIN_ALTITUDE_M)
    assert sp.z >= SafetyLimits().min_altitude_m
    assert manager.state is MissionState.LAND


def test_abort_holds_position_and_state_stays_abort():
    manager = MissionManager()
    manager.abort()
    sp = manager.step(3.0, 4.0, 5.0, make_perception())
    assert sp == Setpoint(x=3.0, y=4.0, z=5.0)
    assert manager.state is MissionState.ABORT
    manager.step(3.0, 4.0, 5.0, make_perception(target_detected=True, confidence=0.99))
    assert manager.state is MissionState.ABORT
