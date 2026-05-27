import threading

from std_msgs.msg import String
from std_msgs.msg import Bool

import rclpy
from rclpy.node import Node

from turtlebot_llm_control.audio_utils import speak_text


class SpeechResponseNode(Node):
    def __init__(self):
        super().__init__("speech_response_node")
        self.mute = bool(self.declare_parameter("mute", False).value)
        self.tts_state_publisher = self.create_publisher(Bool, "/speech/tts_active", 10)
        self.pepper_speech_publisher = self.create_publisher(String, "/pepper_speech", 10)
        self.done_talking_publisher = self.create_publisher(String, "/done_talking", 10)
        self.subscription = self.create_subscription(
            String, "/speech/response", self.handle_response, 10
        )
        self.get_logger().info("Speech response node ready. mute=%s" % self.mute)

    def handle_response(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return
        pepper_msg = String()
        pepper_msg.data = text
        self.pepper_speech_publisher.publish(pepper_msg)
        if self.mute:
            self.done_talking_publisher.publish(String(data="done_speaking"))
            return

        def speak_then_signal():
            self.publish_tts_state(True)
            try:
                if not speak_text(text):
                    self.get_logger().warning(
                        "No local TTS command available. Install spd-say, espeak, or say to hear responses."
                    )
            finally:
                self.publish_tts_state(False)
                self.done_talking_publisher.publish(String(data="done_speaking"))

        threading.Thread(target=speak_then_signal, daemon=True).start()

    def publish_tts_state(self, active: bool) -> None:
        msg = Bool()
        msg.data = bool(active)
        self.tts_state_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SpeechResponseNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
