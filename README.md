# Social Tour Guide Robot Workspace

This workspace contains the full Social Tour Guide Robot stack for ROS 2 Humble.
It integrates a TurtleBot3 Waffle Pi base, optional SoftBank Pepper HRI, QR code
following, speech/LLM intent parsing, waypoint tour planning, docking, and
Nav2-based locomotion.

## What this project does

- Accepts spoken commands and LLM-guided intent input.
- Navigates TurtleBot3 to saved waypoint tours using Nav2.
- Supports full tours and optimized subtours via a TSP planner.
- Speaks waypoint descriptions through local TTS and Pepper audio.
- Executes Pepper gestures, tablet UI updates, and socially-aware interaction.
- Saves waypoint and dock poses in SQLite databases.
- Follows QR codes in direct or pose-following mode.
- Runs in Gazebo simulation or on real TurtleBot3 hardware.

## Prerequisites

- Ubuntu 22.04 LTS
- ROS 2 Humble Hawksbill
- TurtleBot3 packages: `turtlebot3`, `turtlebot3_simulations`, `turtlebot3_navigation2`
- `opennav_docking` plugin (OpenNav docking support)
- `python3-opencv`, `ros-humble-cv-bridge`
- Optional Pepper robot with NAOqi / `qi` SDK for full Pepper HRI support

## Build

From the workspace root:

```bash
source /opt/ros/humble/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

To rebuild only the integrated packages:

```bash
colcon build --packages-select tour_manager pepper_hri turtlebot_llm_control docking speech_locomotion_interface qr_code_follower
source install/setup.bash
```

If you change `src/tour_manager/config/tour_manager_params.yaml`, rebuild
`tour_manager` so the installed launch files use the updated parameters.

## Quick start

Launch the integrated system:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

### Simulation mode (default)

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=sim use_sim_time:=true
```

### Real TurtleBot3 mode

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=real use_sim_time:=false usb_port:=/dev/ttyACM0
```

### Disable Pepper HRI

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false
```

### Disable LLM / intent layer

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_intent:=false
```

### Real robot without Pepper and intent

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=real enable_pepper:=false enable_intent:=false
```

## Core packages

| Package | Role |
| --- | --- |
| `tour_manager` | Main launch files, waypoint database, tour management, shared ROS params. |
| `robot_tour` | Tour and subtour execution, Nav2 waypoint plugins. |
| `speech_locomotion_interface` | Converts `/speech/intent` JSON into tour, docking, and navigation commands. |
| `pepper_hri` | Pepper gesture manager, tablet UI assets, audio and HRI coordination. |
| `turtlebot_llm_control` | Speech-to-text, intent classification, LLM fallback, waypoint speaker. |
| `docking` | OpenNav docking listener and dock pose manager. |
| `qr_code_follower` | QR-code-based follower with direct-velocity and pose-follow modes. |

## Main launch arguments

| Argument | Default | Description |
| --- | --- | --- |
| `turtlebot_mode` | `sim` | `sim` launches Gazebo; `real` launches physical TurtleBot3 hardware. |
| `use_sim_time` | auto (`true` in sim, `false` in real) | Uses the simulated clock when running Gazebo. |
| `enable_pepper` | `true` | Launch Pepper HRI support. |
| `enable_intent` | `true` | Launch the speech/LLM intent stack. |
| `model` | `waffle_pi` | TurtleBot3 model name. |
| `lds_model` | `LDS-01` | Lidar sensor model for real TurtleBot bringup. |
| `usb_port` | `/dev/ttyACM0` | OpenCR serial port for real TurtleBot mode. |
| `namespace` | empty | Optional ROS namespace for real TurtleBot bringup. |
| `nav2_params_file` | `waffle_pi.yaml` | Nav2 parameter file used for TurtleBot3. |

## QR code follower

Launch the optional QR code follower:

```bash
ros2 launch qr_code_follower qr_follower.launch.py
```

Common options:

```bash
ros2 launch qr_code_follower qr_follower.launch.py \
  image_topic:=/camera/image_raw \
  camera_info_topic:=/camera/camera_info \
  follow_command_topic:=follow_command \
  follow_mode:=pose \
  enabled:=false
```

Direct-follow mode:

```bash
ros2 launch qr_code_follower qr_follower.launch.py follow_mode:=direct
```

Enable / disable at runtime:

```bash
ros2 service call /qr_follower/set_enabled std_srvs/srv/SetBool "{data: true}"
ros2 service call /qr_follower/set_enabled std_srvs/srv/SetBool "{data: false}"
```

Watch status:

```bash
ros2 topic echo /qr_follower/status
```

## Notes

- The integrated launch file is `src/tour_manager/launch/pepper_locomotion_llm.launch.py`.
- Simulation uses `turtlebot3_gazebo`; hardware mode uses `turtlebot3_bringup`.
- The workspace must be sourced after building before `ros2 launch` can find `tour_manager`.
- This system assumes a pre-built map for Nav2 localisation and does not perform live SLAM during tours.
