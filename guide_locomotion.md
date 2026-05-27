# Locomotion Subsystem Guide

This guide explains only the locomotion side of the workspace. It intentionally leaves out `turtlebot_LLM_control` and `Pepper_HRI`. Use this when you want to install, run, configure, and debug navigation, saved tours, optimized subtours, waypoint triggers, and docking.

The locomotion subsystem answers one practical question: how does the robot move through saved tour waypoints and optionally return to its dock?

## 1. Project Overview

The locomotion subsystem can:

- save the robot's current pose as a tour waypoint;
- retrieve saved tour waypoints from a SQLite database;
- send a full saved tour to Nav2;
- send a selected subtour to Nav2 after optimizing the waypoint order;
- publish the correct original waypoint index at each reached waypoint;
- wait for a `/done_talking` signal before moving to the next waypoint;
- dock after a tour when `dock_after_tour` is enabled;
- run in simulation or on real TurtleBot3 hardware.

Main launch options:

```bash
ros2 launch tour_manager locomotion_test.launch.py
```

or, if you want the larger launch but with HRI/LLM disabled:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false enable_intent:=false
```

## 2. Included Packages

| Package | Purpose |
| --- | --- |
| `tour_manager` | Launches the locomotion nodes and stores/retrieves saved waypoints. |
| `robot_tour` | Sends full tours/subtours to Nav2 and provides the waypoint task plugin. |
| `social_robot_interfaces` | Defines custom `TspCommand`, `Tours`, and `Description` interfaces. |
| `docking` | Converts `/dock_command` into an OpenNav docking action. |
| `speech_locomotion_interface` | Optional command bridge from `/speech/intent` JSON to locomotion topics. |
| `turtlebot3_navigation2` | Nav2 params, maps, waypoint follower config. |
| `turtlebot3_bringup` | Real TurtleBot3 hardware bringup. |
| `turtlebot3_gazebo` | TurtleBot3 simulation launch. |
| `open_nav/opennav_docking` | Docking action server and docking framework. |

Excluded from this guide:

- `Pepper_HRI`;
- `turtlebot_LLM_control`.

## 3. Important Files

```text
src/tour_manager/launch/locomotion_test.launch.py
src/tour_manager/launch/tour_manager_launch.py
src/tour_manager/config/tour_manager_params.yaml
src/tour_manager/tour_manager/tour_manager_service.py
src/tour_manager/tour_manager/tour_saver.py
src/robot_tour/src/tour_guide.cpp
src/robot_tour/src/subtour.cpp
src/robot_tour/plugins/talk_at_waypoint.cpp
src/docking/docking/dock_listener.py
src/turtlebot3/turtlebot3_navigation2/param/humble/waffle_pi.yaml
```

## 4. Dependencies

### Hardware

For real operation:

- TurtleBot3-compatible mobile base;
- LDS lidar;
- OpenCR board connected by USB, commonly `/dev/ttyACM0`;
- laptop or onboard computer running ROS 2 Humble;
- saved map for localization;
- known dock location if docking is used.

For simulation:

- Gazebo-capable computer;
- no physical robot required.

### Software

Main dependencies:

- ROS 2 Humble;
- Nav2;
- TurtleBot3 packages;
- `geometry_msgs`, `std_msgs`, `nav2_msgs`;
- `rclcpp`, `rclpy`, `rclcpp_action`, `rclcpp_components`;
- `tf2_ros`;
- `pluginlib`, `nav2_core`, `nav2_util`;
- OpenNav docking packages;
- SQLite command line tool for database inspection.

Install missing ROS dependencies:

```bash
cd /home/tom/big_ws
source /opt/ros/humble/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

## 5. Build And Source

Build everything:

```bash
cd /home/tom/big_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

Build only the locomotion packages after edits:

```bash
cd /home/tom/big_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select robot_tour tour_manager docking speech_locomotion_interface turtlebot3_navigation2
source install/setup.bash
```

Important: launch files read installed package files. If you edit `src/tour_manager/config/tour_manager_params.yaml`, rebuild `tour_manager`:

```bash
colcon build --packages-select tour_manager
source install/setup.bash
```

Check the installed config:

```bash
sed -n '1,80p' install/tour_manager/share/tour_manager/config/tour_manager_params.yaml
```

## 6. Running The Locomotion System

### Simulation

```bash
cd /home/tom/big_ws
source install/setup.bash
ros2 launch tour_manager locomotion_test.launch.py
```

If using the integrated launch with HRI and LLM disabled:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=sim use_sim_time:=true enable_pepper:=false enable_intent:=false
```

Expected result:

- Gazebo starts;
- TurtleBot3 appears in simulation;
- Nav2 launches;
- `tour_manager`, `tour_saver`, `tour_guide`, `subtour`, `dock_listener`, and docking lifecycle nodes start;
- `/follow_waypoints` action becomes available.

### Real TurtleBot3

```bash
cd /home/tom/big_ws
source install/setup.bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=real use_sim_time:=false enable_pepper:=false enable_intent:=false usb_port:=/dev/ttyACM0
```

If the USB port is different:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

## 7. System Data Flow

Full tour:

```text
/tour_command
  -> tour_guide
  -> /tour_retrieve service
  -> /tour_waypoint_order
  -> /follow_waypoints action
  -> Nav2 waypoint_follower
  -> TalkAtWaypoint plugin
  -> /talk_command
  -> waits for /done_talking
```

Optimized subtour:

```text
/tsp_command
  -> subtour
  -> /tour_retrieve service
  -> TSP-style route optimization
  -> /tour_waypoint_order
  -> /follow_waypoints action
  -> TalkAtWaypoint plugin
  -> /talk_command
  -> waits for /done_talking
```

Docking:

```text
/dock_command
  -> dock_listener
  -> /dock_robot action
  -> OpenNav docking server
```

## 8. Configuration

Main locomotion config:

```text
src/tour_manager/config/tour_manager_params.yaml
```

Important section:

```yaml
tour_guide:
  ros__parameters:
    dock_after_tour: true
    dock_command_topic: /dock_command
    waypoint_order_topic: /tour_waypoint_order

subtour:
  ros__parameters:
    command_topic: /tsp_command
    action_name: /follow_waypoints
    current_pose_topic: /amcl_pose
    dock_after_tour: true
    dock_command_topic: /dock_command
    waypoint_order_topic: /tour_waypoint_order
    max_2opt_iterations: 10000
```

Nav2 waypoint plugin config:

```text
src/turtlebot3/turtlebot3_navigation2/param/humble/waffle_pi.yaml
```

Important section:

```yaml
waypoint_follower:
  ros__parameters:
    waypoint_task_executor_plugin: "talk_at_waypoint"
    talk_at_waypoint:
      plugin: "robot_tour::TalkAtWaypoint"
      enabled: true
      waypoint_pause_duration: 200
      waypoint_order_topic: /tour_waypoint_order
```

## 9. Subsystem: Tour Storage

Package:

```text
tour_manager
```

Nodes:

| Node | Purpose |
| --- | --- |
| `/tour_manager` | Stores waypoints in `tours.db` and serves them through services. |
| `/tour_saver` | Saves the current `map -> base_link` pose when commanded. |

Topics/services:

| Name | Type | Purpose |
| --- | --- | --- |
| `/save_tour_command` | `std_msgs/String` | Ask `tour_saver` to save current robot pose. |
| `/save_tour` | `geometry_msgs/PoseStamped` | Internal pose message from saver to manager. |
| `/tour_retrieve` | `social_robot_interfaces/srv/Tours` | Return saved tour poses. |
| `/retrieve_description` | `social_robot_interfaces/srv/Description` | Return text description for a waypoint. |

Save current robot pose as a tour waypoint:

```bash
ros2 topic pub --once /save_tour_command std_msgs/msg/String "{data: save}"
```

Inspect saved waypoints:

```bash
sqlite3 tours.db 'SELECT rowid, px, py, pz, qx, qy, qz, qw, description FROM tours;'
```

