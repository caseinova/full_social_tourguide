# Social Tour Guide Robot Workspace Guide

This guide explains how this ROS 2 workspace is put together, how to run it, how to configure it, and how to debug it. It is written for a first-time user: commands are explicit, important files are named, and each subsystem explains what it receives and what it publishes.

The main system is a social tour guide robot. A TurtleBot3-style mobile base handles mapping, localization, navigation, waypoint following, and docking. Pepper handles human interaction, tablet display, gestures, and exhibit explanations. Speech and LLM nodes convert human commands into robot actions. The tour manager stores saved waypoints and returns them to navigation nodes.

## 1. Project Overview

The workspace runs a robot that can:

- save tour stops from the robot's current pose;
- retrieve a saved tour from a SQLite database;
- run a full tour through Nav2 waypoint following;
- run a selected subtour through a travelling-salesman-style optimizer;
- speak at each waypoint using the original tour waypoint index;
- dock after a tour if configured;
- receive commands from speech, tablet UI, or ROS topics;
- run in simulation or on real TurtleBot3 hardware;
- optionally launch Pepper HRI and LLM intent handling.

The common all-in-one launch file is:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

That launch file includes:

- TurtleBot3 Gazebo simulation or TurtleBot3 real bringup;
- Nav2 navigation;
- tour manager, tour saver, full tour, subtour, docking listener;
- OpenNav docking server;
- Pepper HRI;
- LLM/speech intent nodes.

## 2. Workspace Layout

Important packages in this workspace:

| Package | Purpose |
| --- | --- |
| `tour_manager` | Stores and retrieves tour waypoints from `tours.db`; owns main launch files and shared params. |
| `robot_tour` | Sends full tours and optimized subtours to Nav2; provides `TalkAtWaypoint` Nav2 plugin. |
| `social_robot_interfaces` | Custom ROS interfaces: `TspCommand`, `Tours`, `Description`. |
| `docking` | Listens on `/dock_command` and sends OpenNav docking action goals. |
| `qr_code_follower` | Optional QR-code direct follower; publishes short-lived `/cmd_vel` commands from fresh camera detections. |
| `speech_locomotion_interface` | Converts `/speech/intent` JSON into tour, subtour, docking, or navigation commands. |
| `pepper_hri` | Pepper coordinator, tablet UI server/assets, audio processor, gesture manager. |
| `turtlebot_llm_control` | Speech-to-text, LLM command parsing, speech responses, waypoint speaker, GUI helpers. |
| `turtlebot3_navigation2` | TurtleBot3 Nav2 configuration, maps, RViz, waypoint follower settings. |
| `turtlebot3_gazebo` | Simulation world and robot launch files. |
| `open_nav/opennav_docking` | Docking framework used by the docking server. |

Key files:

```text
src/tour_manager/launch/pepper_locomotion_llm.launch.py
src/tour_manager/launch/tour_manager_launch.py
src/tour_manager/config/tour_manager_params.yaml
src/robot_tour/src/subtour.cpp
src/robot_tour/src/tour_guide.cpp
src/robot_tour/plugins/talk_at_waypoint.cpp
src/docking/docking/dock_listener.py
src/qr_code_follower/qr_code_follower/qr_follower_node.py
src/qr_code_follower/config/qr_follower.yaml
src/turtlebot3/turtlebot3_navigation2/param/humble/waffle_pi.yaml
src/Pepper_HRI/pepper_real.launch.py
src/turtlebot_LLM_control/launch/intent_only.launch.py
waypoint_info_loader_helper.py
waypoint_info.txt
```

## 3. Dependencies

### Hardware

For real-robot operation:

- TurtleBot3-compatible base;
- LDS lidar, usually `LDS-01`;
- OpenCR board connected by USB, usually `/dev/ttyACM0`;
- a computer running ROS 2 Humble;
- optional Pepper robot on the same network;
- optional microphone/speaker for speech interaction;
- a saved map and working Nav2 localization.

For simulation:

- a computer capable of running Gazebo and Nav2;
- no physical robot required.

### Software

This workspace is ROS 2 Humble-style. Main ROS dependencies include:

