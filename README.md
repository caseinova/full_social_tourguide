# Big Workspace

ROS 2 workspace for the TurtleBot tour stack, Pepper HRI integration, and
speech/LLM intent control.

## Build

From the workspace root:

```bash
colcon build
source install/setup.bash
```

For only the integrated launch package:

```bash
colcon build --packages-select tour_manager
source install/setup.bash
```

## Integrated Pepper, TurtleBot, and LLM Launch

The workspace-level integrated launch is:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

This starts the current locomotion test stack and can optionally include:

- real Pepper support from `pepper_hri/pepper_real.launch.py`
- intent-only speech and LLM control from
  `turtlebot_llm_control/intent_only.launch.py`
- either Gazebo TurtleBot simulation or real TurtleBot bringup

The LLM intent launch is wired with:

```bash
enable_microphone:=true
llm_provider:=groq
llm_model:=llama-3.1-8b-instant
```

## Common Commands

Default: Gazebo TurtleBot, Pepper enabled, intent control enabled.

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py
```

Use the real TurtleBot instead of Gazebo:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py turtlebot_mode:=real
```

Disable real Pepper HRI:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_pepper:=false
```

Disable the LLM intent layer:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py enable_intent:=false
```

Run real TurtleBot with Pepper and intent disabled:

```bash
ros2 launch tour_manager pepper_locomotion_llm.launch.py \
  turtlebot_mode:=real \
  enable_pepper:=false \
  enable_intent:=false
```

## Launch Arguments

| Argument | Default | Description |
| --- | --- | --- |
| `turtlebot_mode` | `sim` | `sim` launches Gazebo, `real` launches physical TurtleBot bringup. |
| `use_sim_time` | `true` in sim, `false` in real | Clock mode passed through to Nav2 and intent nodes. |
| `enable_pepper` | `true` | Starts real Pepper HRI nodes. |
| `enable_intent` | `true` | Starts the intent-only speech and LLM nodes. |
| `model` | `waffle_pi` | TurtleBot3 model. |
| `lds_model` | `LDS-02` | Lidar model for real TurtleBot bringup. |
| `usb_port` | `/dev/ttyACM0` | OpenCR USB port for real TurtleBot mode. |
| `namespace` | empty | Namespace forwarded to real TurtleBot bringup. |
| `nav2_params_file` | TurtleBot3 `waffle_pi.yaml` | Nav2 parameters file. |

## Notes

- `turtlebot_mode:=sim` launches `turtlebot3_gazebo/turtlebot3_world.launch.py`.
- `turtlebot_mode:=real` launches `turtlebot3_bringup/robot.launch.py`.
- Nav2 and the tour manager launch in both modes.
- The workspace must be sourced after building before `ros2 launch` can find
  `tour_manager`.
