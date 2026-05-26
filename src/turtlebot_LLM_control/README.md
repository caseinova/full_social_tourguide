# TurtleBot LLM Control

Speech, LLM, and behaviour orchestration layer for the Social Guide Robot. Converts spoken natural language into structured ROS2 intents and robot actions using offline speech recognition, a local LLM, a PyQt5 waypoint GUI, and a behaviour-tree navigation orchestrator.

Developed by **Karan Sharma** — University of Technology Sydney, Robotics Studio 2 (41069).

> **Setup from scratch?** See [SETUP.md](SETUP.md) for the full installation guide.

---

## Features at a Glance

- **Wake-word speech pipeline** — listens only after "hey pepper"; returns to sleep on "good night pepper"
- **Offline STT** — faster-whisper (no internet, no API key, VAD-filtered)
- **LLM intent resolution** — rule-based parser first, then Ollama / Groq / OpenAI fallback for natural language
- **Behaviour-tree orchestration** — Nav2 goal dispatch with pause, resume, stop, and tour replay
- **TSP waypoint GUI** — PyQt5 map overlay for selecting a custom tour order; publishes directly to `/tsp_command`
- **Route recording** — teleop-driven waypoint capture with automatic teleop terminal launch
- **Follow-me** — colour-tracking person follower via camera
- **Emotion engine** — classifies each conversation turn into one of five robot states; publishes to `/emotions`
- **Text-to-speech** — spoken replies via `spd-say` / `espeak`
- **Mock mode** — full pipeline testable without a microphone

---

## Architecture

```
Microphone / /speech/mock_text
        │
        ▼
 speech_to_text_node          /speech/text ──────────────────────────────┐
        │                                                                  │
        ▼                                                                  ▼
 speech_command_node ──► /speech/intent ──► bt_orchestrator_node    emotion_node
        │            ──► /speech/response                │                │
        │            ──► /tsp_gui/show                   │           /emotions
        │                     │                          │
        │              tsp_gui_node                      ▼
        │                     │              NavigateToPose (Nav2)
        │              /tsp_command                      │
        │                     │              /route/record
        │            tour_intent_bridge_node      │
        │                                  tour_recording_manager
        │                                         │
        ▼                                  tour_teleop_session (xterm)
 speech_response_node (TTS)
 speech_debug_node     ──► /speech/debug
 emotion_node          ──► /emotions
```

---

## Nodes

### `speech_to_text_node`
Offline microphone listener using **faster-whisper**. Applies wake-word gating, deduplication, and TTS mute.

| Direction | Topic | Type |
|---|---|---|
| pub | `/speech/text` | `String` |
| pub | `/speech_to_text/status` | `String` |
| sub | `/speech/mock_text` | `String` |
| sub | `/speech/tts_active` | `Bool` |

Parameters:

| Parameter | Default | Description |
|---|---|---|
| `enable_microphone` | `false` | Enable live mic input |
| `mic_device_index` | `-1` | Mic device index (`-1` = system default) |
| `energy_threshold` | `300` | Minimum audio energy before capture starts |
| `dynamic_energy_threshold` | `true` | Auto-adjust energy threshold |
| `calibrate_ambient_noise` | `true` | Calibrate on startup |
| `phrase_time_limit` | `8.0` | Max seconds captured per phrase |
| `require_wake_word` | `true` | Ignore all speech until wake phrase |
| `wake_command_window_seconds` | `45.0` | Seconds robot stays awake after wake phrase |
| `tts_cooldown_seconds` | `5.0` | Silence period after TTS finishes |
| `whisper_model_size` | `"base"` | `tiny` / `base` / `small` / `medium` |
| `whisper_device` | `"cpu"` | `cpu` or `cuda` |

---

### `speech_command_node`
Resolves raw transcript to a structured `IntentToken` using the rule-based parser and LLM fallback. Intercepts `tsp` intent and routes it directly to the GUI instead of publishing to `/speech/intent`.

| Direction | Topic | Type |
|---|---|---|
| sub | `/speech/text` | `String` |
| pub | `/speech/intent` | `String` (JSON) |
| pub | `/speech/response` | `String` |
| pub | `/tsp_gui/show` | `String` |

Parameters:

| Parameter | Default | Description |
|---|---|---|
| `enable_llm` | `true` | Enable LLM fallback for unrecognised commands |
| `llm_provider` | `"ollama"` | `ollama`, `groq`, or `openai` |
| `llm_model` | `"qwen2.5-coder:latest"` | Model name |
| `llm_api_key_path` | `""` | Path to API key file (Groq / OpenAI only) |
| `personality` | (built-in) | System prompt personality string |

---

### `bt_orchestrator_node`
Behaviour-tree-based intent dispatcher. Receives intent JSON from `/speech/intent`, sends Nav2 goals, handles recording, touring, pause/resume, and follow-me.

| Direction | Topic | Type |
|---|---|---|
| sub | `/speech/intent` | `String` (JSON) |
| sub | `/route/data` | `String` (JSON) |
| pub | `/speech/response` | `String` |
| pub | `/tour/status` | `String` (JSON) |
| pub | `/route/record` | `String` |
| pub | `/route/replay` | `String` |
| pub | `/save_tour_command` | `String` |
| pub | `/manual_override/control` | `String` |
| pub | `/follow_me/control` | `String` |
| action | `/navigate_to_pose` | `NavigateToPose` |

**Simulation location map** (pillar positions in the demo Gazebo world):

| Label | x | y |
|---|---|---|
| `pillar_1` | -1.6 | -1.1 |
| `pillar_2` | -1.6 | 0.0 |
| `pillar_3` | -1.6 | 1.1 |
| `pillar_4` | -0.5 | -1.1 |
| `pillar_5` | -0.5 | 0.0 |
| `pillar_6` | -0.5 | 1.1 |
| `pillar_7` | 0.6 | -1.1 |
| `pillar_8` | 0.6 | 0.0 |
| `pillar_9` | 0.6 | 1.1 |

---

### `speech_response_node`
Converts `/speech/response` text to audio using system TTS (`spd-say` → `espeak` → `say`). Publishes `/speech/tts_active` to mute the microphone while speaking.

| Direction | Topic | Type |
|---|---|---|
| sub | `/speech/response` | `String` |
| pub | `/speech/tts_active` | `Bool` |

Parameters: `mute` (bool, default `false`)

---

### `speech_debug_node`
Aggregates all speech topics into a single `/speech/debug` stream. Useful for monitoring the full pipeline in one terminal.

| Direction | Topic | Type |
|---|---|---|
| sub | `/speech/text`, `/speech/intent`, `/speech/response`, `/speech_to_text/status` | `String` |
| pub | `/speech/debug` | `String` |

---

### `tsp_gui` (TSP Waypoint Selector)
Persistent PyQt5 GUI. Hides after Start and re-opens on the next trigger without restarting. Enforces single-instance via file lock.

| Direction | Topic | Type |
|---|---|---|
| sub | `/tsp_gui/show` | `String` |
| pub | `/tsp_command` | `TspCommand` (int64[] waypoints) |

- Click waypoints in the order you want to visit them
- Orange lines show the route preview
- **Start** — publish `TspCommand` and hide the window
- **Clear** — reset selection

Trigger manually for testing:
```bash
ros2 topic pub --once /tsp_gui/show std_msgs/msg/String "{data: show}"
ros2 topic echo /tsp_command
```

---

### `emotion_node`
Classifies each conversation turn into one of five robot emotion states and publishes to `/emotions`.

| Direction | Topic | Type |
|---|---|---|
| sub | `/speech/text` | `String` |
| sub | `/speech/response` | `String` |
| pub | `/emotions` | `String` |

| Emotion | Trigger |
|---|---|
| `thinking` | STT fires — robot is processing before LLM replies |
| `greeting` | Response contains hello / welcome / hi phrases |
| `explaining` | Response ≥ 60 words or contains narration phrases |
| `speaking` | Short conversational reply (default) |
| `idle` | No activity for `idle_timeout_seconds` (default 15 s) |

Parameters: `idle_timeout_seconds` (float, default `15.0`)

---

### `tour_recording_manager`
Records robot routes via AMCL pose sampling during manual teleop. Launches an `xterm` terminal running `tour_teleop_session` automatically.

