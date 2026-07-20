"""Unit tests for the runtime assurance layer.

Mirrors the failure-mode test matrix in docs/safety_layer.md. Run with:
    pytest tests/test_safety_gate.py -v
"""

from sentinel_flight_control.safety_gate import (
    AIStatus,
    SafetyGate,
    SafetyState,
    SafetyStatus,
    Setpoint,
    VehicleState,
)

NOW = 1000.0


def make_ai(confidence=0.95, age=0.0, obstacle_detected=False, obstacle_distance_m=None):
    return AIStatus(
        confidence=confidence,
        last_command_timestamp=NOW - age,
        obstacle_detected=obstacle_detected,
        obstacle_distance_m=obstacle_distance_m,
    )


def make_vehicle(x=0.0, y=0.0, z=5.0, battery_percent=100.0):
    return VehicleState(x=x, y=y, z=z, battery_percent=battery_percent)


def test_safe_command_is_approved():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=1.0, z=5.0, vx=1.0, vy=0.0, vz=0.0),
        make_vehicle(),
        make_ai(),
        now=NOW,
    )
    assert decision.status == SafetyStatus.APPROVED
    assert decision.state == SafetyState.NORMAL


def test_rejects_altitude_above_max():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=0.0, y=0.0, z=50.0), make_vehicle(), make_ai(), now=NOW
    )
    assert decision.status == SafetyStatus.REJECTED_ALTITUDE_LIMIT
    assert decision.setpoint.z == make_vehicle().z  # holds position, doesn't crash into limit


def test_rejects_altitude_below_min():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=0.0, y=0.0, z=0.2), make_vehicle(), make_ai(), now=NOW
    )
    assert decision.status == SafetyStatus.REJECTED_ALTITUDE_LIMIT


def test_low_confidence_triggers_hover():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0), make_vehicle(), make_ai(confidence=0.6), now=NOW
    )
    assert decision.status == SafetyStatus.REJECTED_LOW_CONFIDENCE
    assert decision.state == SafetyState.FAILSAFE_HOVER


def test_critical_confidence_triggers_land():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0), make_vehicle(), make_ai(confidence=0.4), now=NOW
    )
    assert decision.status == SafetyStatus.FAILSAFE_LAND
    assert decision.state == SafetyState.FAILSAFE_LAND


def test_rejects_command_outside_geofence():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=25.0, y=0.0, z=5.0), make_vehicle(), make_ai(), now=NOW
    )
    assert decision.status == SafetyStatus.REJECTED_GEOFENCE


def test_rejects_excessive_horizontal_velocity():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0, vx=5.0), make_vehicle(), make_ai(), now=NOW
    )
    assert decision.status == SafetyStatus.REJECTED_MAX_VELOCITY


def test_rejects_excessive_vertical_velocity():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=0.0, y=0.0, z=5.0, vz=2.0), make_vehicle(), make_ai(), now=NOW
    )
    assert decision.status == SafetyStatus.REJECTED_MAX_VELOCITY


def test_stale_command_under_3s_triggers_hover():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0), make_vehicle(), make_ai(age=0.75), now=NOW
    )
    assert decision.status == SafetyStatus.FAILSAFE_HOVER


def test_stale_command_over_3s_triggers_land():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0), make_vehicle(), make_ai(age=4.0), now=NOW
    )
    assert decision.status == SafetyStatus.FAILSAFE_LAND


def test_obstacle_within_proximity_rejects_forward_motion():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0),
        make_vehicle(),
        make_ai(obstacle_detected=True, obstacle_distance_m=1.0),
        now=NOW,
    )
    assert decision.status == SafetyStatus.REJECTED_OBSTACLE_PROXIMITY


def test_low_battery_triggers_land_regardless_of_command():
    gate = SafetyGate()
    decision = gate.evaluate(
        Setpoint(x=1.0, y=0.0, z=5.0),
        make_vehicle(battery_percent=10.0),
        make_ai(),
        now=NOW,
    )
    assert decision.status == SafetyStatus.FAILSAFE_LAND


def test_repeated_unsafe_commands_trigger_mission_abort():
    gate = SafetyGate()
    unsafe = Setpoint(x=99.0, y=0.0, z=5.0)  # outside geofence every time
    vehicle = make_vehicle()
    ai = make_ai()

    decisions = [gate.evaluate(unsafe, vehicle, ai, now=NOW) for _ in range(6)]

    assert decisions[-1].status == SafetyStatus.MISSION_ABORT
    assert all(d.status == SafetyStatus.REJECTED_GEOFENCE for d in decisions[:5])


def test_approval_resets_consecutive_rejection_counter():
    gate = SafetyGate()
    vehicle = make_vehicle()
    ai = make_ai()

    for _ in range(4):
        gate.evaluate(Setpoint(x=99.0, y=0.0, z=5.0), vehicle, ai, now=NOW)

    safe_decision = gate.evaluate(Setpoint(x=1.0, y=0.0, z=5.0), vehicle, ai, now=NOW)
    assert safe_decision.status == SafetyStatus.APPROVED

    # counter should be reset, so this shouldn't abort yet
    decision = gate.evaluate(Setpoint(x=99.0, y=0.0, z=5.0), vehicle, ai, now=NOW)
    assert decision.status == SafetyStatus.REJECTED_GEOFENCE
