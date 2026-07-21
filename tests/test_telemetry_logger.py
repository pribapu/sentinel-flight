"""Unit tests for the telemetry CSV logger."""

import csv

from sentinel_flight_telemetry.telemetry_logger import TELEMETRY_CSV_COLUMNS, TelemetryLogger


def test_writes_header_once_on_new_file(tmp_path):
    path = tmp_path / "mission.csv"
    logger = TelemetryLogger(str(path))
    logger.log({"timestamp": 1.0, "x": 0.0})
    logger.close()

    with path.open(newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == TELEMETRY_CSV_COLUMNS
    assert len(rows) == 2


def test_appends_without_duplicating_header(tmp_path):
    path = tmp_path / "mission.csv"
    TelemetryLogger(str(path)).log({"timestamp": 1.0})

    logger2 = TelemetryLogger(str(path))
    logger2.log({"timestamp": 2.0})
    logger2.close()

    with path.open(newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == TELEMETRY_CSV_COLUMNS
    assert len(rows) == 3  # header + 2 data rows


def test_row_values_round_trip(tmp_path):
    path = tmp_path / "mission.csv"
    row = {
        "timestamp": 12.54,
        "x": 3.2,
        "y": 1.1,
        "z": 5.0,
        "safety_status": "APPROVED",
        "rejection_reason": "NONE",
    }
    with TelemetryLogger(str(path)) as logger:
        logger.log(row)

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        written = next(reader)

    assert written["timestamp"] == "12.54"
    assert written["safety_status"] == "APPROVED"
    assert written["vx"] == ""  # not provided, defaults to empty


def test_context_manager_closes_file(tmp_path):
    path = tmp_path / "mission.csv"
    with TelemetryLogger(str(path)) as logger:
        logger.log({"timestamp": 1.0})
    assert logger._file.closed