| Direction | Topic | Type |
|---|---|---|
| sub | `/route/record` | `String` (`start:<label>` or `stop`) |
| sub | `/save_tour_command` | `String` |
| sub | `/amcl_pose` | `PoseWithCovarianceStamped` |
| pub | `/route/data` | `String` (JSON) |
| pub | `/tour/status` | `String` |
| pub | `/manual_override/control` | `String` |

Waypoints are sampled every 0.5 s when the robot moves more than 5 cm or rotates more than 0.1 rad.

---

### `tour_teleop_session`
Keyboard teleop session run inside an auto-launched terminal during route recording. Uses `w / a / s / d` for movement. Press `r` + Enter to publish the route label; `Esc` to stop.

---

### `waypoint_speaker_node`
Reads waypoint descriptions from a SQLite database and speaks them aloud when the robot arrives at a stop. Includes a pose-based failsafe that overrides the published index if the robot is actually closer to a different waypoint.

| Direction | Topic | Type |
|---|---|---|
| sub | `/talk_command` | `String` (contains waypoint index, e.g. `"reached at waypoint 2"`) |
| sub | `/amcl_pose` | `PoseWithCovarianceStamped` |
| pub | `/done_talking` | `String` (`"done_speaking"`) |
| pub | `/done_speaking` | `String` (`"done_speaking"`) |
| pub | `/robot/emotion` | `String` (JSON: `{emotion, context, intensity}`) |

Parameters:

| Parameter | Default | Description |
|---|---|---|
| `db_path` | `tours.db` | Path to SQLite database with `tours` table (`px`, `py`, `description`) |

The node extracts the last integer from the `/talk_command` message as the waypoint index. If the robot is >0.5 m closer to a different waypoint than the published index, it silently corrects to the nearest one. TTS uses `spd-say` → `espeak` → `say` (first available).

---

### `tour_intent_bridge_node`
Bridges `start_recording` and `stop_recording` intents from `/speech/intent` to `/route/record`. Also triggers recording from a default route label.

Parameters: `default_route_label` (default `"saved_route"`)

---

### `sim_initial_pose_node`
Publishes an initial pose estimate to `/initialpose` at startup for Gazebo simulation. Used by the `sim_pillar_nav_demo` launch.

Parameters: `x`, `y`, `yaw`

---

### `llm_intent_test`
Standalone command-line tester. No ROS nav stack required. Tests the full STT → intent → response pipeline from the terminal.

```bash
ros2 run turtlebot_llm_control llm_intent_test \
  --provider ollama \
  --model qwen2.5-coder:latest \
  --microphone

# All flags:
#   --provider   ollama | groq | openai
#   --model      model name
#   --key        path to api key file
#   --microphone enable live mic
#   --mute       disable TTS
#   --no-llm     rule-based only
#   --list-microphones
#   --mic-device INDEX
#   --energy-threshold INT
#   --wake-timeout SECONDS
```

---

## Launch Files

### `intent_only.launch.py` — Speech + LLM layer only

Use this when the `turtlebot_social_guide` workspace owns navigation, touring, and docking.

```bash
source /opt/ros/humble/setup.bash
source /home/karan/Development/robot_gpt/turtlebot_social_guide/install/setup.bash
source /home/karan/Development/robot_gpt/llm_ws_1/install/setup.bash

ros2 launch turtlebot_llm_control intent_only.launch.py \
  enable_microphone:=true \
  llm_provider:=ollama \
  llm_model:=qwen2.5-coder:latest
```

All arguments:

| Argument | Default | Description |
|---|---|---|
| `enable_microphone` | `true` | Live mic STT |
| `mic_device_index` | `-1` | Mic device index |
| `energy_threshold` | `150` | Mic capture threshold |
| `dynamic_energy_threshold` | `false` | Auto-adjust threshold |
| `calibrate_ambient_noise` | `false` | Noise calibration on start |
| `phrase_time_limit` | `5.0` | Max seconds per phrase |
| `require_wake_word` | `true` | Wake-word gating |
| `wake_command_window_seconds` | `45.0` | Awake window duration |
| `enable_llm` | `true` | LLM fallback |
| `llm_provider` | `ollama` | `ollama` / `groq` / `openai` |
| `llm_model` | `qwen2.5-coder:latest` | Model name |
| `llm_api_key_path` | `""` | Path to API key file |
| `intent_topic` | `/speech/intent` | Remap intent output topic |
| `enable_speech_debug` | `true` | Launch debug aggregator |
| `enable_speech_response` | `true` | Launch TTS speaker |
| `enable_tour_teleop_trigger` | `true` | Launch recording bridge |
| `default_route_label` | `saved_route` | Route label for recording |
| `mute` | `false` | Disable TTS output |
| `enable_tsp_gui` | `true` | Launch TSP waypoint GUI |
| `enable_emotion` | `true` | Launch emotion publisher |
| `enable_waypoint_speaker` | `true` | Launch waypoint description speaker |
| `waypoint_db_path` | `tours.db` | Path to SQLite waypoint database |
| `use_sim_time` | `false` | Use simulation clock |

---

### `sim_pillar_nav_demo.launch.py` — Full Gazebo demo

Launches Gazebo, Nav2, RViz, and the full LLM bringup in one command.

```bash
export TURTLEBOT3_MODEL=waffle
source /opt/ros/humble/setup.bash
source /home/karan/Development/robot_gpt/llm_ws_1/install/setup.bash

ros2 launch turtlebot_llm_control sim_pillar_nav_demo.launch.py \
  enable_microphone:=true \
  llm_provider:=ollama \
  llm_model:=qwen2.5-coder:latest
```

Arguments: same as `intent_only` plus:

| Argument | Default | Description |
|---|---|---|
| `enable_direct_locomotion_interface` | `false` | Also launch `speech_locomotion_interface` package |

Launches: Gazebo world → Nav2 bringup → RViz → full LLM bringup → initial pose publisher.

---

### `bringup.launch.py` — LLM bringup (included by sim demo)

Launches all speech nodes: STT, command, response, debug, BT orchestrator, tour recording manager, follow-me. Used internally by `sim_pillar_nav_demo.launch.py`.

---

## All ROS2 Topics

| Topic | Type | Published by | Subscribed by |
|---|---|---|---|
| `/speech/text` | `String` | `speech_to_text_node` | `speech_command_node`, `emotion_node` |
| `/speech/mock_text` | `String` | (external) | `speech_to_text_node` |
| `/speech/intent` | `String` (JSON) | `speech_command_node` | `bt_orchestrator_node`, `tour_intent_bridge_node` |
| `/speech/response` | `String` | `speech_command_node`, `bt_orchestrator_node` | `speech_response_node`, `emotion_node` |
| `/speech/debug` | `String` | `speech_debug_node` | (monitor) |
| `/speech_to_text/status` | `String` | `speech_to_text_node` | `speech_debug_node` |
| `/speech/tts_active` | `Bool` | `speech_response_node` | `speech_to_text_node` |
| `/tsp_gui/show` | `String` | `speech_command_node` | `tsp_gui_node` |
| `/tsp_command` | `TspCommand` | `tsp_gui_node` | navigation layer |
| `/emotions` | `String` | `emotion_node` | (external / display) |
| `/tour/status` | `String` (JSON) | `bt_orchestrator_node`, `tour_recording_manager` | (monitor) |
| `/route/record` | `String` | `bt_orchestrator_node`, `tour_intent_bridge_node` | `tour_recording_manager` |
| `/route/data` | `String` (JSON) | `tour_recording_manager` | `bt_orchestrator_node` |
| `/route/replay` | `String` | `bt_orchestrator_node` | (navigation layer) |
| `/save_tour_command` | `String` | `bt_orchestrator_node` | `tour_recording_manager` |
| `/manual_override/control` | `String` | `bt_orchestrator_node`, `tour_recording_manager` | (navigation layer) |
| `/follow_me/control` | `String` | `bt_orchestrator_node` | `follow_me_node` |
| `/follow_me/debug` | `Image` | `follow_me_node` | (optional viewer) |
| `/cmd_vel` | `Twist` | `follow_me_node` | robot base |
| `/amcl_pose` | `PoseWithCovarianceStamped` | Nav2 | `tour_recording_manager` |

---

## Voice Commands Reference

### Wake / Sleep