Retrieve waypoints through ROS:

```bash
ros2 service call /tour_retrieve social_robot_interfaces/srv/Tours "{idx: 0}"
```

## 10. Subsystem: Full Tour

File:

```text
src/robot_tour/src/tour_guide.cpp
```

Node launched as:

```text
/tour_guide
```

Start a full tour:

```bash
ros2 topic pub --once /tour_command std_msgs/msg/String "{data: start}"
```

What happens:

1. `tour_guide` receives `/tour_command`.
2. It calls `/tour_retrieve`.
3. It publishes an identity waypoint map, such as `[0, 1, 2, 3]`, to `/tour_waypoint_order`.
4. It sends every saved pose to Nav2 `/follow_waypoints`.
5. If the action succeeds and `dock_after_tour` is true, it publishes `"dock"` to `/dock_command`.

Useful logs:

```text
received start
Published waypoint order map with N entries
Sending goal
Goal accepted by server, waiting for result
Published dock command after tour completion
```

## 11. Subsystem: Optimized Subtour

File:

```text
src/robot_tour/src/subtour.cpp
```

Node launched as:

```text
/subtour
```

Start an optimized subtour:

```bash
ros2 topic pub --once /tsp_command social_robot_interfaces/msg/TspCommand "{waypoints: [0, 4, 2]}"
```

What the waypoint numbers mean:

- They are original saved tour waypoint indices.
- If you saved 9 tour points, valid values are usually `0` through `8`.
- The optimizer may reorder them for shorter travel distance.

What happens internally:

1. `subtour` receives `/tsp_command`.
2. It calls `/tour_retrieve`.
3. It validates the requested waypoint indices.
4. It selects only the requested poses.
5. It chooses a start pose closest to current `/amcl_pose`.
6. It computes straight-line distances between selected poses.
7. It creates an initial nearest-neighbor route.
8. It improves the route with 2-opt.
9. It publishes the optimized original index order on `/tour_waypoint_order`.
10. It sends optimized poses to `/follow_waypoints`.
11. It docks after success if `dock_after_tour` is true.

Useful logs:

```text
Listening for TSP waypoint lists on '/tsp_command' and sending tours to '/follow_waypoints'
Optimized 3 selected waypoints; final path length is 4.321 m
Published waypoint order map with 3 entries
Sent 3 optimized waypoints
Waypoint follower accepted the goal
Waypoint tour completed with 0 missed waypoints
```

Watch the optimized order:

```bash
ros2 topic echo /tour_waypoint_order
```

## 12. Subsystem: Talk At Waypoint Plugin

File:

```text
src/robot_tour/plugins/talk_at_waypoint.cpp
```

Plugin:

```text
robot_tour::TalkAtWaypoint
```

Purpose: publish a waypoint command when Nav2 reaches a waypoint, then wait until something publishes `/done_talking`.

Inputs:

| Topic | Type | Purpose |
| --- | --- | --- |
| `/tour_waypoint_order` | `std_msgs/Int64MultiArray` | Maps Nav2 goal index to original tour waypoint index. |
| `/done_talking` | `std_msgs/String` | Allows Nav2 to continue to the next waypoint. |

Output:

| Topic | Type | Purpose |
| --- | --- | --- |
| `/talk_command` | `std_msgs/String` | Publishes waypoint index or configured waypoint message. |

Why `/tour_waypoint_order` matters:

Nav2 only knows the local index inside the current goal. For a subtour, local index `0` might actually be original tour waypoint `4`. The map fixes that.

Example:

```text
/tsp_command requested: [0, 4, 2]
optimizer order:        [4, 0, 2]
Nav2 local indices:     [0, 1, 2]
/tour_waypoint_order:   [4, 0, 2]
```

Expected log:

```text
Arrived at goal waypoint 0 (tour waypoint 4), published talk command: '4'
```

Manually unblock waypoint waiting:

```bash
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done}"
```

## 13. Subsystem: Docking

Package:

```text
docking
```

Node:

```text
/dock_listener
```

Start docking:

```bash
ros2 topic pub --once /dock_command std_msgs/msg/String "{data: dock}"
```

Save current pose as a dock pose:

```bash
ros2 topic pub --once /save_dock_command std_msgs/msg/String "{data: save}"
```

Inspect dock database:

```bash
sqlite3 docks.db 'SELECT rowid, px, py, pz, qx, qy, qz, qw FROM docks;'
```

Important parameters:

```yaml
dock_listener:
  ros__parameters:
    database_path: docks.db
    action_name: /dock_robot
    dock_type: ''
    max_staging_time: 1000.0
    navigate_to_staging_pose: true
    use_dock_id: false
    default_dock_id: ''
    current_pose_topic: /amcl_pose
    global_frame: map
    base_frame: base_link
```

Useful logs:

```text
Received dock command: "dock"
Sending docking goal to OpenNav
Docking goal accepted
Docking feedback: navigating to staging pose, retries=0
Docking succeeded after 0 retries
```

## 14. Optional Command Bridge: `speech_locomotion_interface`

This package is still locomotion-side because it converts already-parsed intent JSON into movement commands. It does not perform LLM reasoning itself.

Node:

```text
/speech_listener
```

Input:

```text
/speech/intent std_msgs/String
```

Outputs:

```text
/tour_command
/tsp_command
/dock_command
```

Manual intent examples:

```bash
ros2 topic pub --once /speech/intent std_msgs/msg/String '{data: "{\"intent\":\"start_tour\"}"}'
```

```bash
ros2 topic pub --once /speech/intent std_msgs/msg/String '{data: "{\"intent\":\"tsp\", \"waypoints\":[0,2,4]}"}'
```

```bash
ros2 topic pub --once /speech/intent std_msgs/msg/String '{data: "{\"intent\":\"dock\"}"}'
```

## 15. Debugging Commands

### Basic ROS Checks

```bash
ros2 node list
ros2 topic list -t
ros2 service list
ros2 action list
```

Inspect nodes:

```bash
ros2 node info /subtour
ros2 node info /tour_guide
ros2 node info /tour_manager
ros2 node info /waypoint_follower
ros2 node info /dock_listener
```

### Topic Checks

```bash
ros2 topic echo /tour_command
ros2 topic echo /tsp_command
ros2 topic echo /tour_waypoint_order
ros2 topic echo /talk_command
ros2 topic echo /done_talking
ros2 topic echo /dock_command
ros2 topic echo /amcl_pose
ros2 topic echo /cmd_vel
```

Check publisher/subscriber counts:

```bash
ros2 topic info /tour_waypoint_order
ros2 topic info /talk_command
ros2 topic info /dock_command
```

### Parameter Checks

```bash
ros2 param get /subtour dock_after_tour
ros2 param get /subtour waypoint_order_topic
ros2 param get /waypoint_follower talk_at_waypoint.waypoint_order_topic
```

Change docking behavior at runtime:

```bash
ros2 param set /subtour dock_after_tour true
ros2 param set /tour_guide dock_after_tour true
```

### Action Checks

```bash
ros2 action info /follow_waypoints
ros2 action info /navigate_to_pose
ros2 action info /dock_robot
```

### Lifecycle Checks

Nav2 nodes must be active.

```bash
ros2 lifecycle nodes
ros2 lifecycle get /waypoint_follower
ros2 lifecycle get /bt_navigator
ros2 lifecycle get /controller_server
ros2 lifecycle get /planner_server
```

Expected result:

```text
active
```

### TF Checks

Tour saving needs the transform from `map` to `base_link`.

```bash
ros2 run tf2_ros tf2_echo map base_link
ros2 run tf2_ros tf2_echo odom base_link
```

### Database Checks

```bash
sqlite3 tours.db '.tables'
sqlite3 tours.db 'SELECT rowid, px, py, description FROM tours;'
sqlite3 docks.db '.tables'
sqlite3 docks.db 'SELECT rowid, px, py FROM docks;'
```

### Logging Flags

Show debug logs:

```bash
ros2 launch tour_manager locomotion_test.launch.py --ros-args --log-level debug
```