- `rclcpp`, `rclpy`, `rclcpp_action`, `rclcpp_components`;
- `geometry_msgs`, `std_msgs`, `nav2_msgs`;
- `nav2_core`, `nav2_util`, `nav2_simple_commander`;
- `tf2_ros`;
- `pluginlib`;
- `opennav_docking_msgs`;
- TurtleBot3 packages;
- Gazebo packages for simulation;
- Python `sqlite3`, included with Python.

LLM and speech nodes may require extra Python libraries depending on your machine setup. Check `src/turtlebot_LLM_control/SETUP.md` and `src/turtlebot_LLM_control/README.md` for that package's deeper speech/LLM setup.

## 4. Installation

Run these commands from a fresh terminal.

```bash
cd /home/tom/big_ws
source /opt/ros/humble/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build
source install/setup.bash
```

If you only changed Python config/launch files and want to rebuild quickly:

```bash
cd /home/tom/big_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select tour_manager pepper_hri turtlebot_llm_control docking speech_locomotion_interface qr_code_follower
source install/setup.bash
```

If you changed C++ files in `robot_tour`:

```bash
cd /home/tom/big_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select robot_tour
source install/setup.bash
```

Important: launch files use installed package shares. If you edit `src/tour_manager/config/tour_manager_params.yaml`, rebuild `tour_manager`; otherwise ROS may launch the old installed YAML.

```bash
colcon build --packages-select tour_manager
source install/setup.bash
```

Check the installed copy:

```bash
sed -n '1,40p' install/tour_manager/share/tour_manager/config/tour_manager_params.yaml
```

## 5. Running The System

### Simulation Mode

Simulation is the default mode.

```bash
cd /home/tom/big_ws
source install/setup.bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

Equivalent explicit command:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=sim use_sim_time:=true
```

Expected result:

- Gazebo starts with a TurtleBot3;
- Nav2 nodes start;
- `/waypoint_follower` becomes active;
- `tour_manager`, `tour_saver`, `subtour`, `tour_guide`, `dock_listener` start;
- if enabled, Pepper and LLM/speech nodes start.

### Real TurtleBot3 Mode

```bash
cd /home/tom/big_ws
source install/setup.bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=real use_sim_time:=false usb_port:=/dev/ttyACM0
```

If the OpenCR board uses another port, list ports:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

### Disable Pepper Or Intent Nodes

Useful when testing only navigation:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false enable_intent:=false
```

Useful when testing navigation plus speech/LLM but not Pepper:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false enable_intent:=true
```

## 6. Main Launch Arguments

`src/tour_manager/launch/pepper_locomotion_llm.launch.py` supports:

| Argument | Default | Meaning |
| --- | --- | --- |
| `model` | `waffle_pi` | TurtleBot3 model. |
| `lds_model` | `LDS-01` | Lidar model for real TurtleBot3 bringup. |
| `turtlebot_mode` | `sim` | `sim` launches Gazebo; `real` launches robot hardware. |
| `use_sim_time` | true in sim, false in real | Uses Gazebo clock when true. |
| `nav2_params_file` | TurtleBot3 Humble `waffle_pi.yaml` | Nav2 config file. |
| `usb_port` | `/dev/ttyACM0` | Real TurtleBot3 OpenCR serial port. |
| `namespace` | empty | Optional ROS namespace for robot bringup. |
| `enable_pepper` | `true` | Launch Pepper HRI. |
| `enable_intent` | `true` | Launch LLM/speech intent stack. |

Example using a custom Nav2 params file:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py nav2_params_file:=/home/tom/big_ws/src/turtlebot3/turtlebot3_navigation2/param/humble/waffle_pi.yaml
```

## 7. Shared Configuration

Main config:

```text
src/tour_manager/config/tour_manager_params.yaml
```

Important values:

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

`dock_after_tour` controls whether a successful tour publishes `"dock"` to `/dock_command`.

`waypoint_order_topic` carries the map from Nav2's local waypoint index to the original tour waypoint index. This matters for subtours because the travelling-salesman solver may reorder the stops.

## 8. Concept Map

The usual data flow:

```text
Speech / Tablet / ROS topic
        |
        v
/tour_command or /tsp_command or /dock_command
        |
        v
tour_guide or subtour
        |
        v
tour_retrieve service -> tours.db
        |
        v
/tour_waypoint_order + /follow_waypoints action goal
        |
        v
Nav2 waypoint_follower
        |
        v
TalkAtWaypoint plugin -> /talk_command
        |
        v
