"""Brings up the full SentinelFlight mission stack (Phase 4): mission
planner, safety gate, offboard controller, and telemetry logger as four
separate ROS 2 nodes wired together over sentinel_flight_msgs topics.

    ros2 launch sentinel_flight_control mission.launch.py
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    telemetry_csv_path_arg = DeclareLaunchArgument("telemetry_csv_path", default_value="logs/mission.csv")

    return LaunchDescription(
        [
            telemetry_csv_path_arg,
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
