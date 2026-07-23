# Mirrors sentinel_flight_control.mission_manager.PerceptionResult (minus
# estimated_distance_m -- not used by MissionManager.step() today, cut from
# Phase 5's scope; see docs/roadmap.md "Phase 5 notes"). Carried on
# /sentinelflight/perception_status.

bool target_detected
float32 confidence
float32 center_x_offset
float32 center_y_offset