waypoint_speaker / Pepper HRI -> speech -> /done_talking
```

Docking flow:

```text
tour result or voice command
        |
        v
/dock_command: "dock"
        |
        v
dock_listener
        |
        v
OpenNav DockRobot action
```

## 9. Subsystem: `social_robot_interfaces`

This package defines custom messages and services.

### `TspCommand.msg`

```text
int64[] waypoints
```

Use this to request a selected subtour. The numbers are original tour waypoint indices.

Example:

```bash
ros2 topic pub --once /tsp_command social_robot_interfaces/msg/TspCommand "{waypoints: [0, 4, 2]}"
```

### `Tours.srv`

```text
int64 idx
---
geometry_msgs/PoseStamped[] tour
```

The current implementation retrieves all saved waypoints from `tours.db`.

Example:

```bash
ros2 service call /tour_retrieve social_robot_interfaces/srv/Tours "{idx: 0}"
```

### `Description.srv`

```text
int64 idx
---
std_msgs/String description
```

Use this to retrieve text for a waypoint.

Example:

```bash
ros2 service call /retrieve_description social_robot_interfaces/srv/Description "{idx: 2}"
```

## 10. Subsystem: `tour_manager`

Purpose: save and retrieve tour waypoints.

Nodes:

| Node | Executable | Purpose |
| --- | --- | --- |
| `/tour_manager` | `tour_manager` | Owns `tours.db`, serves saved tour waypoints and descriptions. |
| `/tour_saver` | `tour_saver` | Saves the current robot pose when commanded. |

Topics and services:

| Name | Type | Direction | Meaning |
| --- | --- | --- | --- |
| `/save_tour_command` | `std_msgs/String` | input to `tour_saver` | Save current robot pose as a tour waypoint. |
| `/save_tour` | `geometry_msgs/PoseStamped` | `tour_saver` to `tour_manager` | Pose to store in database. |
| `/tour_retrieve` | `social_robot_interfaces/srv/Tours` | service | Return saved tour waypoints. |
| `/retrieve_description` | `social_robot_interfaces/srv/Description` | service | Return waypoint description text. |

Save a waypoint:

```bash
ros2 topic pub --once /save_tour_command std_msgs/msg/String "{data: save}"
```

List database files created while running:

```bash
find /home/tom/big_ws -name 'tours.db' -print
```

Inspect saved tour rows:

```bash
sqlite3 tours.db 'SELECT rowid, px, py, pz, qx, qy, qz, qw, description FROM tours;'
```

Load waypoint descriptions from `waypoint_info.txt`:

```bash
python3 waypoint_info_loader_helper.py
```

Each nonblank line maps sequentially to a `tours` row: line `0` updates the first row by `rowid`, line `1` updates the second row, and so on. If the text file has more lines than the database has rows, the helper inserts new rows with `0.0` for `px, py, pz, qx, qy, qz, qw`.

Known assumption: `tour_manager_service.py` currently stores all saved points in a single `tours` table and retrieves all rows. `request.idx` is accepted but not used to select different tours.

## 11. Subsystem: `robot_tour`

Purpose: send saved tours to Nav2 and speak at waypoints.

Executables/plugins:

| Name | Type | Purpose |
| --- | --- | --- |
| `tour_guide_start` | C++ component executable | Retrieves full tour and sends it to `/follow_waypoints`. |
| `subtour_start` | C++ component executable | Receives selected waypoint indices, optimizes order, sends selected tour. |
| `robot_tour::TalkAtWaypoint` | Nav2 plugin | Publishes `/talk_command` when each waypoint is reached. |

### Full Tour: `tour_guide.cpp`

Input:

```text
/tour_command std_msgs/String
```

Example:

```bash
ros2 topic pub --once /tour_command std_msgs/msg/String "{data: start}"
```

Behavior:

1. calls `/tour_retrieve`;
2. publishes identity waypoint order `[0, 1, 2, ...]` to `/tour_waypoint_order`;
3. sends all poses to Nav2 `/follow_waypoints`;
4. if `dock_after_tour` is true and the action succeeds, publishes `"dock"` to `/dock_command`.

### Optimized Subtour: `subtour.cpp`

Input:

```text
/tsp_command social_robot_interfaces/msg/TspCommand
```

Example:

```bash
ros2 topic pub --once /tsp_command social_robot_interfaces/msg/TspCommand "{waypoints: [0, 4, 2]}"
```

Behavior:

1. validates requested original waypoint indices;
2. retrieves saved tour from `/tour_retrieve`;
3. selects only requested poses;
4. starts from the selected pose nearest the robot's current `/amcl_pose`;
5. builds a distance cost matrix;
6. creates an initial nearest-neighbor route;
7. improves the route using 2-opt;
8. publishes reordered original waypoint IDs to `/tour_waypoint_order`;
9. sends reordered poses to `/follow_waypoints`;
10. optionally docks after successful completion.

Important logs:

```text
Optimized 3 selected waypoints; final path length is 4.321 m
Published waypoint order map with 3 entries
Sent 3 optimized waypoints
Waypoint tour completed with 0 missed waypoints
Published dock command after tour completion
```

### Talk At Waypoint Plugin

File:

```text
src/robot_tour/plugins/talk_at_waypoint.cpp
```

Nav2 config:

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

What it does:

1. Nav2 calls `processAtWaypoint(curr_pose, curr_waypoint_index)`;
2. plugin converts Nav2 local index to original tour index using `/tour_waypoint_order`;
3. publishes the original tour index or configured text to `/talk_command`;
4. waits until `/done_talking` arrives or timeout expires;
5. returns `true` so Nav2 can continue.

Important timing detail: `/tour_waypoint_order` uses transient local QoS, so late subscribers should receive the most recent map. For debugging, confirm this log appears before the first talk command:

```text
Received waypoint order map with N entries
Arrived at goal waypoint 0 (tour waypoint X), published talk command: ...
```

Watch the map:

```bash
ros2 topic echo /tour_waypoint_order
```

Watch talk commands:

```bash
ros2 topic echo /talk_command
```

Manually release the waypoint wait:

```bash
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done_speaking}"
```

## 12. Subsystem: Nav2 And TurtleBot3 Navigation

Purpose: localization, path planning, movement control, waypoint following.

Main launch included by `pepper_locomotion_llm.launch.py`:

```text
turtlebot3_navigation2/launch/navigation2.launch.py
```

Default params:

```text
src/turtlebot3/turtlebot3_navigation2/param/humble/waffle_pi.yaml
```

Important node:

```text
/waypoint_follower
```

Important actions:

```text
/navigate_to_pose
/follow_waypoints
```

Check action availability:

```bash
ros2 action list | grep waypoint
ros2 action info /follow_waypoints
```

Check Nav2 lifecycle state:

```bash
ros2 lifecycle nodes
ros2 lifecycle get /waypoint_follower
ros2 lifecycle get /bt_navigator
ros2 lifecycle get /controller_server
```

Expected state for running navigation:

```text
active
```

Common navigation topics:

```bash
ros2 topic echo /amcl_pose
ros2 topic echo /cmd_vel
ros2 topic echo /scan
ros2 topic echo /tf
```

## 13. Subsystem: `docking`

Purpose: turn a simple command into an OpenNav docking action.

Node:

```text
/dock_listener
```

Inputs:

| Topic | Type | Meaning |
| --- | --- | --- |
| `/dock_command` | `std_msgs/String` | Start docking. Usually data is `"dock"`. |
| `/save_dock_command` | `std_msgs/String` | Save the current dock pose into `docks.db`. |
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | Current pose for nearest-dock selection. |

Action client:

```text
/dock_robot opennav_docking_msgs/action/DockRobot
```

Save current pose as dock:

```bash
ros2 topic pub --once /save_dock_command std_msgs/msg/String "{data: save}"
```

Start docking:

```bash
ros2 topic pub --once /dock_command std_msgs/msg/String "{data: dock}"
```

Debug docking:

```bash
ros2 action list | grep dock
ros2 action info /dock_robot
ros2 topic echo /dock_command
sqlite3 docks.db 'SELECT rowid, * FROM docks;'
```

Important parameters in `tour_manager_params.yaml`:

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

Known assumption: if `use_dock_id` is false, `dock_listener` uses the nearest pose stored in `docks.db`.

## 14. Subsystem: `speech_locomotion_interface`

Purpose: convert parsed speech intent JSON into navigation/tour commands.

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
/tour_command std_msgs/String
/tsp_command social_robot_interfaces/msg/TspCommand
/dock_command std_msgs/String
```

