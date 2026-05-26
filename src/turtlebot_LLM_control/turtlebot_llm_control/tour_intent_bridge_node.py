import shlex
import shutil
import subprocess
from typing import List, Optional

from std_msgs.msg import String

import rclpy
from rclpy.node import Node

from turtlebot_llm_control.models import IntentToken


class TourIntentBridgeNode(Node):
    def __init__(self):
        super().__init__("tour_intent_bridge_node")
        self.default_route_label = self.declare_parameter(
            "default_route_label", "saved_route"
        ).value
        self.teleop_process: Optional[subprocess.Popen] = None

        self.create_subscription(String, "/speech/intent", self.handle_intent, 10)
        self.get_logger().info("Tour intent bridge ready. Waiting for intents.")

    def handle_intent(self, msg: String) -> None:
        try:
            token = IntentToken.from_json(msg.data)
        except Exception as exc:
            self.get_logger().warning("Ignoring invalid intent JSON: %s" % exc)
            return

        if token.intent == "start_recording":
            label = token.label or self.default_route_label
            self.launch_teleop_terminal(label)
            return

        if token.intent == "stop_recording":
            self.terminate_teleop_terminal()
            return

    def launch_teleop_terminal(self, route_label: str) -> None:
        if self.teleop_process is not None and self.teleop_process.poll() is None:
            self.get_logger().info("Tour teleop session is already running.")
            return

        teleop_cmd = [
            "ros2",
            "run",
            "turtlebot_llm_control",
            "tour_teleop_session",
            "--ros-args",
            "-p",
            "route_label:=%s" % route_label,
        ]

        terminal_cmd = self.build_terminal_command(teleop_cmd)
        if terminal_cmd is None:
            self.get_logger().warning(
                "No supported terminal emulator was found. "
                "Cannot start interactive tour teleop session from launch."
            )
            return

        self.teleop_process = subprocess.Popen(terminal_cmd)
        self.get_logger().info("Started tour teleop terminal for '%s'." % route_label)

    def terminate_teleop_terminal(self) -> None:
        if self.teleop_process is None:
            return
        if self.teleop_process.poll() is None:
            self.teleop_process.terminate()
            try:
                self.teleop_process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.teleop_process.kill()
        self.teleop_process = None

    def build_terminal_command(self, teleop_cmd: List[str]) -> Optional[List[str]]:
        shell_command = " ".join(shlex.quote(part) for part in teleop_cmd)
        terminal_candidates = [
            ["xterm", "-T", "Tour Teleop", "-e", "bash", "-lc", shell_command],
            ["gnome-terminal", "--", "bash", "-lc", shell_command],
            ["konsole", "-e", "bash", "-lc", shell_command],
            ["xfce4-terminal", "-e", shell_command],
            ["lxterminal", "-e", "bash", "-lc", shell_command],
            ["mate-terminal", "-e", shell_command],
        ]

        for candidate in terminal_candidates:
            if shutil.which(candidate[0]) is not None:
                return candidate
        return None


def main(args=None):
    rclpy.init(args=args)
    node = TourIntentBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.terminate_teleop_terminal()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
