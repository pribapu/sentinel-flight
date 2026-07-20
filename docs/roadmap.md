# Roadmap

SentinelFlight is being built incrementally. This tracks what's real today
vs. what's designed-but-not-yet-built, mapped to the original 8-week plan.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Ubuntu 22.04 + ROS 2 Humble + PX4 SITL + Gazebo running | **Done** — WSL2 Ubuntu 22.04, ROS 2 Humble, PX4 SITL + Gazebo Harmonic 8.14.0 booting cleanly with the x500 quadcopter (see [evidence/phase1_sitl_gazebo_boot.log](evidence/phase1_sitl_gazebo_boot.log)) |
| 2 | ROS 2 offboard control (takeoff, waypoint, hover, land) | Design stub (`offboard_controller.py`) |
| 3 | Telemetry logging (CSV/SQLite) | Design stub (`telemetry_logger.py`), CSV schema fixed |
| 4 | **Safety gate / runtime assurance layer** | **Implemented + unit tested** (`safety_gate.py`, 14 passing tests) |
| 5 | AI perception (landing pad / obstacle detection) | Design stub (`landing_pad_detector.py`) |
| 6 | Mission planner state machine | Design stub (`mission_manager.py`), state machine + data contracts defined |
| 7 | Live dashboard (FastAPI + React) | Not started, folders scaffolded |
| 8 | Edge deployment (Jetson Orin Nano / TensorRT) | Not started |
| 9 | Failure-mode testing + validation report | Started — safety gate test matrix in `docs/safety_layer.md`; full sim-based fault injection pending Phase 1 |
| 10 | Repo polish, README, demo video, resume bullets | This scaffold |

## Why start with the safety gate

Phase 4 (the runtime assurance layer) is the architectural centerpiece of
this project and, unlike every other phase, it has zero dependency on ROS 2,
PX4, or Gazebo — it's pure decision logic over vehicle/AI state. That makes
it the highest-value thing to build first and the easiest to prove
correct with unit tests, independent of simulator availability.

## Next steps to reach the MVP demo

1. ~~Set up Ubuntu 22.04 or WSL2 with GPU passthrough for Gazebo (Phase 1).~~ ✅ done
2. ~~Get PX4 SITL + Gazebo launching with a simulated quadcopter.~~ ✅ done
3. Implement `OffboardController` against the running SITL instance
   (Phase 2), reusing the already-defined `Setpoint` contract from
   `safety_gate.py`.
4. Implement `TelemetryLogger` against the fixed CSV schema.
5. Implement `MissionManager.step()` per the state machine already defined
   in `mission_manager.py`.
6. Implement `LandingPadDetector` starting with an OpenCV ArUco marker
   (fastest path to an end-to-end demo) before training a model.
7. Wire the dashboard to the telemetry stream.
8. Run the full failure-mode test matrix in simulation and fill out
   `validation_report.md`.

## MVP order (fastest path to a legit demo)

1. PX4 + Gazebo drone launches. ✅ done — see [evidence/phase1_sitl_gazebo_boot.log](evidence/phase1_sitl_gazebo_boot.log)
2. ROS 2 node makes the drone take off and land.
3. Safety gate rejects unsafe altitude commands. ✅ done, unit tested.
4. OpenCV detects a landing marker.
5. Drone hovers when AI confidence is low.
6. Telemetry logs safety events.
7. README + demo video.

## Phase 1 notes (WSL2/Windows-specific)

Built on Windows via WSL2 rather than native Ubuntu or dual-boot:

- The WSL2 host's default Ubuntu release didn't match what ROS 2 Humble and
  PX4's `ubuntu.sh` officially support, so a dedicated `Ubuntu-22.04` WSL
  distro was installed alongside it (`wsl --install -d Ubuntu-22.04`).
- `Tools/setup/ubuntu.sh` hardcodes `/home/$USER/.bashrc`, which breaks when
  run as root (`$HOME=/root`, not `/home/root`) under `set -e`. Worked around
  by re-running with `--no-nuttx` — SITL/Gazebo only need the simulation
  dependencies, not the NuttX firmware toolchain for real flight controllers.
- `make px4_sitl gz_x500` with the Gazebo GUI enabled produces runaway
  rendering-warning spam under WSLg (multi-GB logs in minutes). Use
  `HEADLESS=1 make px4_sitl gz_x500` for SITL work — the physics/flight
  simulation runs identically, just without the 3D viewer.

## Advanced additions (post-MVP)

- Jetson Orin Nano deployment with TensorRT-optimized inference.
- GPS-denied navigation via IMU/camera sensor fusion (Kalman filter) — the
  strongest signal-add for defense/aerospace-flavored roles.
- Multi-agent drone simulation.
- Formal safety constraint verification.

## Explicitly out of scope

This project is framed around flight safety, autonomous navigation,
search-and-rescue, inspection, and runtime assurance — not weapon
targeting, autonomous attack, or military payloads.
