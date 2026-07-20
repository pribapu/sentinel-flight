# Resume Bullets

Use the bullet(s) that match what's actually built at the time you're
applying — see [roadmap.md](roadmap.md) for current status. Don't claim a
phase that isn't done yet.

## Available now (safety gate implemented + tested)

> Designed and implemented a runtime assurance layer in Python that
> validates AI-generated UAV flight commands against altitude, velocity,
> geofence, confidence, and timeout constraints, with a 14-case unit test
> suite covering failure modes including stale commands, low-confidence AI
> output, and repeated unsafe proposals.

## After Phase 1-2 (PX4/ROS 2 offboard control working)

> Implemented ROS 2 offboard control for a PX4-simulated UAV, enabling
> autonomous takeoff, waypoint navigation, hover, and landing through
> custom flight-control nodes.

## After Phase 3 (telemetry)

> Built a telemetry and safety-event logging pipeline for UAV autonomy
> testing, capturing vehicle state, AI confidence, command approvals, and
> failsafe activations for post-mission analysis.

## After Phase 5-6 (perception + mission planner)

> Integrated embedded AI perception into a PX4/ROS 2 UAV simulation, using
> landing-zone or obstacle detection outputs to guide autonomous mission
> behavior under safety constraints.

## After full MVP (Phases 1-9)

> Built SentinelFlight, a safety-aware UAV autonomy stack using PX4, ROS 2,
> and Gazebo, enabling simulated autonomous takeoff, waypoint navigation,
> AI-assisted landing, and failsafe recovery.

> Developed telemetry logging and validation tooling to analyze UAV state,
> AI confidence, rejected commands, and failsafe activations across normal
> and fault-injected mission scenarios.

## Tagline

> SentinelFlight: a safety-aware UAV autonomy stack combining PX4, ROS 2,
> edge AI perception, and runtime assurance for reliable autonomous flight
> control.