Example intents:

```bash
ros2 topic pub --once /speech/intent std_msgs/msg/String '{data: "{\"intent\":\"start_tour\"}"}'
```

```bash
ros2 topic pub --once /speech/intent std_msgs/msg/String '{data: "{\"intent\":\"tsp\", \"waypoints\":[0,2,4]}"}'
```

```bash
ros2 topic pub --once /speech/intent std_msgs/msg/String '{data: "{\"intent\":\"dock\"}"}'
```

Debug:

```bash
ros2 topic echo /speech/intent
ros2 topic echo /tour_command
ros2 topic echo /tsp_command
ros2 topic echo /dock_command
```

## 15. Subsystem: `turtlebot_llm_control`

Purpose: speech-to-text, command parsing, LLM intent generation, speech response, GUI helpers, and waypoint speaking.

Important launch:

```bash
ros2 launch turtlebot_llm_control intent_only.launch.py
```

This is included by `pepper_locomotion_llm.launch.py` when `enable_intent:=true`.

Important launch arguments:

| Argument | Default | Meaning |
| --- | --- | --- |
| `enable_microphone` | `true` in integrated launch | Use live microphone. |
| `enable_llm` | `true` | Use LLM for intent parsing. |
| `llm_provider` | `ollama`, integrated launch uses `groq` | LLM backend. |
| `llm_model` | varies | Model name. |
| `enable_speech_debug` | `true` | Starts debug topic aggregator. |
| `enable_speech_response` | `true` | Enables spoken/text response. |
| `enable_tsp_gui` | `true` | Enables GUI for waypoint selection. |
| `enable_waypoint_speaker` | `true` | Speaks waypoint descriptions from `/talk_command`. |
| `require_wake_word` | `true` | Ignore speech until wake phrase. |
| `wake_command_window_seconds` | `45.0` | Command window after wake phrase. |

