#!/usr/bin/env python3
"""Summarize a SentinelFlight telemetry CSV.

Works standalone against any CSV matching the schema defined in
sentinel_flight_telemetry.telemetry_logger.TELEMETRY_CSV_COLUMNS — no ROS 2
or PX4 required. Once telemetry_logger.py is implemented (see
docs/roadmap.md Phase 3) and a real mission log exists, point this at it:

    python scripts/analyze_logs.py logs/sample_mission.csv
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


def summarize(csv_path: Path) -> None:
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"{csv_path} has no data rows.")
        return

    altitudes = [float(r["z"]) for r in rows if r.get("z")]
    confidences = [float(r["ai_confidence"]) for r in rows if r.get("ai_confidence")]
    statuses = Counter(r.get("safety_status", "") for r in rows)

    print(f"Rows: {len(rows)}")
    if altitudes:
        print(f"Altitude: min={min(altitudes):.2f}m max={max(altitudes):.2f}m avg={sum(altitudes) / len(altitudes):.2f}m")
    if confidences:
        print(f"AI confidence: min={min(confidences):.2f} max={max(confidences):.2f} avg={sum(confidences) / len(confidences):.2f}")
    print("Safety status breakdown:")
    for status, count in statuses.most_common():
        print(f"  {status or '(blank)'}: {count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <telemetry.csv>", file=sys.stderr)
        sys.exit(1)
    summarize(Path(sys.argv[1]))
