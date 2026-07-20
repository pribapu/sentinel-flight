from setuptools import find_packages, setup

package_name = "sentinel_flight_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
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
            "mission_manager = sentinel_flight_control.mission_manager:main",
            "offboard_controller = sentinel_flight_control.offboard_controller:main",
        ],
    },
)