Waypoint speaker behavior:

- subscribes to `/talk_command`;
- retrieves text from `/retrieve_description`;
- publishes `explain` to `/pepper/gesture_command` when it starts speaking;
- publishes `done_speaking` to `/done_talking` and `/done_speaking` when speech finishes.

Useful debug commands:

```bash
ros2 topic echo /speech_to_text/status
ros2 topic echo /speech/text
ros2 topic echo /speech/intent
ros2 topic echo /speech/response
ros2 topic echo /speech/debug
ros2 topic echo /pepper/gesture_command
ros2 topic echo /done_talking
```

If logs show:

```text
Ignored speech until wake phrase like 'hey ...'
```

then speech-to-text is working, but the node is waiting for the wake phrase. For testing, launch with:

```bash
ros2 launch turtlebot_llm_control intent_only.launch.py require_wake_word:=false
```

In the integrated launch, edit `pepper_locomotion_llm.launch.py` or pass launch arguments if exposed.

## 16. Subsystem: `pepper_hri`

Purpose: Pepper interaction: coordinator, tablet display, audio processor, and gestures.

Main launch included by the integrated launch:

```bash
ros2 launch pepper_hri pepper_real.launch.py
```

Important nodes/executables:

| Executable | Purpose |
| --- | --- |
| `hri_coordinator` | Coordinates Pepper speech, gestures, tablet, and done-talking signal. |
| `tablet_builder` | Serves/generates tablet UI and publishes selected tour waypoints. |
| `gesture_manager` | Receives gesture commands and controls Pepper gestures. |
| `audio_processor` | Processes Pepper/audio stream. |

Important topics:

| Topic | Type | Meaning |
| --- | --- | --- |
| `/talk_command` | `std_msgs/String` | Waypoint/exhibit to speak about. |
| `/done_talking` | `std_msgs/String` | Tells Nav2 waypoint plugin it can continue. |
| `/done_speaking` | `std_msgs/String` | Duplicate speech-finished signal from `waypoint_speaker`. |
| `/pepper/gesture_command` | `std_msgs/String` | Gesture command, including `explain` from `waypoint_speaker`. |
| `/pepper/spoken_words` | `std_msgs/String` | Text Pepper should speak or has spoken. |
| `/pepper/explain_exhibit` | `std_msgs/String` | Tablet exhibit display command. |
| `/current_tour` | `std_msgs/String` | Current tour state/command. |
| `/human_present` | `std_msgs/String` | Human presence signal. |

