"""Landing-pad perception: pure OpenCV ArUco marker detection, zero rclpy
dependency (same pattern as safety_gate.py/mission_manager.py) so it's unit
testable without ROS 2.

Beginner path per docs/roadmap.md Phase 5: cv2.aruco marker detection --
proves the full pipeline before any model training (advanced path: train
YOLOv8n/MobileNet SSD, export to ONNX/TensorRT for Jetson, Phase 8).

The marker dictionary default below was determined empirically against the
ArUco texture PX4-Autopilot ships at
Tools/simulation/gz/models/arucotag/arucotag.png (see docs/roadmap.md
"Phase 5 notes" for how it was found).

Never touches flight commands directly -- landing_pad_detector_node.py
publishes this module's DetectionResult as
sentinel_flight_msgs/msg/PerceptionStatus; mission_manager.py consumes it.

center_x_offset/center_y_offset sign convention (image pixel axes, not
camera/body/world frame) is a first approximation -- confirmed/flipped
against live SITL during Phase 5 verification if the drone approaches the
marker backwards (see docs/roadmap.md "Phase 5 notes").
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Empirically confirmed against PX4-Autopilot's
# Tools/simulation/gz/models/arucotag/arucotag.png (dictionary DICT_4X4_50,
# marker ID 0) by sweeping all standard cv2.aruco dictionaries with a
# padded quiet zone -- see docs/roadmap.md "Phase 5 notes". Detection on
# the raw texture alone fails (no quiet zone); a real camera view of the
# ground plane naturally provides one.
DEFAULT_ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
DEFAULT_TARGET_MARKER_ID = 0

# A detected marker filling this fraction of the frame's area is treated as
# a fully-confident (1.0) detection; smaller/farther markers scale down
# linearly from there.
CONFIDENT_AREA_FRACTION = 0.15


@dataclass(frozen=True)
class DetectionResult:
    target_detected: bool
    center_x_offset: float
    center_y_offset: float
    confidence: float
    estimated_distance_m: float | None = None


def _get_dictionary(dictionary_id: int):
    if hasattr(cv2.aruco, "getPredefinedDictionary"):
        return cv2.aruco.getPredefinedDictionary(dictionary_id)
    return cv2.aruco.Dictionary_get(dictionary_id)  # OpenCV < 4.7 (WSL's apt python3-opencv is 4.5.4)


def _detect_markers(gray: np.ndarray, dictionary):
    if hasattr(cv2.aruco, "ArucoDetector"):
        detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
        corners, ids, _ = detector.detectMarkers(gray)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, dictionary, parameters=cv2.aruco.DetectorParameters_create()
        )
    return corners, ids


def _polygon_area(points: np.ndarray) -> float:
    """Shoelace formula over a marker's 4 corners."""
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


class LandingPadDetector:
    """ArUco marker detector.

    target_marker_id=None accepts any marker from the configured
    dictionary, so it isn't overly brittle if more than one tag is ever
    present in frame.
    """

    def __init__(
        self,
        dictionary_id: int = DEFAULT_ARUCO_DICTIONARY,
        target_marker_id: int | None = DEFAULT_TARGET_MARKER_ID,
    ) -> None:
        self.dictionary = _get_dictionary(dictionary_id)
        self.target_marker_id = target_marker_id

    def detect(self, frame: np.ndarray) -> DetectionResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        corners, ids = _detect_markers(gray, self.dictionary)

        marker_corners = self._select_marker(corners, ids)
        if marker_corners is None:
            return DetectionResult(
                target_detected=False, center_x_offset=0.0, center_y_offset=0.0, confidence=0.0
            )

        frame_h, frame_w = gray.shape[:2]
        pts = marker_corners.reshape(4, 2)
        centroid_x, centroid_y = pts.mean(axis=0)

        # Normalized to roughly [-1, 1], matching MissionManager's
        # CENTERED_OFFSET_TOLERANCE range.
        center_x_offset = (centroid_x - frame_w / 2) / (frame_w / 2)
        center_y_offset = (centroid_y - frame_h / 2) / (frame_h / 2)

        marker_area = _polygon_area(pts)
        frame_area = float(frame_w * frame_h)
        confidence = min(1.0, marker_area / (frame_area * CONFIDENT_AREA_FRACTION))

        return DetectionResult(
            target_detected=True,
            center_x_offset=float(center_x_offset),
            center_y_offset=float(center_y_offset),
            confidence=float(confidence),
        )

    def _select_marker(self, corners, ids) -> np.ndarray | None:
        if ids is None or len(corners) == 0:
            return None
        if self.target_marker_id is None:
            return corners[0]
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            if int(marker_id) == self.target_marker_id:
                return marker_corners
        return None
