"""Telemetry logger node (interface stub).

Status: NOT YET IMPLEMENTED. Planned as Phase 3 in docs/roadmap.md. The CSV
schema below is fixed by that design doc so scripts/analyze_logs.py can rely
on it once this node is built.

Design contract (see docs/architecture.md):
    - Subscribes to vehicle odometry, the safety gate's decision + reason,
      and AI confidence.
    - Writes one row per control-loop tick to CSV (or SQLite for larger
      runs).

CSV schema (see docs/safety_layer.md for the safety_status enum values):
    timestamp, x, y, z, vx, vy, vz, roll, pitch, yaw, flight_mode,
    armed_status, proposed_x, proposed_y, proposed_z, approved_x,
    approved_y, approved_z, ai_confidence, safety_status, rejection_reason,
    failsafe_active
"""

from __future__ import annotations

TELEMETRY_CSV_COLUMNS = [
    "timestamp",
    "x",
    "y",
    "z",
    "vx",
    "vy",
    "vz",
    "roll",
    "pitch",
    "yaw",
    "flight_mode",
    "armed_status",
    "proposed_x",
    "proposed_y",
    "proposed_z",
    "approved_x",
    "approved_y",
    "approved_z",
    "ai_confidence",
    "safety_status",
    "rejection_reason",
    "failsafe_active",
]


class TelemetryLogger:
    """TODO(week-3): implement per docs/roadmap.md Phase 3.

    Should be a thin ROS 2 subscriber that writes TELEMETRY_CSV_COLUMNS rows
    to logs/. Keep it dumb — no analysis here, that belongs in
    scripts/analyze_logs.py.
    """

    def __init__(self, output_path: str):
        raise NotImplementedError(
            "TelemetryLogger is a design stub — implement per docs/roadmap.md Phase 3"
        )
