"""Runtime assurance layer for SentinelFlight.

The AI-driven mission planner *proposes* setpoints; this module is the sole
authority that *disposes* of them. Every command that reaches PX4 must pass
through here first. Deliberately has zero dependency on rclpy/PX4 so the
safety logic can be unit tested in complete isolation from the simulator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class SafetyState(Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    FAILSAFE_HOVER = "FAILSAFE_HOVER"
    FAILSAFE_LAND = "FAILSAFE_LAND"
    MISSION_ABORT = "MISSION_ABORT"


class SafetyStatus(Enum):
    APPROVED = "APPROVED"
    REJECTED_LOW_CONFIDENCE = "REJECTED_LOW_CONFIDENCE"
    REJECTED_ALTITUDE_LIMIT = "REJECTED_ALTITUDE_LIMIT"
    REJECTED_GEOFENCE = "REJECTED_GEOFENCE"
    REJECTED_MAX_VELOCITY = "REJECTED_MAX_VELOCITY"
    REJECTED_OBSTACLE_PROXIMITY = "REJECTED_OBSTACLE_PROXIMITY"
    FAILSAFE_HOVER = "FAILSAFE_HOVER"
    FAILSAFE_LAND = "FAILSAFE_LAND"
    MISSION_ABORT = "MISSION_ABORT"


@dataclass(frozen=True)
class Setpoint:
    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0


@dataclass(frozen=True)
class VehicleState:
    x: float
    y: float
    z: float
    battery_percent: float = 100.0


@dataclass(frozen=True)
class AIStatus:
    confidence: float
    last_command_timestamp: float
    obstacle_detected: bool = False
    obstacle_distance_m: float | None = None


@dataclass(frozen=True)
class SafetyDecision:
    status: SafetyStatus
    setpoint: Setpoint
    reason: str
    state: SafetyState


@dataclass(frozen=True)
class SafetyLimits:
    min_altitude_m: float = 1.0
    max_altitude_m: float = 20.0
    max_horizontal_velocity_mps: float = 3.0
    max_vertical_velocity_mps: float = 1.0
    geofence_x_m: tuple[float, float] = (-20.0, 20.0)
    geofence_y_m: tuple[float, float] = (-20.0, 20.0)
    hover_confidence_threshold: float = 0.70
    land_confidence_threshold: float = 0.50
    stale_command_hover_s: float = 0.5
    stale_command_land_s: float = 3.0
    obstacle_proximity_m: float = 2.0
    low_battery_percent: float = 15.0
    max_consecutive_rejections: int = 5


class SafetyGate:
    """Deterministic runtime assurance state machine.

    Usage: call `evaluate()` once per proposed setpoint. The gate tracks its
    own state across calls (e.g. consecutive rejections escalate to
    MISSION_ABORT), so a single instance should back one active mission.
    """

    def __init__(self, limits: SafetyLimits | None = None):
        self.limits = limits or SafetyLimits()
        self.state = SafetyState.NORMAL
        self._consecutive_rejections = 0

    def evaluate(
        self,
        proposed: Setpoint,
        vehicle: VehicleState,
        ai: AIStatus,
        now: float | None = None,
    ) -> SafetyDecision:
        now = time.time() if now is None else now

        command_age = now - ai.last_command_timestamp
        if command_age > self.limits.stale_command_land_s:
            return self._decide(
                SafetyState.FAILSAFE_LAND,
                SafetyStatus.FAILSAFE_LAND,
                self._land(vehicle),
                f"No command received for {command_age:.2f}s",
            )
        if command_age > self.limits.stale_command_hover_s:
            return self._decide(
                SafetyState.FAILSAFE_HOVER,
                SafetyStatus.FAILSAFE_HOVER,
                self._hover(vehicle),
                f"No command received for {command_age:.2f}s",
            )

        if vehicle.battery_percent < self.limits.low_battery_percent:
            return self._decide(
                SafetyState.FAILSAFE_LAND,
                SafetyStatus.FAILSAFE_LAND,
                self._land(vehicle),
                f"Battery at {vehicle.battery_percent:.0f}%",
            )

        if self._consecutive_rejections >= self.limits.max_consecutive_rejections:
            return self._decide(
                SafetyState.MISSION_ABORT,
                SafetyStatus.MISSION_ABORT,
                self._land(vehicle),
                "Repeated unsafe commands from mission planner",
            )

        if ai.confidence < self.limits.land_confidence_threshold:
            return self._reject(
                SafetyState.FAILSAFE_LAND,
                SafetyStatus.FAILSAFE_LAND,
                self._land(vehicle),
                f"AI confidence {ai.confidence:.2f} below land threshold",
            )
        if ai.confidence < self.limits.hover_confidence_threshold:
            return self._reject(
                SafetyState.FAILSAFE_HOVER,
                SafetyStatus.REJECTED_LOW_CONFIDENCE,
                self._hover(vehicle),
                f"AI confidence {ai.confidence:.2f} below hover threshold",
            )

        if (
            ai.obstacle_detected
            and ai.obstacle_distance_m is not None
            and ai.obstacle_distance_m < self.limits.obstacle_proximity_m
        ):
            return self._reject(
                SafetyState.CAUTION,
                SafetyStatus.REJECTED_OBSTACLE_PROXIMITY,
                self._hover(vehicle),
                f"Obstacle {ai.obstacle_distance_m:.2f}m ahead",
            )

        if not (self.limits.min_altitude_m <= proposed.z <= self.limits.max_altitude_m):
            return self._reject(
                SafetyState.CAUTION,
                SafetyStatus.REJECTED_ALTITUDE_LIMIT,
                self._hover(vehicle),
                f"Proposed z={proposed.z:.2f}m outside "
                f"[{self.limits.min_altitude_m}, {self.limits.max_altitude_m}]",
            )

        horizontal_speed = (proposed.vx**2 + proposed.vy**2) ** 0.5
        if (
            horizontal_speed > self.limits.max_horizontal_velocity_mps
            or abs(proposed.vz) > self.limits.max_vertical_velocity_mps
        ):
            return self._reject(
                SafetyState.CAUTION,
                SafetyStatus.REJECTED_MAX_VELOCITY,
                self._hover(vehicle),
                f"Speed h={horizontal_speed:.2f}m/s v={proposed.vz:.2f}m/s exceeds limits",
            )

        x_min, x_max = self.limits.geofence_x_m
        y_min, y_max = self.limits.geofence_y_m
        if not (x_min <= proposed.x <= x_max and y_min <= proposed.y <= y_max):
            return self._reject(
                SafetyState.CAUTION,
                SafetyStatus.REJECTED_GEOFENCE,
                self._hover(vehicle),
                f"Proposed ({proposed.x:.2f}, {proposed.y:.2f}) outside geofence",
            )

        self._consecutive_rejections = 0
        return self._decide(SafetyState.NORMAL, SafetyStatus.APPROVED, proposed, "OK")

    def _reject(
        self, state: SafetyState, status: SafetyStatus, setpoint: Setpoint, reason: str
    ) -> SafetyDecision:
        self._consecutive_rejections += 1
        return self._decide(state, status, setpoint, reason)

    def _decide(
        self, state: SafetyState, status: SafetyStatus, setpoint: Setpoint, reason: str
    ) -> SafetyDecision:
        self.state = state
        return SafetyDecision(status=status, setpoint=setpoint, reason=reason, state=state)

    @staticmethod
    def _hover(vehicle: VehicleState) -> Setpoint:
        return Setpoint(x=vehicle.x, y=vehicle.y, z=vehicle.z)

    @staticmethod
    def _land(vehicle: VehicleState) -> Setpoint:
        return Setpoint(x=vehicle.x, y=vehicle.y, z=0.0, vz=-0.3)
