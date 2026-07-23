from setuptools import find_packages, setup

package_name = "sentinel_flight_perception"

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
    description="Edge AI perception (landing-pad / obstacle detection) for SentinelFlight.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "landing_pad_detector_node = sentinel_flight_perception.landing_pad_detector_node:main",
        ],
    },
)
