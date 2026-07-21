"""Telemetry logger.

Writes one CSV row per control-loop tick using the fixed schema below (see
docs/safety_layer.md for the safety_status enum values). Deliberately dumb
and dependency-free — no rclpy import, no analysis — so it's usable both as
a plain Python object (called in-process by OffboardController, same
pattern as SafetyGate) and unit tested without ROS 2. Analysis belongs in
scripts/analyze_logs.py.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

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
    """Appends telemetry rows to a CSV file, writing the header once.

    Usage:
        logger = TelemetryLogger("logs/mission.csv")
        logger.log({"timestamp": 12.54, "x": 3.2, ...})  # missing columns -> ""
        logger.close()
    """

    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.output_path.exists() or self.output_path.stat().st_size == 0

        self._file = self.output_path.open("a", newline="")
        self._writer = csv.DictWriter(
            self._file, fieldnames=TELEMETRY_CSV_COLUMNS, extrasaction="ignore"
        )
        if write_header:
            self._writer.writeheader()
            self._file.flush()

    def log(self, row: dict[str, Any]) -> None:
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "TelemetryLogger":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
