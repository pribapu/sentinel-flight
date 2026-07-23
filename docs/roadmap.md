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
| 5 | AI perception (landing pad / obstacle detection) | **Done (landing-pad detection)** — `landing_pad_detector.py` implements real OpenCV ArUco detection (unit tested, 6 passing tests), running as `landing_pad_detector_node.py` against a live Gazebo camera feed bridged via `ros_gz_bridge`, feeding `mission_manager_node`/`safety_gate_node` over `/sentinelflight/perception_status` — verified against live SITL (see [evidence/phase5_perception_landing.log](evidence/phase5_perception_landing.log)). Obstacle detection not started. |
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
6. ~~Implement `LandingPadDetector` starting with an OpenCV ArUco marker
   (fastest path to an end-to-end demo) before training a model.~~ ✅ done
7. Wire the dashboard to the telemetry stream.
8. Run the full failure-mode test matrix in simulation and fill out
   `validation_report.md`.

## MVP order (fastest path to a legit demo)

1. PX4 + Gazebo drone launches. ✅ done — see [evidence/phase1_sitl_gazebo_boot.log](evidence/phase1_sitl_gazebo_boot.log)
2. ROS 2 node makes the drone take off and land. ✅ done — see [evidence/phase2_offboard_control.log](evidence/phase2_offboard_control.log)
3. Safety gate rejects unsafe altitude commands. ✅ done, unit tested, and verified live against PX4 (see Phase 2 notes below).
4. OpenCV detects a landing marker. ✅ done — see [evidence/phase5_perception_landing.log](evidence/phase5_perception_landing.log)
5. Drone hovers when AI confidence is low. ✅ done (the `mission_trusting_perception` fix in Phase 5 notes is exactly this, verified live)
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

## Phase 5 notes

Implemented `LandingPadDetector` (OpenCV ArUco, `cv2.aruco`) and wired it
in as `landing_pad_detector_node`, the first node in this project to
consume live camera data rather than just PX4 telemetry. PX4-Autopilot
ships exactly the right fixtures for this: a downward-facing mono camera
vehicle variant (`Tools/simulation/gz/models/x500_mono_cam_down`) and a
world with a 0.5m ArUco marker already placed on the ground
(`Tools/simulation/gz/worlds/aruco.sdf`, `PX4_GZ_WORLD=aruco`). The
marker's dictionary/ID (`DICT_4X4_50`, ID 0) was found empirically by
sweeping `arucotag.png` against every standard `cv2.aruco` dictionary,
not assumed. `LandingPadDetector` is pure Python/OpenCV (zero rclpy
dependency, same pattern as `safety_gate.py`/`mission_manager.py`), unit
tested with synthetic marker images (6 passing tests in
`tests/test_landing_pad_detector.py`), and uses a small API-compatibility
shim (`hasattr(cv2.aruco, "ArucoDetector")`) so the same code works on
both the modern OpenCV 4.7+ class API (Windows' pip `opencv-python`, used
for fast local unit tests) and the legacy pre-4.7 functional API (WSL's
pinned apt `python3-opencv`, 4.5.4, which is what actually runs against
live SITL).

Environment issues found and fixed, in order:

1. **WSL's apt `python3-opencv` (4.5.4) was broken**: `import cv2` failed
   with a numpy 1.x/2.x ABI mismatch — a pip-installed numpy 2.2.6 was
   shadowing the apt numpy the system `cv2` was built against. Fixed with
   `pip3 install 'numpy<2'`.
2. **`ros-humble-ros-gz` (needed to bridge the Gazebo camera image into
   ROS 2) wasn't installed**; installed via
   `sudo apt install ros-humble-ros-gz`.
3. **The real one: the apt `ros-humble-ros-gz-bridge` package is linked
   against `ignition-transport11`** (the old "Ignition" Gazebo Transport,
   pre-Harmonic), while this PX4 checkout's SITL runs Gazebo Sim 8.14.0
   ("Harmonic") on `gz-transport13` — two separate, incompatible
   transport buses. Confirmed via `ldd libros_gz_bridge.so` showing
   `libignition-transport11.so.11`/`libignition-msgs8.so.8`. The bridge
   process started fine, registered a real ROS 2 publisher, and even
   showed up in `gz topic -i` as a "subscriber" (actually just gz-sim's
   own loopback self-reference) — but never received a single frame.
   `gz topic -e`/`gz topic -l` (built against the correct
   `gz-transport13`) worked the whole time, which is what pointed at a
   transport-layer version mismatch rather than a Gazebo-side problem.
   Fixed by cloning `github.com/gazebosim/ros_gz` (humble branch) and
   building `ros_gz_interfaces`/`ros_gz_bridge`/`ros_gz_image` from
   source with `GZ_VERSION=harmonic` against the already-installed
   `libgz-sim8-dev`/`libgz-transport13-dev`/`libgz-msgs10-dev` headers,
   then overlaying that workspace's `install/setup.bash`
   (`--allow-overriding ros_gz_bridge ros_gz_image`) after
   `/opt/ros/humble` before launching. Confirmed fixed: the rebuilt
   `libros_gz_bridge.so` links against
   `libgz-transport13.so.13`/`libgz-msgs10.so.10`, and a real external
   subscriber address appeared in `gz topic -i` instead of gz-sim's own
   loopback.

