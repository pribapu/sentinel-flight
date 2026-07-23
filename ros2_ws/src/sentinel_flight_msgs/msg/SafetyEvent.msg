# Mirrors sentinel_flight_control.safety_gate.SafetyDecision for cross-node
# telemetry/dashboard consumption. status/state are uint8 constants because
# .msg has no enum type -- the values below MUST be kept in sync by hand
# with SafetyStatus / SafetyState in safety_gate.py.

float64 timestamp          # epoch seconds (matches TelemetryLogger's "timestamp" column)
uint8 status
uint8 state
string reason
float32 ai_confidence
bool failsafe_active

uint8 STATUS_APPROVED = 0
uint8 STATUS_REJECTED_LOW_CONFIDENCE = 1
uint8 STATUS_REJECTED_ALTITUDE_LIMIT = 2
uint8 STATUS_REJECTED_GEOFENCE = 3
uint8 STATUS_REJECTED_MAX_VELOCITY = 4
uint8 STATUS_REJECTED_OBSTACLE_PROXIMITY = 5
uint8 STATUS_FAILSAFE_HOVER = 6
uint8 STATUS_FAILSAFE_LAND = 7
uint8 STATUS_MISSION_ABORT = 8

uint8 STATE_NORMAL = 0
uint8 STATE_CAUTION = 1
uint8 STATE_FAILSAFE_HOVER = 2
uint8 STATE_FAILSAFE_LAND = 3
uint8 STATE_MISSION_ABORT = 4
