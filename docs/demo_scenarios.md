# Demo Scenarios

## Available today: safety gate scenarios

These run right now with `pytest tests/test_safety_gate.py -v` — no
simulator required.

1. **Safe command approved** — normal setpoint within all limits passes
   through unchanged.
2. **Unsafe altitude command rejected** — proposed z=50m (max is 20m) is
   rejected and the drone holds position instead.
3. **Low AI confidence causes hover** — confidence drops below 0.70 and the
   gate commands a hover regardless of what the mission planner proposed.
4. **Critical AI confidence forces landing** — confidence below 0.50 forces
   an immediate landing.
5. **Geofence violation rejected** — a setpoint outside the ±20m box is
   rejected.
6. **Obstacle proximity halts forward motion** — an obstacle inside 2m
   causes the gate to override forward motion with a hover.
7. **Stale command triggers failsafe** — no new command for 500ms → hover;
   for 3s → land.
8. **Repeated unsafe commands trigger mission abort** — 5 consecutive
   rejections force `MISSION_ABORT` and landing, protecting against a
   mission planner stuck in a bad state.

## Target end-to-end demo (post Phase 1-8, see roadmap.md)

1. Drone takes off.
2. Drone searches for the landing pad.
3. AI detects the landing pad with a confidence score.
4. Mission planner proposes movement toward the pad.
5. Safety gate validates each proposed command.
6. Drone aligns above the pad.
7. AI confidence briefly drops (simulated occlusion).
8. Safety gate pauses the descent and commands a hover.
9. Confidence recovers.
10. Drone lands safely.
11. Dashboard shows telemetry and the safety event timeline live.

This is the scenario the project is being built toward — see
[roadmap.md](roadmap.md) for what's needed to get there.
