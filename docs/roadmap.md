# Roadmap

SentinelFlight is being built incrementally. This tracks what's real today
vs. what's designed-but-not-yet-built, mapped to the original 8-week plan.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Ubuntu 22.04 + ROS 2 Humble + PX4 SITL + Gazebo running | **Done** — WSL2 Ubuntu 22.04, ROS 2 Humble, PX4 SITL + Gazebo Harmonic 8.14.0 booting cleanly with the x500 quadcopter (see [evidence/phase1_sitl_gazebo_boot.log](evidence/phase1_sitl_gazebo_boot.log)) |
| 2 | ROS 2 offboard control (takeoff, waypoint, hover, land) | **Done** — `offboard_controller.py` arms PX4, engages OFFBOARD, climbs to 5m, holds, hands off to AUTO_LAND, verified against live SITL with the safety gate evaluating every tick (see [evidence/phase2_offboard_control.log](evidence/phase2_offboard_control.log)) |
| 3 | Telemetry logging (CSV/SQLite) | **Done** — `telemetry_logger.py` implemented + unit tested, wired into `OffboardController` (one row/tick), verified against a live 5660-row SITL run with `scripts/analyze_logs.py` (see [evidence/phase3_analysis_output.txt](evidence/phase3_analysis_output.txt)) |
| 4 | **Safety gate / runtime assurance layer** | **Implemented + unit tested** (`safety_gate.py`, 14 passing tests) |
| 5 | AI perception (landing pad / obstacle detection) | Design stub (`landing_pad_detector.py`) |
| 6 | Mission planner state machine | **Done** — `mission_manager.py` implemented + unit tested (17 passing tests), running as its own ROS 2 node (`mission_manager_node.py`) alongside `safety_gate_node.py` and a simplified `offboard_controller.py`, connected over a real `sentinel_flight_msgs` interfaces package instead of one in-process node — verified against live SITL (see [evidence/phase4_node_decomposition.log](evidence/phase4_node_decomposition.log) and [evidence/phase4_analysis_output.txt](evidence/phase4_analysis_output.txt)) |
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
3. ~~Implement `OffboardController` against the running SITL instance (Phase 2).~~ ✅ done
4. ~~Implement `TelemetryLogger` against the fixed CSV schema.~~ ✅ done
5. ~~Implement `MissionManager.step()` per the state machine already defined
   in `mission_manager.py`, and give it a real cross-node setpoint contract
   (a `sentinel_flight_msgs` interfaces package with a `Setpoint.msg`) so
   mission planning, the safety gate, and offboard control can run as
   separate nodes instead of the safety gate being called in-process by
   `OffboardController` as it is today.~~ ✅ done
6. Implement `LandingPadDetector` starting with an OpenCV ArUco marker
   (fastest path to an end-to-end demo) before training a model.
7. Wire the dashboard to the telemetry stream.
8. Run the full failure-mode test matrix in simulation and fill out
   `validation_report.md`.

## MVP order (fastest path to a legit demo)

1. PX4 + Gazebo drone launches. ✅ done — see [evidence/phase1_sitl_gazebo_boot.log](evidence/phase1_sitl_gazebo_boot.log)
2. ROS 2 node makes the drone take off and land. ✅ done — see [evidence/phase2_offboard_control.log](evidence/phase2_offboard_control.log)
3. Safety gate rejects unsafe altitude commands. ✅ done, unit tested, and verified live against PX4 (see Phase 2 notes below).
4. OpenCV detects a landing marker.
5. Drone hovers when AI confidence is low.
6. Telemetry logs safety events. ✅ done — see [evidence/phase3_analysis_output.txt](evidence/phase3_analysis_output.txt)
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

## Phase 2 notes

Built `OffboardController` as a single node that calls `SafetyGate.evaluate()`
in-process on every control tick (10 Hz) rather than over a ROS 2 topic —
there's no `sentinel_flight_msgs` interfaces package yet to carry a
`Setpoint` between nodes, so the mission-planner/safety-gate/offboard-
controller split shown in docs/architecture.md isn't three separate
processes yet. The safety-gate *logic* is fully live and load-bearing
(every setpoint really is evaluated before publishing to PX4); the
node-boundary decomposition is the next step, tracked above.

Issues hit getting a real flight, in order:

1. **PX4 topic names are version-suffixed.** The PX4 ROS 2 example docs use
   unversioned names (`/fmu/out/vehicle_local_position`); this PX4 checkout
   actually publishes `_v1`/`_v4`-suffixed variants
   (`/fmu/out/vehicle_local_position_v1`, `/fmu/out/vehicle_status_v4`,
   `/fmu/out/battery_status_v1`). Found via `ros2 topic list` /
   `ros2 topic info` against the running SITL instance rather than assumed
   from docs — the message *types* are unchanged.
2. **Arm command silently rejected.** `vehicle_status.pre_flight_checks_pass`
   was `false`; PX4's `rcAndDataLinkCheck.cpp` requires a GCS connection to
   arm whenever `NAV_DLL_ACT > 0` (default), and a ROS 2/DDS offboard client
   doesn't count as a GCS the way a MAVLink connection does. Fixed with
   `param set NAV_DLL_ACT 0` for automated/no-GCS SITL testing.
3. **Landing through the safety gate triggered `MISSION_ABORT`.** The
   descend-to-land setpoints legitimately need to go below
   `SafetyLimits.min_altitude_m` (1m) — the gate correctly rejected them
   as unsafe, which after 5 consecutive rejections escalated to
   `MISSION_ABORT`. This is exactly the kind of interaction bug that only
   shows up running the full system, not from unit-testing the gate in
   isolation. Fix: `OffboardController` now hands descent off to PX4's own
   `AUTO_LAND` mode via `VEHICLE_CMD_NAV_LAND` once holding is done, instead
   of trying to fight the altitude floor with offboard position setpoints —
   matching the pattern in PX4's own reference example.
