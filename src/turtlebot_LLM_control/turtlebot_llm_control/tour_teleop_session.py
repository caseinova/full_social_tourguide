import select
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Dict

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String


KEY_BINDINGS: Dict[str, tuple[float, float]] = {
    "w": (0.18, 0.0),
    "s": (-0.18, 0.0),
    "a": (0.0, 0.9),
    "d": (0.0, -0.9),
    "q": (0.0, 1.2),
    "e": (0.0, -1.2),
    "x": (0.0, 0.0),
    " ": (0.0, 0.0),
}


@dataclass
class KeyEvent:
    key: str


class TourTeleopSession(Node):
    def __init__(self):
        super().__init__("tour_teleop_session")
        self.route_label = self.declare_parameter("route_label", "saved_route").value
        self.cmd_vel_publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        self.save_tour_publisher = self.create_publisher(String, "/save_tour_command", 10)
        self.line_buffer = []
        self.get_logger().info(
            "Tour teleop session started for route '%s'. Press r to save, esc to exit."
            % self.route_label
        )

    def run(self) -> None:
        stdin_fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(stdin_fd)
        try:
            tty.setraw(stdin_fd)
            self.print_help()
            while rclpy.ok():
                if self._key_ready():
                    event = self.read_key(stdin_fd)
                    if event is None:
                        continue
                    if event.key == "\x1b":
                        self.get_logger().info("Escape pressed. Ending teleop session.")
                        break
                    if len(event.key) == 1 and event.key.lower() == "r":
                        self.publish_save_command()
                        continue
                    if event.key in ("\r", "\n"):
                        continue
                    if len(event.key) == 1 and event.key.isprintable():
                        linear, angular = KEY_BINDINGS.get(event.key.lower(), (0.0, 0.0))
                        self.publish_cmd(linear, angular)
                        continue
                    linear, angular = KEY_BINDINGS.get(event.key.lower(), (0.0, 0.0))
                    self.publish_cmd(linear, angular)
                    continue

                rclpy.spin_once(self, timeout_sec=0.05)
        finally:
            self.publish_cmd(0.0, 0.0)
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)

    def consume_line(self) -> str:
        line = "".join(self.line_buffer).strip().lower()
        self.line_buffer = []
        return line

    def handle_line(self, line: str) -> None:
        if not line:
            return
        if line == "r":
            self.publish_save_command()
            return
        self.get_logger().info("Ignoring teleop command line: %s" % line)

    def read_key(self, stdin_fd: int) -> KeyEvent | None:
        try:
            char = sys.stdin.read(1)
        except (KeyboardInterrupt, EOFError):
            return KeyEvent("\x1b")
        if not char:
            return None
        if char == "\x1b":
            return KeyEvent(char)
        return KeyEvent(char)

    def _key_ready(self) -> bool:
        readable, _, _ = select.select([sys.stdin], [], [], 0.0)
        return bool(readable)

    def publish_cmd(self, linear_x: float, angular_z: float) -> None:
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_vel_publisher.publish(msg)

    def publish_save_command(self) -> None:
        msg = String()
        msg.data = self.route_label
        self.save_tour_publisher.publish(msg)
        self.get_logger().info("Published /save_tour_command for '%s'." % self.route_label)

    def print_help(self) -> None:
        print("")
        print("Tour teleop controls:")
        print("  w/s : forward/back")
        print("  a/d : rotate left/right")
        print("  q/e : spin faster left/right")
        print("  x or space : stop")
        print("  r : save current tour to /save_tour_command")
        print("  esc : exit teleop and return to autonomy")
        print("")


def main(args=None):
    rclpy.init(args=args)
    node = TourTeleopSession()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
