"""Landing-pad perception node (interface stub).

Status: NOT YET IMPLEMENTED. Planned as Phase 5 (Option A) in
docs/roadmap.md — see that file for the beginner (OpenCV ArUco/AprilTag)
vs. advanced (YOLOv8n/MobileNet SSD) implementation paths.

Design contract (see docs/architecture.md):
    - Reads camera frames from the simulated (or Jetson-mounted) camera.
    - Publishes a confidence-scored detection result. Never touches flight
      commands directly — mission_manager.py consumes this topic.

Planned ROS 2 topic:
    Publishes:
        /sentinelflight/perception_status  -> PerceptionResult (see
        sentinel_flight_control.mission_manager.PerceptionResult for the
        shared data contract both sides agree on)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionResult:
    landing_pad_detected: bool
    center_x_offset: float
    center_y_offset: float
    confidence: float
    estimated_distance_m: float | None = None


class LandingPadDetector:
    """TODO(week-5): implement per docs/roadmap.md Phase 5.

    Beginner path: cv2.aruco / AprilTag marker detection — proves the full
    pipeline before any model training is needed.
    Advanced path: train YOLOv8n or similar, export to ONNX/TensorRT for
    Jetson deployment (docs/roadmap.md Phase 8).
    """

    def __init__(self):
        raise NotImplementedError(
            "LandingPadDetector is a design stub — implement per docs/roadmap.md Phase 5"
        )

    def detect(self, frame) -> DetectionResult:
        raise NotImplementedError
