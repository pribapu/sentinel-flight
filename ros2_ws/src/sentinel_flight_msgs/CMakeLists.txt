cmake_minimum_required(VERSION 3.8)
project(sentinel_flight_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Setpoint.msg"
  "msg/SafetyEvent.msg"
)

ament_package()
