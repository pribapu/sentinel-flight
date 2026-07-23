"""Unit tests for the ArUco landing-pad detector.

Synthesizes marker images rather than requiring camera hardware or a
Gazebo instance -- mirrors tests/test_safety_gate.py's conventions (flat
functions, factory helpers, no mocking). Run with:
    pytest tests/test_landing_pad_detector.py -v
"""

import cv2
import numpy as np

from sentinel_flight_perception.landing_pad_detector import (
    DEFAULT_ARUCO_DICTIONARY,
    LandingPadDetector,
    _get_dictionary,
)

FRAME_SIZE = 640  # square canvas, pixels


def _draw_marker(dictionary, marker_id, side_pixels):
    if hasattr(cv2.aruco, "generateImageMarker"):
        return cv2.aruco.generateImageMarker(dictionary, marker_id, side_pixels)
    return cv2.aruco.drawMarker(dictionary, marker_id, side_pixels)


def make_frame(marker_id=0, side_pixels=0, top_left=(0, 0)):
    """A blank FRAME_SIZE x FRAME_SIZE grayscale canvas, optionally with a
    synthetic marker pasted at top_left. side_pixels=0 means no marker."""
    canvas = np.full((FRAME_SIZE, FRAME_SIZE), 255, dtype=np.uint8)
    if side_pixels:
        dictionary = _get_dictionary(DEFAULT_ARUCO_DICTIONARY)
        marker_img = _draw_marker(dictionary, marker_id, side_pixels)
        x, y = top_left
        canvas[y : y + side_pixels, x : x + side_pixels] = marker_img
    return canvas


def test_no_marker_reports_not_detected():
    detector = LandingPadDetector()
    result = detector.detect(make_frame())
    assert result.target_detected is False
    assert result.confidence == 0.0


def test_centered_marker_reports_near_zero_offsets():
    side = 200
    top_left = ((FRAME_SIZE - side) // 2, (FRAME_SIZE - side) // 2)
    detector = LandingPadDetector()
    result = detector.detect(make_frame(side_pixels=side, top_left=top_left))
    assert result.target_detected is True
    assert abs(result.center_x_offset) < 0.05
    assert abs(result.center_y_offset) < 0.05


def test_marker_offset_to_the_right_reports_positive_x_offset():
    side = 120
    top_left = (420, 260)  # centroid x=480, frame center x=320
    detector = LandingPadDetector()
    result = detector.detect(make_frame(side_pixels=side, top_left=top_left))
    assert result.target_detected is True
    assert result.center_x_offset > 0.3


def test_marker_offset_to_the_left_reports_negative_x_offset():
    side = 120
    top_left = (100, 260)  # centroid x=160, frame center x=320
    detector = LandingPadDetector()
    result = detector.detect(make_frame(side_pixels=side, top_left=top_left))
    assert result.target_detected is True
    assert result.center_x_offset < -0.3


def test_larger_marker_reports_higher_confidence_than_smaller():
    detector = LandingPadDetector()
    small = detector.detect(make_frame(side_pixels=60, top_left=(290, 290)))
    large = detector.detect(make_frame(side_pixels=300, top_left=(170, 170)))
    assert small.target_detected is True
    assert large.target_detected is True
    assert large.confidence > small.confidence


def test_target_marker_id_filters_other_ids():
    side = 200
    top_left = ((FRAME_SIZE - side) // 2, (FRAME_SIZE - side) // 2)
    frame = make_frame(marker_id=5, side_pixels=side, top_left=top_left)
    detector = LandingPadDetector(target_marker_id=99)
    result = detector.detect(frame)
    assert result.target_detected is False
