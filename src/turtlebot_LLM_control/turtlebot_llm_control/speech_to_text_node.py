from difflib import get_close_matches
from time import monotonic
from typing import Optional

from std_msgs.msg import Bool, String

import rclpy
from rclpy.node import Node

from turtlebot_llm_control.audio_utils import suppress_stderr
from turtlebot_llm_control.predefined_commands import PREDEFINED_COMMANDS
from turtlebot_llm_control.wake_word import canonicalize_robot_name
from turtlebot_llm_control.wake_word import (
    is_emergency_stop_request,
    is_sleep_request,
    normalize_text,
    strip_wake_phrase,
)


class SpeechToTextNode(Node):
    def __init__(self):
        super().__init__("speech_to_text_node")
        self.enable_microphone = self.declare_parameter("enable_microphone", False).value
        self.mic_device_index = int(self.declare_parameter("mic_device_index", -1).value)
        self.energy_threshold = int(self.declare_parameter("energy_threshold", 300).value)
        self.dynamic_energy_threshold = self.declare_parameter("dynamic_energy_threshold", True).value
        self.calibrate_ambient_noise = self.declare_parameter("calibrate_ambient_noise", True).value
        self.phrase_time_limit = float(self.declare_parameter("phrase_time_limit", 8.0).value)
        self.require_wake_word = bool(self.declare_parameter("require_wake_word", True).value)
        self.wake_command_window_seconds = float(
            self.declare_parameter("wake_command_window_seconds", 45.0).value
        )
        self.tts_cooldown_seconds = float(self.declare_parameter("tts_cooldown_seconds", 5.0).value)
        self.command_lock_seconds = float(self.declare_parameter("command_lock_seconds", 8.0).value)
        self.duplicate_recognition_window_seconds = float(
            self.declare_parameter("duplicate_recognition_window_seconds", 2.5).value
        )
        self.whisper_model_size = str(self.declare_parameter("whisper_model_size", "base").value)
        self.whisper_device = str(self.declare_parameter("whisper_device", "cpu").value)

        self.text_publisher = self.create_publisher(String, "/speech/text", 10)
        self.status_publisher = self.create_publisher(String, "/speech_to_text/status", 10)
        self.mock_subscription = self.create_subscription(
            String, "/speech/mock_text", self.handle_mock_text, 10
        )
        self.tts_subscription = self.create_subscription(
            Bool, "/speech/tts_active", self.handle_tts_state, 10
        )

        self.recognizer = None
        self.microphone = None
        self.stop_background_listener = None
        self.whisper_model = None
        self.wake_active_until = 0.0
        self.tts_active = False
        self.tts_active_until = 0.0
        self.command_locked_until = 0.0
        self._last_published_text: str = ""
        self._last_published_time: float = 0.0

        if self.enable_microphone:
            self.setup_microphone_listener()
        else:
            self.publish_status("Speech-to-text node ready in mock mode. Publish on /speech/mock_text.")

    def setup_microphone_listener(self) -> None:
        try:
            import speech_recognition as sr
        except ImportError:
            self.publish_status(
                "speech_recognition is not installed. Falling back to /speech/mock_text input."
            )
            return

        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = self.energy_threshold
            self.recognizer.dynamic_energy_threshold = bool(self.dynamic_energy_threshold)
            device_index = self.mic_device_index if self.mic_device_index >= 0 else None
            with suppress_stderr():
                self.microphone = sr.Microphone(device_index=device_index)
        except Exception as exc:
            self.publish_status("Failed to initialize microphone STT: %s" % exc)
            return

        if self.calibrate_ambient_noise:
            with suppress_stderr(), self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)

        try:
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel(
                self.whisper_model_size,
                device=self.whisper_device,
                compute_type="int8",
            )
            self.publish_status("Loaded faster-whisper '%s' model." % self.whisper_model_size)
        except ImportError:
            self.publish_status(
                "faster-whisper not installed; falling back to Google STT. "
                "Install with: pip install faster-whisper"
            )
        except Exception as exc:
            self.publish_status(
                "Failed to load faster-whisper: %s. Falling back to Google STT." % exc
            )

        with suppress_stderr():
            self.stop_background_listener = self.recognizer.listen_in_background(
                self.microphone,
                self.handle_audio,
                phrase_time_limit=self.phrase_time_limit,
            )
        self.publish_status(
            "Speech-to-text microphone listener started. device=%s energy_threshold=%s "
            "dynamic_energy=%s calibrate_ambient_noise=%s. Say a wake phrase like 'hey pepper'."
            % (
                "default" if self.mic_device_index < 0 else self.mic_device_index,
                int(self.recognizer.energy_threshold),
                bool(self.dynamic_energy_threshold),
                bool(self.calibrate_ambient_noise),
            )
        )

    def handle_audio(self, recognizer, audio) -> None:
        if self.is_tts_active():
            return
        transcript = self.transcribe_audio(recognizer, audio)
        if not transcript or self.is_tts_active():
            return
        self.process_recognized_text(transcript)

    def transcribe_audio(self, recognizer, audio) -> str:
        try:
            if self.whisper_model is not None:
                import numpy as np
                raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                _prompt = (
                    "stop navigate tour dock pillar pepper hey robot "
                    "pause resume recording route waypoint charge recharge"
                )
                segments, _ = self.whisper_model.transcribe(
                    audio_np,
                    beam_size=1,
                    language="en",
                    vad_filter=True,
                    initial_prompt=_prompt,
                )
                raw_text = " ".join(seg.text for seg in segments).strip()
            else:
                raw_text = recognizer.recognize_google(audio)
        except Exception as exc:
            error_text = str(exc).strip()
            if error_text:
                self.publish_status("Speech recognition failed: %s" % error_text)
            else:
                self.publish_status("Speech recognition could not understand the audio.")
            return ""

        normalized = raw_text.strip().lower()
        if not normalized:
            return ""
        return normalized

    def find_best_command(self, text: str) -> Optional[str]:
        if self.should_skip_fuzzy_match(text):
            return None
        matches = get_close_matches(text, PREDEFINED_COMMANDS, n=1, cutoff=0.6)
        return matches[0] if matches else None

    def should_skip_fuzzy_match(self, text: str) -> bool:
        normalized = canonicalize_robot_name(text)
        multiword_phrases = (
            "go to ",
            "navigate to ",
            "take me to ",
            "tell me about ",
            "explain ",
            "pillar ",
            "pillow ",
            "below ",
        )
        if any(phrase in normalized for phrase in multiword_phrases):
            return True
        return len(normalized.split()) > 2

    def handle_mock_text(self, msg: String) -> None:
        normalized = msg.data.strip().lower()
        if not normalized:
            return
        if self.is_tts_active():
            self.publish_status("Ignored mock speech while TTS is active.")
            return
        self.process_recognized_text(normalized)

    def handle_tts_state(self, msg: Bool) -> None:
        self.tts_active = bool(msg.data)
        if self.tts_active:
            self.tts_active_until = monotonic()
            self.publish_status("Speech playback active. Temporarily ignoring microphone input.")
        else:
            self.tts_active_until = monotonic() + self.tts_cooldown_seconds
            self.publish_status(
                "Speech playback finished. Resuming microphone input after %.1f seconds."
                % self.tts_cooldown_seconds
            )

    def is_tts_active(self) -> bool:
        return self.tts_active or monotonic() <= self.tts_active_until

    def process_recognized_text(self, text: str) -> None:
        gated_text = self.apply_wake_word_gate(text)
        if not gated_text:
            return

        now = monotonic()
        dedup_key = normalize_text(gated_text)
        if (
            now <= self.command_locked_until
            and not is_emergency_stop_request(gated_text)
            and not is_sleep_request(gated_text)
        ):
            self.publish_status("Command lock active, suppressing fragment: %s" % gated_text)
            return
        if (
            dedup_key
            and not is_emergency_stop_request(gated_text)
            and not is_sleep_request(gated_text)
            and dedup_key == self._last_published_text
            and now - self._last_published_time < self.duplicate_recognition_window_seconds
        ):
            self.publish_status("Dropped duplicate recognized speech: %s" % gated_text)
            return

        exact_match = next((cmd for cmd in PREDEFINED_COMMANDS if cmd == gated_text), None)
        if exact_match:
            self.publish_recognized_text(exact_match)
            return

        close_match = self.find_best_command(gated_text)
        if close_match:
            self.publish_status("Recognized '%s' as '%s'." % (gated_text, close_match))
            self.publish_recognized_text(close_match)
            return

        self.publish_status("Heard '%s' but it is not in the predefined command set." % gated_text)
        self.publish_recognized_text(gated_text)

    def apply_wake_word_gate(self, text: str) -> str:
        normalized = text.strip().lower()
        if not normalized:
            return ""
        if not self.require_wake_word:
            return normalized
        if is_emergency_stop_request(normalized):
            self.wake_active_until = 0.0
            self.publish_status("Emergency stop detected. Stopping active tasks immediately.")
            return "stop"
        if is_sleep_request(normalized):
            self.wake_active_until = 0.0
            self.publish_status("Sleep command detected. Stopping active tasks and returning to sleep.")
            return "stop"

        wake_command = strip_wake_phrase(normalized)
        now = monotonic()
        if wake_command is not None:
            self.wake_active_until = now + self.wake_command_window_seconds
            if wake_command:
                self.publish_status("Wake phrase detected. Processing '%s'." % wake_command)
                return wake_command
            self.publish_status(
                "Wake phrase detected. Pepper is awake for %.0f seconds."
                % self.wake_command_window_seconds
            )
            return ""

        if now <= self.wake_active_until:
            self.wake_active_until = now + self.wake_command_window_seconds
            return normalized

        self.publish_status(
            "Ignored speech until wake phrase like 'hey', 'hi', 'hello', or 'hey pepper' is heard."
        )
        return ""

    def publish_recognized_text(self, text: str) -> None:
        now = monotonic()
        if now - self._last_published_time < 3.0:
            self.publish_status("STT cooldown active, suppressing: %s" % text)
            return
        self._last_published_text = normalize_text(text)
        self._last_published_time = now
        if not is_emergency_stop_request(text) and not is_sleep_request(text):
            self.command_locked_until = now + self.command_lock_seconds
        msg = String()
        msg.data = text
        self.text_publisher.publish(msg)
        self.publish_status(
            "Published recognized text: %s (lock %.1fs)" % (text, self.command_lock_seconds)
        )

    def publish_status(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.status_publisher.publish(msg)
        self.get_logger().info(text)

    def shutdown_listener(self) -> None:
        if self.stop_background_listener is not None:
            self.stop_background_listener(wait_for_stop=False)
            self.stop_background_listener = None


def main(args=None):
    rclpy.init(args=args)
    node = SpeechToTextNode()
    try:
        rclpy.spin(node)
    finally:
        node.shutdown_listener()
        node.destroy_node()
        rclpy.shutdown()
