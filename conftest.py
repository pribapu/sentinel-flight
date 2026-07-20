"""Makes the ROS 2 package sources importable by pytest without a ROS 2/colcon
build. Each ament_python package's inner directory is added to sys.path so
`import sentinel_flight_control...` works directly from source.
"""

import sys
from pathlib import Path

ROS2_SRC = Path(__file__).parent / "ros2_ws" / "src"

for package_dir in ("sentinel_flight_control", "sentinel_flight_perception", "sentinel_flight_telemetry"):
    path = str(ROS2_SRC / package_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
