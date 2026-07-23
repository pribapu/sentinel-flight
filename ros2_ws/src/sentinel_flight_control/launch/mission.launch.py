"""Brings up the full SentinelFlight mission stack: perception (Phase 5),
mission planner, safety gate, offboard controller, and telemetry logger as
separate ROS 2 nodes wired together over sentinel_flight_msgs topics, plus
a ros_gz_bridge camera bridge so the perception node gets real frames from
Gazebo.

    ros2 launch sentinel_flight_control mission.launch.py

Requires PX4 SITL launched against the "aruco" world with a camera-equipped
vehicle, e.g.:

    PX4_GZ_WORLD=aruco HEADLESS=1 make px4_sitl gz_x500_mono_cam_down

The Gazebo camera topic name below was confirmed live via `gz topic -l`
against that world/vehicle combination -- see docs/roadmap.md
"Phase 5 notes" (Gazebo topic names are instance-numbered and not something
to assume from the SDF alone).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

CAMERA_IMAGE_TOPIC = "/sentinelflight/camera/image_raw"

# Confirmed live via `gz topic -l` with PX4_GZ_WORLD=aruco and
# gz_x500_mono_cam_down -- see docs/roadmap.md "Phase 5 notes".
GZ_CAMERA_IMAGE_TOPIC = "/world/aruco/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image"


def generate_launch_description() -> LaunchDescription:
    telemetry_csv_path_arg = DeclareLaunchArgument("telemetry_csv_path", default_value="logs/mission.csv")

    return LaunchDescription(
        [
            telemetry_csv_path_arg,
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name="sentinelflight_camera_bridge",
                arguments=[f"{GZ_CAMERA_IMAGE_TOPIC}@sensor_msgs/msg/Image[gz.msgs.Image"],
                remappings=[(GZ_CAMERA_IMAGE_TOPIC, CAMERA_IMAGE_TOPIC)],
            ),
            Node(
                package="sentinel_flight_perception",
                executable="landing_pad_detector_node",
                name="sentinelflight_landing_pad_detector",
            ),
            Node(
                package="sentinel_flight_control",
                executable="mission_manager_node",
                name="sentinelflight_mission_manager",
            ),
            Node(
                package="sentinel_flight_control",
                executable="safety_gate_node",
                name="sentinelflight_safety_gate",
            ),
            Node(
                package="sentinel_flight_control",
                executable="offboard_controller",
                name="sentinelflight_offboard_controller",
            ),
            Node(
                package="sentinel_flight_telemetry",
                executable="telemetry_logger_node",
                name="sentinelflight_telemetry_logger",
                parameters=[{"csv_path": LaunchConfiguration("telemetry_csv_path")}],
            ),
        ]
    )