| Phrase | Effect |
|---|---|
| `hey pepper` / `hi pepper` / `hello pepper` | Wake up — robot listens for 45 s |
| `good night pepper` / `sleep pepper` | Return to sleep |
| `stop` / `stop stop` / `emergency stop` | Immediate stop (bypasses wake gate) |

### Navigation

| Phrase | Intent | Notes |
|---|---|---|
| `go to pillar 3` | `navigate` | Pillars 1–9 supported |
| `take me to the lab` | `navigate` | Custom location (LLM resolves) |
| `head to waypoint 2` | `navigate` | |
| `navigate to the entrance` | `navigate` | |

### Touring

| Phrase | Intent | Notes |
|---|---|---|
| `start the tour` / `full tour` | `start_tour` | All waypoints in sequence |
| `show me around` / `short tour` | `tsp` | Opens waypoint GUI for custom selection |
| `let me choose some stops` | `tsp` | |
| `pick some places` | `tsp` | |

### Recording

| Phrase | Intent | Notes |
|---|---|---|
| `start recording` | `start_recording` | Launches teleop terminal |
| `stop recording` | `stop_recording` | Ends session |
| `save route as my_route` | `save_route` | Label extracted from phrase |
| `replay my_route` | `replay_route` | |

### Control

| Phrase | Intent |
|---|---|
| `stop` / `halt` / `abort` / `cancel` | `stop` |
| `stop navigation` / `cancel navigation` | `stop_navigation` |
| `pause` | `pause` |
| `resume` | `resume` |
| `go home` / `go charge` / `recharge` | `dock` |
| `manual override` / `enable teleop` | `manual_override_on` |
| `return to autonomous` | `manual_override_off` |

### Conversation

| Phrase | Intent |
|---|---|
| `are you awake` / `are you there` | `is_alive` |
| `what can you do` | `no_action` (capabilities summary) |
| `tell me about the lab` | `explain` |
| Anything else | `no_action` (LLM responds naturally) |

---

## Route Recording Workflow

1. Say **"start recording"** (or publish `start:<label>` on `/route/record`)
2. An `xterm` terminal opens running the teleop session
3. Drive the robot with `w` / `a` / `s` / `d`
4. Press `r` + Enter in the teleop terminal to set the route label
5. Press `Esc` to stop teleop — recording ends automatically
6. The route is published on `/route/data` as JSON

---

## Testing Without a Microphone (Mock Mode)

```bash
# Terminal 1 — launch speech pipeline
ros2 launch turtlebot_llm_control intent_only.launch.py enable_microphone:=false

# Terminal 2 — inject speech
ros2 topic pub --once /speech/mock_text std_msgs/msg/String "{data: 'hey pepper go to pillar 5'}"

# Monitor all speech activity
ros2 topic echo /speech/debug

# Monitor intent
ros2 topic echo /speech/intent

# Monitor emotion state
ros2 topic echo /emotions

# Trigger TSP GUI
ros2 topic pub --once /tsp_gui/show std_msgs/msg/String "{data: show}"

# Check TSP waypoint output
ros2 topic echo /tsp_command
```

---

## Intent JSON Format

Every message on `/speech/intent` is a JSON string:

```json
{
  "intent": "navigate",
  "label": "",
  "location": "pillar_5",
  "utterance": "go to pillar five",
  "response": "Navigating to pillar_5.",
  "metadata": {}
}
```

Fields:

| Field | Description |
|---|---|
| `intent` | One of the intents in the table above |
| `label` | Route label (for recording / replay intents) |
| `location` | Normalised location name (navigate / explain intents) |
| `utterance` | Original spoken text |
| `response` | Text the robot will speak aloud |
| `metadata` | Extra data (e.g. `waypoints` list for TSP) |

---

## Pre-launch Checklist

1. `ollama serve` is running — `curl http://localhost:11434/api/tags` responds
2. `colcon build --packages-select turtlebot_llm_control && source install/setup.bash`
3. `export TURTLEBOT3_MODEL=waffle` (Gazebo demo only)
4. Watch `ros2 topic echo /speech_to_text/status` on startup — look for `Loaded faster-whisper 'base' model`
5. Watch `ros2 topic echo /speech/debug` during the demo for the combined pipeline view