Design bug found via live testing (the actual point of running the full
system instead of trusting unit tests, same pattern as the Phase 2/4
interaction bugs): the first mission-stack launch with real perception
hit `MISSION_ABORT` within seconds of arming, during ordinary
SEARCH-phase hover. `safety_gate_node` was forwarding raw perception
confidence to `AIStatus.confidence` *whenever a marker was merely
visible*, even faint/distant (~0.15-0.4 while still climbing to 5m) —
below `SafetyLimits.land_confidence_threshold` (0.50), and below
`MissionManager`'s own `APPROACH_CONFIDENCE_THRESHOLD` (0.80) that would
ever actually act on it. Five consecutive low-confidence ticks (0.5s at
10Hz) permanently aborted a mission that wasn't depending on that
detection at all. Fixed: added `/sentinelflight/mission_trusting_perception`
(`std_msgs/Bool`, published by `mission_manager_node`, true only in
`APPROACH_TARGET`/`ALIGN`/`DESCEND`/`LAND`); `safety_gate_node` now only
forwards real perception confidence when that's true, else the same
`NO_TARGET_AI_CONFIDENCE=0.95` placeholder used when no target is
detected at all — keeping "is the mission state machine gated on this
detection" and "should the safety gate trust this detection" as two
separate, correctly-scoped questions instead of conflating them.

Verified against live SITL post-fix: real `target_detected: true`,
`confidence: 0.151...`, real pixel-offset values from the live camera
feed, and a correspondingly `APPROVED`/`NORMAL` safety event during
SEARCH-phase hover (no false abort). `offboard_controller`'s
hold-duration fallback timer then triggered `AUTO_LAND` (MissionManager
never crossed 0.80 confidence while holding steady at the 5m SEARCH
altitude — see calibration note below). As PX4's `AUTO_LAND` physically
descended the vehicle, the marker grew in-frame and confidence rose with
it; `MissionManager` — still evaluating every tick against the real
vehicle_z and perception — followed along through
`APPROACH_TARGET → ALIGN → DESCEND → LAND` on its own
(`mission_land_requested` flipped `true`), a genuine live confirmation
that the full state-machine chain and its thresholds work, even though
it was PX4's descent driving it rather than a `MissionManager`-commanded
one at that point. During that same descent, confidence fluctuated
enough (real camera noise, unsmoothed heuristic) to correctly and
intentionally trip `SafetyGate`'s 5-consecutive-rejection abort a second
time — this one is the safety gate doing its job, not a bug, but it
means the mission didn't complete a clean uninterrupted autonomous
landing this run.

**Known limitation, not fixed this session — confidence heuristic
calibration.** `LandingPadDetector`'s confidence is
`min(1, marker_area_px / (frame_area_px * CONFIDENT_AREA_FRACTION))`,
`CONFIDENT_AREA_FRACTION=0.15`. The camera is wide-FOV
(`horizontal_fov=1.74` rad, 1280x960) and the marker is small (0.5m); at
a 5m hover the marker covers only ~0.24% of frame area, giving confidence
~0.016 with the current constant — calibrated against the wrong
intuition (a close-up, filled-frame marker) rather than this camera's
actual geometry. Flagged as follow-up: recalibrate against the real
geometry above (roughly `CONFIDENT_AREA_FRACTION≈0.003` gets a 5m hover
near the 0.80 threshold) and/or add hysteresis/smoothing so brief
confidence dips during a real descent don't accumulate toward
`SafetyGate`'s fixed 5-rejection abort.

Full run: 3252 telemetry rows, `docs/evidence/phase5_mission_sample.csv`
+ [evidence/phase5_analysis_output.txt](evidence/phase5_analysis_output.txt).
The known Phase 2/3/4 "heartbeat delays disarm after `AUTO_LAND`"
limitation is still present, unchanged.

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
