from time import monotonic

from std_msgs.msg import String

import rclpy
from rclpy.node import Node

# Emotions the robot can express
THINKING = "thinking"
SPEAKING = "speaking"
EXPLAINING = "explaining"
GREETING = "greeting"
IDLE = "idle"

_GREETING_WORDS = {
    "hello", "hi", "hey", "welcome", "greetings", "good morning",
    "good afternoon", "good evening", "nice to meet", "pleased to meet",
    "glad to meet", "howdy",
}

_EXPLAINING_WORDS = {
    "this is", "here you", "let me explain", "let me tell", "allow me",
    "this building", "this area", "this room", "this section", "this exhibit",
    "was built", "was founded", "is located", "you can see", "you will see",
    "named after", "known for", "famous for", "history", "dates back",
    "century", "originally",
}

_EXPLAINING_WORD_THRESHOLD = 60


def classify_response(text: str) -> str:
    """Return one of the five emotion states based on response content."""
    lower = text.lower()

    # Greeting: short AND starts with or contains a greeting word
    for phrase in _GREETING_WORDS:
        if lower.startswith(phrase) or (f" {phrase}" in lower and len(text.split()) < 30):
            return GREETING

    # Explaining: long response or contains topic-narration phrases
    word_count = len(text.split())
    if word_count >= _EXPLAINING_WORD_THRESHOLD:
        return EXPLAINING
    for phrase in _EXPLAINING_WORDS:
        if phrase in lower:
            return EXPLAINING

    return SPEAKING


class EmotionNode(Node):
    def __init__(self):
        super().__init__("emotion_node")
        self.idle_timeout = float(self.declare_parameter("idle_timeout_seconds", 15.0).value)

        self._emotion_pub = self.create_publisher(String, "/emotions", 10)
        self._speech_text_sub = self.create_subscription(
            String, "/speech/text", self._on_speech_text, 10
        )
        self._response_sub = self.create_subscription(
            String, "/speech/response", self._on_response, 10
        )
        self._idle_timer = self.create_timer(2.0, self._check_idle)
        self._last_activity = monotonic()
        self._current_emotion = IDLE

        self._publish(IDLE)
        self.get_logger().info("Emotion node ready. Publishing on /emotions.")

    def _on_speech_text(self, msg: String) -> None:
        """User spoke — robot starts thinking immediately."""
        self._last_activity = monotonic()
        self._publish(THINKING)

    def _on_response(self, msg: String) -> None:
        """LLM replied — classify the response text and publish the emotion."""
        self._last_activity = monotonic()
        text = msg.data.strip()
        if not text:
            return
        emotion = classify_response(text)
        self._publish(emotion)

    def _check_idle(self) -> None:
        if self._current_emotion != IDLE and monotonic() - self._last_activity > self.idle_timeout:
            self._publish(IDLE)

    def _publish(self, emotion: str) -> None:
        self._current_emotion = emotion
        msg = String()
        msg.data = emotion
        self._emotion_pub.publish(msg)
        self.get_logger().info("Emotion → %s" % emotion)


def main(args=None):
    rclpy.init(args=args)
    node = EmotionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