Manual tests:

```bash
ros2 topic pub --once /talk_command std_msgs/msg/String "{data: '0'}"
ros2 topic pub --once /pepper/gesture_command std_msgs/msg/String "{data: explain}"
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done_speaking}"
```

## 17. Subsystem: `qr_code_follower`

Purpose: optionally follow a QR code with camera feedback. In `direct` mode, the node publishes `/cmd_vel` from each freshly processed QR image.

Important files:

```text
src/qr_code_follower/qr_code_follower/qr_follower_node.py
src/qr_code_follower/config/qr_follower.yaml
src/qr_code_follower/launch/qr_follower.launch.py
```

Run:

```bash
ros2 launch qr_code_follower qr_follower.launch.py follow_mode:=direct
```

Start and stop following:

```bash
ros2 topic pub --once /follow_command std_msgs/msg/String "{data: start}"
ros2 topic pub --once /follow_command std_msgs/msg/String "{data: stop}"
```

Safety behavior in direct mode:

- a nonzero `/cmd_vel` is published only from a processed QR image;
- that command is valid for `direct_command_timeout_sec`, default `0.5`;
- if no newer QR image is processed before the timeout, the node publishes a zero `Twist` and waits for the next QR update.

Useful checks:

```bash
ros2 topic echo /qr_follower/status
ros2 topic echo /cmd_vel
ros2 param get /qr_follower direct_command_timeout_sec
```

## 18. Common Operator Workflows

### Start A Full Tour

1. Launch the system:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

2. In another terminal:

```bash
source /home/tom/big_ws/install/setup.bash
ros2 topic pub --once /tour_command std_msgs/msg/String "{data: start}"
```

3. Watch:

```bash
ros2 topic echo /talk_command
ros2 topic echo /done_talking
```

### Start A Selected Optimized Subtour

```bash
source /home/tom/big_ws/install/setup.bash
ros2 topic pub --once /tsp_command social_robot_interfaces/msg/TspCommand "{waypoints: [0, 4, 2]}"
```

Watch the optimized waypoint map:

```bash
ros2 topic echo /tour_waypoint_order
```

### Enable Or Disable Docking After Tour

Set in source config:

```yaml
subtour:
  ros__parameters:
    dock_after_tour: true
```

Then rebuild config package:

```bash
colcon build --packages-select tour_manager
source install/setup.bash
```

Or change while the node is running:

```bash
ros2 param set /subtour dock_after_tour true
ros2 param get /subtour dock_after_tour
```

### Save A Tour Stop

Move the robot to the desired location, then:

```bash
ros2 topic pub --once /save_tour_command std_msgs/msg/String "{data: save}"
```

Confirm:

```bash
sqlite3 tours.db 'SELECT rowid, px, py FROM tours;'
```

### Save A Dock Pose

Place the robot near the dock location, then:

```bash
ros2 topic pub --once /save_dock_command std_msgs/msg/String "{data: save}"
sqlite3 docks.db 'SELECT rowid, px, py FROM docks;'
```

## 19. Debugging Flags And Commands

### ROS Logging Flags

Show debug logs for all nodes launched by a command:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py --ros-args --log-level debug
```

Show debug logs for one node:

```bash
ros2 run robot_tour subtour_start --ros-args --log-level subtour:=debug
```

Force logs to print immediately:

```bash
export RCUTILS_LOGGING_BUFFERED_STREAM=1
```

Put logs in a known folder:

```bash
export ROS_LOG_DIR=/tmp/ros_logs
mkdir -p /tmp/ros_logs
```

Colorized console output:

```bash
export RCUTILS_COLORIZED_OUTPUT=1
```

### Launch Debugging

Show launch arguments:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py --show-args
```

Print package install path:

```bash
ros2 pkg prefix tour_manager
ros2 pkg prefix robot_tour
```

Check whether your source edits reached the installed share:

```bash
diff -u src/tour_manager/config/tour_manager_params.yaml install/tour_manager/share/tour_manager/config/tour_manager_params.yaml
```

### Graph And Topic Debugging

List nodes:

```bash
ros2 node list
```

Inspect one node:

```bash
ros2 node info /subtour
ros2 node info /waypoint_follower
ros2 node info /dock_listener
```

List topics with types:

