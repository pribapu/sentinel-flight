import os
from glob import glob

from setuptools import find_packages, setup

package_name = "sentinel_flight_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Prithu Bapu",
    maintainer_email="pribapu@gmail.com",
    description="Mission planning, runtime assurance (safety gate), and PX4 offboard control for SentinelFlight.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "mission_manager_node = sentinel_flight_control.mission_manager_node:main",
            "safety_gate_node = sentinel_flight_control.safety_gate_node:main",
            "offboard_controller = sentinel_flight_control.offboard_controller:main",
        ],
    },
)
