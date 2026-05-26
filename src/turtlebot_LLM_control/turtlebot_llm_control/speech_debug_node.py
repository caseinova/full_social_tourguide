from std_msgs.msg import String

import rclpy
from rclpy.node import Node


class SpeechDebugNode(Node):
    def __init__(self):
        super().__init__("speech_debug_node")
        self.publisher = self.create_publisher(String, "/speech/debug", 20)
        self.create_subscription(String, "/speech_to_text/status", self.make_callback("stt_status"), 20)
        self.create_subscription(String, "/speech/text", self.make_callback("heard"), 20)
        self.create_subscription(String, "/speech/intent", self.make_callback("intent"), 20)
        self.create_subscription(String, "/speech/response", self.make_callback("response"), 20)
        self.get_logger().info("Speech debug node ready. Echo /speech/debug for voice-only tracing.")

    def make_callback(self, label: str):
        def callback(msg: String) -> None:
            debug_msg = String()
            debug_msg.data = "[%s] %s" % (label, msg.data)
            self.publisher.publish(debug_msg)

        return callback


def main(args=None):
    rclpy.init(args=args)
    node = SpeechDebugNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