4. **PX4 console spams gigabytes of log** when its interactive shell's stdin
   is `/dev/null` (no TTY) — `pxh>` prompt redraw loops indefinitely with
   nothing to read. Harmless to the simulation itself but fills disk fast.
   Worked around by giving PX4 a FIFO as stdin with a background process
   holding the write end open (`exec 3>fifo; sleep infinity`), which also
   makes it possible to send real console commands (like the `param set`
   above) into a running headless SITL instance.

Known limitation not yet fixed: the controller keeps publishing the
`OffboardControlMode` heartbeat after commanding `AUTO_LAND`, which appears
to slow PX4's disarm-after-landing logic — the vehicle stayed armed
immediately after touchdown in Phase 2 testing. Update from the Phase 3 run:
given enough real time (a few minutes, not seconds) it did eventually
disarm on its own, so this is a delay, not a permanent block — still worth
fixing by stopping the heartbeat once landing is commanded, just not
urgent.

## Phase 3 notes

`TelemetryLogger` is a plain CSV writer (like `SafetyGate`, no rclpy
dependency, unit tested in isolation) called in-process by
`OffboardController` once per tick, for the same reason the safety gate is
called in-process rather than over a topic: no `sentinel_flight_msgs`
interfaces package exists yet for cross-node structured data. A 5660-row
run (full takeoff -> hold -> `AUTO_LAND` -> disarm) logged with zero
safety-gate rejections, confirming the Phase 2 landing-altitude bug fix
holds up over a full mission, not just the one run it was found in.

## Phase 4 notes

Split the single in-process `OffboardController` (Phase 2/3) into four
separate ROS 2 nodes — `mission_manager_node`, `safety_gate_node`,
`offboard_controller`, `telemetry_logger_node` — connected over a new
`sentinel_flight_msgs` interfaces package (`Setpoint.msg`, `SafetyEvent.msg`),
and implemented `MissionManager.step()` for real (17 new unit tests in
`tests/test_mission_manager.py`). Issues hit, in order:

1. **A startup `MISSION_ABORT` landmine, found during design, not at
   runtime.** `SafetyGate._consecutive_rejections` never resets except on a
   fully `APPROVED` decision — once it hits 5 it's `MISSION_ABORT`
   permanently, no recovery. An early design for `MissionManager`'s
   `INIT`/`ARMING` states proposed "hold at the vehicle's current
   position," which on the ground is `z≈0` — below `SafetyLimits.min_altitude_m`
   (1.0m). That would have been rejected every tick and hit `MISSION_ABORT`
   within 0.5s of every real run. Fixed before it ever ran: `INIT`/`ARMING`/
   `TAKEOFF` all propose the same climb-to-`TAKEOFF_ALTITUDE_M` setpoint
   PX4 ignores pre-OFFBOARD anyway, same pattern as the existing
   pre-offboard setpoint streaming.
2. **Two pre-existing broken `console_scripts` entry points**, present
   since Phase 2/3 but never actually exercised because `README.md`'s
   "How to run" instructions used `python3 -m sentinel_flight_control.offboard_controller`
   directly rather than `ros2 run`/`ros2 launch`: `setup.py` registered
   `mission_manager = sentinel_flight_control.mission_manager:main` and
   `telemetry_logger = sentinel_flight_telemetry.telemetry_logger:main`,
   but neither module had a `main()` — both would have failed immediately
   if ever invoked. Replaced with the new node entry points.
3. **Missing `setup.cfg` meant `ros2 run`/`ros2 launch` silently couldn't
   find any executable**, even after fixing (2) and a clean `colcon build`
   succeeding. `ros2 pkg executables sentinel_flight_control` returned
   nothing, and the built console scripts landed under
   `install/<pkg>/bin/` instead of the `install/<pkg>/lib/<pkg>/` path
   `ros2 run` looks in. This is the standard `ament_python` package
   `setup.cfg` boilerplate (`script_dir`/`install_scripts` pointed at
   `$base/lib/<package_name>`), just never added to this repo because
   Phase 2/3 never needed `ros2 run` to work. Added to both
   `sentinel_flight_control` and `sentinel_flight_telemetry`; confirmed
   fixed via `ros2 pkg executables`.
4. **PX4 SITL launched via a background shell survived individual
   `wsl.exe` invocations fine, but the first launch attempt got killed
   mid-build ("interrupted by user")** because it was still attached to a
   pty (`pts/2`) that closed with the invoking session, despite `nohup`.
   `nohup` only blocks `SIGHUP`; `setsid` was needed to fully detach the
   process into its own session.
5. **The known Phase 2/3 "controller keeps heartbeating after AUTO_LAND,
   delaying disarm" limitation is still present** (not fixed in this
   phase — landing trigger logic didn't change, just moved to
   `offboard_controller`'s own independent timer, decoupled from
   `MissionManager.state` since `MissionState.LAND` is unreachable live
   without perception — see design note in `mission_manager.py`). This run
   took roughly 16 minutes to disarm on its own, longer than Phase 3's "a
   few minutes" — still not chased further, same follow-up item as before.

Verified end-to-end against live SITL with a full arm → climb to 5m → hold
→ `AUTO_LAND` → disarm cycle, zero safety-gate rejections across 9619 rows,
and `ros2 topic info`/`node info` confirming the node boundaries are real
(mission planner never sees a rejected proposal reach PX4; offboard
controller never sees a raw, unvalidated proposal) — see
[evidence/phase4_node_decomposition.log](evidence/phase4_node_decomposition.log)
and [evidence/phase4_analysis_output.txt](evidence/phase4_analysis_output.txt).

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