Force logs to flush quickly:

```bash
export RCUTILS_LOGGING_BUFFERED_STREAM=1
```

Use a known log folder:

```bash
export ROS_LOG_DIR=/tmp/ros_logs
mkdir -p /tmp/ros_logs
```

Show launch arguments:

```bash
ros2 launch tour_manager locomotion_test.launch.py --show-args
```

## 16. Troubleshooting

### Config says `dock_after_tour: true`, but runtime says false

Cause: edited source YAML was not installed.

Fix:

```bash
cd /home/tom/big_ws
colcon build --packages-select tour_manager
source install/setup.bash
ros2 param get /subtour dock_after_tour
```

### No docking after tour

Check:

```bash
ros2 param get /subtour dock_after_tour
ros2 topic echo /dock_command
```

Expected success logs:

```text
Waypoint tour completed with 0 missed waypoints
Published dock command after tour completion
```

Docking is only sent after a successful waypoint action. Aborted or canceled tours do not dock.

### Wrong waypoint is published to `/talk_command`

Check the map:

```bash
ros2 topic echo /tour_waypoint_order
```

Expected order:

```text
Published waypoint order map with N entries
Received waypoint order map with N entries
Arrived at goal waypoint 0 (tour waypoint X), published talk command: ...
```

If the map is missing, `TalkAtWaypoint` falls back to Nav2's local waypoint index.

### Robot reaches a waypoint and waits forever

The plugin is waiting for `/done_talking`.

Unblock manually:

```bash
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done}"
```

### `/follow_waypoints` is not available

Check Nav2:

```bash
ros2 action list | grep follow
ros2 lifecycle get /waypoint_follower
```

If inactive, inspect Nav2 logs.

### Saving a waypoint fails

Check TF:

```bash
ros2 run tf2_ros tf2_echo map base_link
```

If TF is missing, localize the robot or fix the frame names.

### `tour_retrieve` service is missing

Check:

```bash
ros2 node list | grep tour_manager
ros2 service list | grep tour_retrieve
```

If missing, relaunch `tour_manager_launch.py` or the locomotion launch.

### Docking says no dock poses found

Save a dock pose first:

```bash
ros2 topic pub --once /save_dock_command std_msgs/msg/String "{data: save}"
sqlite3 docks.db 'SELECT rowid, px, py FROM docks;'
```

## 17. Known Limitations

- The tour database is a flat list of waypoints, not multiple named tours.
- `subtour` uses straight-line pose distance, not full Nav2 path cost.
- `/tour_waypoint_order` is a side-channel for the waypoint plugin; transient local QoS helps late subscribers receive the latest map.
- `TalkAtWaypoint` blocks waypoint progress until `/done_talking` arrives or timeout expires.
- Docking requires either saved dock poses in `docks.db` or a valid OpenNav dock ID setup.
- Changes to installed config files require rebuilding the package that installs them.

## 18. Quick Reference

Source:

```bash
cd /home/tom/big_ws
source install/setup.bash
```

Launch locomotion:

```bash
ros2 launch tour_manager locomotion_test.launch.py
```

Launch integrated file without HRI/LLM:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false enable_intent:=false
```

Save tour waypoint:

```bash
ros2 topic pub --once /save_tour_command std_msgs/msg/String "{data: save}"
```

Run full tour:

```bash
ros2 topic pub --once /tour_command std_msgs/msg/String "{data: start}"
```

Run optimized subtour:

```bash
ros2 topic pub --once /tsp_command social_robot_interfaces/msg/TspCommand "{waypoints: [0, 2, 4]}"
```

Release waypoint wait:

```bash
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done}"
```

Dock:

```bash
ros2 topic pub --once /dock_command std_msgs/msg/String "{data: dock}"
```

Check route map:

```bash
ros2 topic echo /tour_waypoint_order
```

Check databases:

```bash
sqlite3 tours.db 'SELECT rowid, px, py FROM tours;'
sqlite3 docks.db 'SELECT rowid, px, py FROM docks;'
```
