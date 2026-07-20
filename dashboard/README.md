# Dashboard (planned — Phase 7)

FastAPI + React + WebSocket dashboard showing live mission status, AI
perception confidence, safety gate decisions, and a rolling timeline of
safety events.

- `backend/` — FastAPI service that streams telemetry + safety events over
  WebSocket, reading from the same CSV/SQLite schema defined in
  `sentinel_flight_telemetry/telemetry_logger.py`.
- `frontend/` — React app rendering vehicle state, AI confidence, mission
  state, and the safety event timeline in real time.

Not yet implemented. See [../docs/roadmap.md](../docs/roadmap.md).
