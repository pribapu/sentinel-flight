"""Landing-pad perception node -- thin ROS 2 wrapper around LandingPadDetector.

Subscribes to the bridged camera image topic (see
ros2_ws/src/sentinel_flight_control/launch/mission.launch.py for the
Gazebo -> ROS 2 image bridge), runs ArUco detection on every frame, and
publishes the result on /sentinelflight/perception_status. Never touches
flight commands directly (see docs/architecture.md).
"""

from __future__ import annotations

import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from sentinel_flight_msgs.msg import PerceptionStatus

from sentinel_flight_perception.landing_pad_detector import LandingPadDetector

CAMERA_IMAGE_TOPIC = "/sentinelflight/camera/image_raw"
PERCEPTION_STATUS_TOPIC = "/sentinelflight/perception_status"


class LandingPadDetectorNode(Node):
    def __init__(self) -> None:
        super().__init__("sentinelflight_landing_pad_detector")

        self.detector = LandingPadDetector()
        self.bridge = CvBridge()
        self.status_pub = self.create_publisher(PerceptionStatus, PERCEPTION_STATUS_TOPIC, 10)
        self.create_subscription(Image, CAMERA_IMAGE_TOPIC, self._on_image, qos_profile_sensor_data)

    def _on_image(self, msg: Image) -> None:
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        result = self.detector.detect(frame)

        status_msg = PerceptionStatus()
        status_msg.target_detected = result.target_detected
        status_msg.confidence = result.confidence
        status_msg.center_x_offset = result.center_x_offset
        status_msg.center_y_offset = result.center_y_offset
        self.status_pub.publish(status_msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = LandingPadDetectorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