```bash
ros2 topic list -t
```

Check publisher/subscriber counts:

```bash
ros2 topic info /talk_command
ros2 topic info /tour_waypoint_order
ros2 topic info /dock_command
ros2 topic info /qr_follower/status
```

Echo important topics:

```bash
ros2 topic echo /tsp_command
ros2 topic echo /tour_waypoint_order
ros2 topic echo /talk_command
ros2 topic echo /done_talking
ros2 topic echo /dock_command
ros2 topic echo /amcl_pose
ros2 topic echo /qr_follower/status
ros2 topic echo /cmd_vel
```

Check topic rate:

```bash
ros2 topic hz /scan
ros2 topic hz /cmd_vel
```

### Parameter Debugging

List parameters:

```bash
ros2 param list /subtour
ros2 param list /waypoint_follower
```

Read important parameters:

```bash
ros2 param get /subtour dock_after_tour
ros2 param get /subtour waypoint_order_topic
ros2 param get /waypoint_follower talk_at_waypoint.waypoint_order_topic
```

Set a runtime parameter:

```bash
ros2 param set /subtour dock_after_tour true
```

Dump parameters to a file:

```bash
ros2 param dump /subtour > /tmp/subtour_params.yaml
```

### Action Debugging

```bash
ros2 action list
ros2 action info /follow_waypoints
ros2 action info /dock_robot
ros2 action info /navigate_to_pose
```

### TF Debugging

Check transforms:

```bash
ros2 run tf2_ros tf2_echo map base_link
ros2 run tf2_ros tf2_echo odom base_link
```

If saving a tour fails with `Could not transform map to base_link`, TF is missing or the robot is not localized.

### Database Debugging

Tour database:

```bash
sqlite3 tours.db '.tables'
sqlite3 tours.db 'SELECT rowid, px, py, description FROM tours;'
python3 waypoint_info_loader_helper.py
```

Dock database:

```bash
sqlite3 docks.db '.tables'
sqlite3 docks.db 'SELECT rowid, px, py FROM docks;'
```

Remove a bad row carefully:

```bash
sqlite3 tours.db 'DELETE FROM tours WHERE rowid = 3;'
```

### Build Debugging

Build only the changed packages:

```bash
colcon build --packages-select robot_tour tour_manager
```

Build with console output:

```bash
colcon build --packages-select robot_tour --event-handlers console_direct+
```

Clean one package's build/install output when C++ plugin changes do not appear:

```bash
rm -rf build/robot_tour install/robot_tour log
colcon build --packages-select robot_tour
source install/setup.bash
```

## 20. Troubleshooting And FAQs

### `dock_after_tour` is true in source YAML, but runtime says false

Cause: launch uses installed YAML, not source YAML.

Fix:

```bash
colcon build --packages-select tour_manager
source install/setup.bash
ros2 param get /subtour dock_after_tour
```

### No message appears on `/dock_command` after tour completion

Check:

```bash
ros2 param get /subtour dock_after_tour
ros2 topic echo /dock_command
```

Expected successful tour log:

```text
Waypoint tour completed with 0 missed waypoints
Published dock command after tour completion
```

If the tour was aborted or canceled, docking is not published.

### Talk command uses wrong waypoint number during a subtour

Check the order map:

```bash
ros2 topic echo /tour_waypoint_order
```

Expected logs:

```text
Published waypoint order map with N entries
Received waypoint order map with N entries
Arrived at goal waypoint 0 (tour waypoint X), published talk command: ...
```

If `Received waypoint order map` appears after the first `Arrived at goal waypoint`, the plugin may have used the local Nav2 index for the first stop.

### Robot reaches waypoint but never moves to the next one

`TalkAtWaypoint` waits for `/done_talking`.

Check:

```bash
ros2 topic echo /done_talking
```

Manually unblock:

```bash
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done_speaking}"
```

Also check `waypoint_pause_duration` and `max_wait_duration`.

### `/follow_waypoints` action is missing

Nav2 waypoint follower is not active.

Check:

```bash
ros2 action list | grep follow
ros2 lifecycle get /waypoint_follower
```

If inactive, inspect Nav2 launch logs and lifecycle manager logs.

### `tour_retrieve service is not available`

`tour_manager` is not running or not sourced from the right workspace.

Check:

