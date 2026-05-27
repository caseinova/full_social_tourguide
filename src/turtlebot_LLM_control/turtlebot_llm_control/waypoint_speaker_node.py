import json
import re
import shutil
import subprocess
import threading

import rclpy
from rclpy.node import Node
from social_robot_interfaces.srv import Description
from std_msgs.msg import String


def _run_tts(text: str) -> None:
    for cmd in (["spd-say", "-w", text], ["espeak", text], ["say", text]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=False)
            return
    print(f"[waypoint_speaker] No TTS available. Would say: {text}")


class WaypointSpeakerNode(Node):
    def __init__(self):
        super().__init__("waypoint_speaker_node")
        self._speaking_lock = threading.Lock()

        self._talk_sub = self.create_subscription(
            String, "/talk_command", self._on_talk_command, 10
        )
        self._description_client = self.create_client(
            Description, "retrieve_description"
        )

        self._done_talking_pub = self.create_publisher(String, "/done_talking", 10)
        self._done_speaking_pub = self.create_publisher(String, "/done_speaking", 10)
        self._emotion_pub = self.create_publisher(String, "/robot/emotion", 10)
        self._gesture_pub = self.create_publisher(String, "/pepper/gesture_command", 10)

        self.get_logger().info(
            "Waypoint speaker ready. Waiting for retrieve_description service."
        )

    # ── main handler ───────────────────────────────────────────────────────

    def _on_talk_command(self, msg: String) -> None:
        numbers = re.findall(r"\d+", msg.data)
        if not numbers:
            self.get_logger().warning(f"No integer in talk_command: {msg.data!r}")
            self._signal_done()
            return

        published_index = int(numbers[-1])
        self._publish_emotion(
            "informative",
            f"retrieving description for waypoint {published_index}",
            0.75,
        )

        if not self._description_client.service_is_ready():
            self.get_logger().warning(
                "retrieve_description service is not available; using fallback."
            )
            self._publish_emotion(
                "puzzled",
                f"retrieve_description unavailable for waypoint {published_index}",
                0.45,
            )
            self._speak_text(f"Arrived at waypoint {published_index}.")
            return

        request = Description.Request()
        request.idx = published_index
        future = self._description_client.call_async(request)
        future.add_done_callback(
            lambda done_future: self._on_description_response(
                done_future, published_index
            )
        )

    def _on_description_response(self, future, waypoint_index: int) -> None:
        try:
            response = future.result()
        except Exception as exc:
            self.get_logger().warning(
                f"retrieve_description request failed for waypoint "
                f"{waypoint_index}: {exc}"
            )
            response = None

        description_msg = getattr(response, "description", None)
        description = getattr(description_msg, "data", description_msg) or ""
        description = str(description).strip()

        if description:
            text = description
        else:
            text = f"Arrived at waypoint {waypoint_index}."
            self.get_logger().info(
                f"No description for index {waypoint_index}, using fallback."
            )
            self._publish_emotion(
                "puzzled",
                f"no description for waypoint {waypoint_index}",
                0.45,
            )

        self._speak_text(text)

    def _speak_text(self, text: str) -> None:
        self.get_logger().info(
            f"Speaking: '{text[:80]}{'...' if len(text) > 80 else ''}'"
        )

        def _speak_then_signal():
            self._gesture_pub.publish(String(data="explain"))
            with self._speaking_lock:
                _run_tts(text)
            self._publish_emotion("satisfied", "finished explanation", 0.55)
            self._signal_done()

        threading.Thread(target=_speak_then_signal, daemon=True).start()

    # ── signalling ─────────────────────────────────────────────────────────

    def _signal_done(self) -> None:
        done_msg = String(data="done_speaking")
        self._done_talking_pub.publish(done_msg)
        self._done_speaking_pub.publish(done_msg)

    def _publish_emotion(self, emotion: str, context: str, intensity: float) -> None:
        payload = json.dumps(
            {"emotion": emotion, "context": context, "intensity": intensity}
        )
        self._emotion_pub.publish(String(data=payload))


def main(args=None):
    rclpy.init(args=args)
    node = WaypointSpeakerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
