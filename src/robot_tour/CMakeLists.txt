cmake_minimum_required(VERSION 3.8)
project(robot_tour)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(social_robot_interfaces REQUIRED)
find_package(nav2_core REQUIRED)
find_package(nav2_util REQUIRED)
find_package(pluginlib REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

add_library(tour_guide SHARED src/tour_guide.cpp)
ament_target_dependencies(tour_guide rclcpp rclcpp_action rclcpp_components nav2_msgs geometry_msgs social_robot_interfaces)
rclcpp_components_register_node(tour_guide PLUGIN "robot_tour::WaypointFollowerClient" EXECUTABLE tour_guide_start)
add_library(subtour SHARED src/subtour.cpp)
target_include_directories(subtour PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
ament_target_dependencies(subtour rclcpp rclcpp_action rclcpp_components nav2_msgs geometry_msgs social_robot_interfaces)
rclcpp_components_register_node(subtour PLUGIN "robot_tour::SubtourNode" EXECUTABLE subtour_start)
install(TARGETS
  tour_guide
  subtour
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)

add_library(talk_at_waypoint SHARED plugins/talk_at_waypoint.cpp)
target_include_directories(talk_at_waypoint PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
ament_target_dependencies(
  talk_at_waypoint
  rclcpp
  rclcpp_lifecycle
  std_msgs
  nav2_core
  nav2_util
  pluginlib
)

install(
  DIRECTORY include/
  DESTINATION include
)

install(
  TARGETS talk_at_waypoint
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

ament_export_libraries(
  talk_at_waypoint
)
ament_export_include_directories(
  include
)
ament_export_dependencies(
  rclcpp
  rclcpp_lifecycle
  std_msgs
  nav2_core
  nav2_util
  pluginlib
)
ament_export_targets(
  export_${PROJECT_NAME}
)

pluginlib_export_plugin_description_file(nav2_waypoint_follower plugins.xml)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