```bash
ros2 node list | grep tour_manager
ros2 service list | grep tour_retrieve
```

### Saved tour has no points

Check database:

```bash
sqlite3 tours.db 'SELECT rowid, px, py FROM tours;'
```

Save a point:

```bash
ros2 topic pub --once /save_tour_command std_msgs/msg/String "{data: save}"
```

If saving fails, check TF:

```bash
ros2 run tf2_ros tf2_echo map base_link
```

### Speech is ignored until wake phrase

This is expected when `require_wake_word` is true.

For testing:

```bash
ros2 launch turtlebot_llm_control intent_only.launch.py require_wake_word:=false
```

### Pepper does not speak at waypoints

Check:

```bash
ros2 topic echo /talk_command
ros2 topic echo /pepper/gesture_command
ros2 topic echo /done_talking
ros2 node list | grep waypoint
ros2 node list | grep hri
```

If `/talk_command` appears but Pepper does not respond, confirm `waypoint_speaker` publishes `explain` on `/pepper/gesture_command`, then debug Pepper HRI or `waypoint_speaker`.

### The robot does not move in simulation

Check:

```bash
ros2 topic echo /cmd_vel
ros2 topic echo /amcl_pose
ros2 lifecycle get /controller_server
```

If `/cmd_vel` is empty, Nav2 is probably not planning or waypoint action was not accepted. If `/cmd_vel` is active but the robot does not move, Gazebo/plugin control may be the issue.

## 21. Known Limitations And Assumptions

- `tour_manager` currently stores and retrieves one flat list of waypoints from `tours.db`.
- `subtour` optimizes based on straight-line distance between poses, not actual Nav2 path cost.
- `TalkAtWaypoint` receives original waypoint IDs through `/tour_waypoint_order`; this is robust because transient local QoS retains the latest map, but very fast first-waypoint timing should still be checked in logs.
- `dock_after_tour` only triggers after successful waypoint action completion.
- Docking requires a valid dock pose in `docks.db` unless using OpenNav dock IDs.
- Config changes under `src/.../config` usually require rebuilding the package that installs that config.
- Real robot runs depend on correct TF, localization, serial port, network, and battery state.

## 22. Quick Command Reference

Source workspace:

```bash
cd /home/tom/big_ws
source install/setup.bash
```

Build common changed packages:

```bash
colcon build --packages-select robot_tour tour_manager turtlebot3_navigation2
```

Launch integrated system:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

Launch without Pepper and speech:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false enable_intent:=false
```

Start full tour:

```bash
ros2 topic pub --once /tour_command std_msgs/msg/String "{data: start}"
```

Start subtour:

```bash
ros2 topic pub --once /tsp_command social_robot_interfaces/msg/TspCommand "{waypoints: [0, 2, 4]}"
```

Dock:

```bash
ros2 topic pub --once /dock_command std_msgs/msg/String "{data: dock}"
```

Unblock waypoint speaking:

```bash
ros2 topic pub --once /done_talking std_msgs/msg/String "{data: done_speaking}"
```

Check subtour docking:

```bash
ros2 param get /subtour dock_after_tour
ros2 topic echo /dock_command
```

Check waypoint speech index mapping:

```bash
ros2 topic echo /tour_waypoint_order
ros2 topic echo /talk_command
```

## 23. What A Healthy Run Looks Like

During startup:

```text
TalkAtWaypoint initialized: enabled=true, talk_topic=/talk_command, waypoint_order_topic=/tour_waypoint_order, pause=200 ms
Listening for TSP waypoint lists on '/tsp_command' and sending tours to '/follow_waypoints'
Dock listener ready; using OpenNav docking action "/dock_robot"
```

During a subtour:

```text
Optimized 3 selected waypoints; final path length is ...
Published waypoint order map with 3 entries
Waypoint follower accepted the goal
Received waypoint order map with 3 entries
Arrived at goal waypoint 0 (tour waypoint 4), published talk command: '4'
Received done talking signal for tour waypoint 4, resuming navigation
Waypoint tour completed with 0 missed waypoints
Published dock command after tour completion
```

During docking:

```text
Received dock command: "dock"
Sending docking goal to OpenNav
Docking goal accepted
Docking feedback: ...
Docking succeeded after 0 retries
```

If your logs differ, use the topic, parameter, action, and lifecycle checks above to isolate the missing part.
