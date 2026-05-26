# Setup Guide — TurtleBot LLM Control

Complete environment and installation guide. Follow every section in order on a fresh machine.

---

## System Requirements

| Item | Requirement |
|---|---|
| OS | Ubuntu 22.04 LTS |
| ROS | ROS2 Humble Hawksbill |
| Python | 3.10 (ships with Ubuntu 22.04) |
| RAM | 8 GB minimum, 16 GB recommended |
| GPU | Optional — CPU-only is fully supported |

---

## 1. ROS2 Humble

If ROS2 Humble is not yet installed:

```bash
sudo apt update && sudo apt install -y software-properties-common curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools
```

Add to `~/.bashrc`:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## 2. TurtleBot3 Packages (for Gazebo simulation)

```bash
sudo apt install -y \
  ros-humble-turtlebot3 \
  ros-humble-turtlebot3-simulations \
  ros-humble-turtlebot3-gazebo \
  ros-humble-nav2-bringup \
  ros-humble-nav2-simple-commander \
  ros-humble-tf-transformations
```

Set your robot model (add to `~/.bashrc`):

```bash
echo "export TURTLEBOT3_MODEL=waffle" >> ~/.bashrc
source ~/.bashrc
```

---

## 3. System Audio & TTS

```bash
sudo apt install -y \
  speech-dispatcher \
  espeak \
  portaudio19-dev \
  python3-pyaudio
```

Verify TTS works:

```bash
spd-say "hello"
# or
espeak "hello"
```

---

## 4. Python Dependencies

Install all Python packages in one go:

```bash
pip install \
  faster-whisper \
  openai \
  PyQt5 \
  numpy \
  opencv-python \
  SpeechRecognition \
  pyaudio
```

| Package | Purpose |
|---|---|
| `faster-whisper` | Offline STT engine — no internet needed at runtime |
| `openai` | HTTP client for Ollama, OpenAI, and Groq |
| `PyQt5` | TSP waypoint selector GUI |
| `numpy` | Map rendering and audio processing |
| `opencv-python` | Follow-me colour tracking |
| `SpeechRecognition` | Microphone capture (used by the STT node) |
| `pyaudio` | Audio backend for SpeechRecognition |

---

## 5. Local LLM — Ollama (default, no API key needed)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull the default model:

```bash
ollama pull qwen2.5-coder
```

Start the Ollama server (runs in background automatically on most installs, otherwise):

```bash
ollama serve &
```

Verify it is reachable:

```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response listing available models.

---

## 6. Cloud LLM Providers (optional)

Use these if you want a cloud model instead of Ollama.

### Groq

```bash
pip install groq
```

Set your key as an environment variable (add to `~/.bashrc`):

```bash
export GROQ_API_KEY="your_groq_api_key_here"
```

Or drop it in a file:

```bash
echo "your_groq_api_key_here" > \
  ~/Development/robot_gpt/llm_ws_1/src/turtlebot_LLM_control/turtlebot_llm_control/api.key
```

### OpenAI

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

**Key resolution order** (checked in this order):
1. `GROQ_API_KEY` / `OPENAI_API_KEY` environment variable
2. `llm_api_key_path` launch argument pointing to a file
3. `turtlebot_llm_control/api.key` next to the Python source files

---

## 7. social_robot_interfaces (for intent-only mode)

This workspace depends on the custom message types from `turtlebot_social_guide`. Build that workspace first if you are using `intent_only.launch.py`:

```bash
cd /home/karan/Development/robot_gpt/turtlebot_social_guide
source /opt/ros/humble/setup.bash
colcon build --packages-select social_robot_interfaces
source install/setup.bash
```

---

## 8. Build This Workspace

```bash
cd /home/karan/Development/robot_gpt/llm_ws_1
source /opt/ros/humble/setup.bash

# If using intent_only mode, source turtlebot_social_guide first:
source /home/karan/Development/robot_gpt/turtlebot_social_guide/install/setup.bash

colcon build --packages-select turtlebot_llm_control
source install/setup.bash
```

Rebuild after any source change:

```bash
colcon build --packages-select turtlebot_llm_control && source install/setup.bash
```

---

## 9. Source Order

Always source in this order or commands will fail with missing packages:

```bash
source /opt/ros/humble/setup.bash
source /home/karan/Development/robot_gpt/turtlebot_social_guide/install/setup.bash  # intent_only mode only
source /home/karan/Development/robot_gpt/llm_ws_1/install/setup.bash
```

Add the first two to `~/.bashrc` if you want them persistent. Source the workspace install manually after each build.

---

## 10. Microphone Setup

List available microphones:

```bash
ros2 run turtlebot_llm_control llm_intent_test --list-microphones
```

Example output:
```
[0] Built-in Microphone
[1] USB Audio Device
```

Use the index when launching:

```bash
ros2 launch turtlebot_llm_control intent_only.launch.py \
  enable_microphone:=true \
  mic_device_index:=1
```

Test that the microphone is picking up audio before a demo:

```bash
python3 -c "
import speech_recognition as sr
r = sr.Recognizer()
with sr.Microphone() as src:
    r.adjust_for_ambient_noise(src, duration=1)
    print('Listening...')
    audio = r.listen(src, timeout=5)
    print('Heard audio, length:', len(audio.get_raw_data()), 'bytes')
"
```

---

## 11. Whisper Model

The faster-whisper model downloads automatically on first run into `~/.cache/huggingface/`.

| Model | Size | Best for |
|---|---|---|
| `tiny` | ~75 MB | fastest, lowest accuracy |
| `base` | ~145 MB | default — good balance |
| `small` | ~465 MB | better accuracy, still real-time on CPU |
| `medium` | ~1.5 GB | best accuracy, slower on CPU |

Pre-download before a demo (avoids first-run delay):

```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
```

---

## 12. Verify the Full Stack

```bash
# ROS2 available
ros2 --version

# Ollama responding
curl http://localhost:11434/api/tags

# faster-whisper importable
python3 -c "from faster_whisper import WhisperModel; print('ok')"

# PyQt5 importable
python3 -c "from PyQt5.QtWidgets import QApplication; print('ok')"

# OpenCV importable
python3 -c "import cv2; print('ok')"

# TTS working
spd-say "setup complete"

# social_robot_interfaces available (intent_only mode)
ros2 interface show social_robot_interfaces/msg/TspCommand
```

---

## 13. Troubleshooting

**`colcon build` fails with missing `social_robot_interfaces`**
Source `turtlebot_social_guide/install/setup.bash` before building, or build `social_robot_interfaces` first (see section 7).

**`faster-whisper` not found**
```bash
pip install faster-whisper
```

**Ollama connection refused**
```bash
ollama serve
# or check the service:
systemctl status ollama
```

**No audio from `spd-say`**
```bash
sudo systemctl start speech-dispatcher
```

**TSP GUI does not open**
PyQt5 must be installed and a display must be available. On headless machines set `DISPLAY=:0` or use a virtual framebuffer (`Xvfb`).

**Nav2 action server not ready**
`bt_orchestrator_node` prints a warning and retries automatically. Wait 10–20 s after launch for Nav2 to fully initialise before issuing navigation commands.

**Whisper transcribes garbage / empty strings**
Lower the energy threshold or adjust the microphone device:
```bash
ros2 launch turtlebot_llm_control intent_only.launch.py \
  enable_microphone:=true \
  energy_threshold:=100 \
  dynamic_energy_threshold:=true \
  calibrate_ambient_noise:=true
```

**`ImportError: No module named 'groq'`**
```bash
pip install groq
```
