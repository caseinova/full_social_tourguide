import json
import math
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from typing import List, Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from std_msgs.msg import String


class TourRecordingManager(Node):
    def __init__(self):
        super().__init__("tour_recording_manager")
        self.active = False
        self.route_label = ""
        self.route_summary = ""
        self.waypoints: List[dict] = []
        self.last_pose: Optional[tuple[float, float, float]] = None
        self.last_sample_time = self.get_clock().now()
        self.teleop_process: Optional[subprocess.Popen] = None

        self.record_subscription = self.create_subscription(
            String, "/route/record", self.handle_record_command, 10
        )
        self.save_subscription = self.create_subscription(
            String, "/save_tour_command", self.handle_save_command, 10
        )
        self.pose_subscription = self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self.handle_pose, 10
        )
        self.route_data_publisher = self.create_publisher(String, "/route/data", 10)
        self.route_record_publisher = self.create_publisher(String, "/route/record", 10)
        self.status_publisher = self.create_publisher(String, "/tour/status", 10)
        self.manual_override_publisher = self.create_publisher(String, "/manual_override/control", 10)
        self.timer = self.create_timer(0.5, self.monitor_teleop_process)
        self.get_logger().info("Tour recording manager ready.")

    def handle_record_command(self, msg: String) -> None:
        command = msg.data.strip().lower()
        if command.startswith("start:"):
            route_label = msg.data.split(":", 1)[1].strip() or "saved_route"
            self.start_recording(route_label)
            return

        if command == "stop":
            self.stop_recording("Recording stopped.")
            return

        self.publish_status("Unknown route recording command: %s" % msg.data)

    def handle_save_command(self, msg: String) -> None:
        if not self.active:
            self.publish_status("Ignoring save command because recording is not active.")
            return

        requested_label = msg.data.strip() or self.route_label or "saved_route"
        self.publish_route_data(requested_label)

    def handle_pose(self, msg: PoseWithCovarianceStamped) -> None:
        if not self.active:
            return

        now = self.get_clock().now()
        if (now - self.last_sample_time).nanoseconds < int(0.5 * 1e9):
            return

        pose = msg.pose.pose
        x = float(pose.position.x)
        y = float(pose.position.y)
        yaw = self.quaternion_to_yaw(
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        )

        if self.last_pose is not None:
            last_x, last_y, last_yaw = self.last_pose
            distance = math.hypot(x - last_x, y - last_y)
            angle_delta = abs(yaw - last_yaw)
            if distance < 0.05 and angle_delta < 0.1:
                return

        self.waypoints.append(
            {
                "x": round(x, 3),
                "y": round(y, 3),
                "yaw": round(yaw, 3),
            }
        )
        self.last_pose = (x, y, yaw)
        self.last_sample_time = now
        self.publish_status(
            "Recorded waypoint %d for %s." % (len(self.waypoints), self.route_label)
        )

    def start_recording(self, route_label: str) -> None:
        self.active = True
        self.route_label = route_label
        self.route_summary = ""
        self.waypoints = []
        self.last_pose = None
        self.last_sample_time = self.get_clock().now()
        self.publish_manual_override("on")
        self.publish_status("Recording started for %s." % self.route_label)
        self.launch_teleop_terminal()

    def stop_recording(self, reason: str) -> None:
        self.active = False
        self.publish_manual_override("off")
        stop_msg = String()
        stop_msg.data = "stop"
        self.route_record_publisher.publish(stop_msg)
        self.terminate_teleop_terminal()
        self.publish_status(reason)

    def publish_route_data(self, route_label: str) -> None:
        if not self.waypoints:
            self.publish_status("No waypoints recorded yet for %s." % route_label)
            return

        payload = {
            "label": route_label,
            "waypoints": self.waypoints,
            "summary": self.route_summary or "Recorded tour route",
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.route_data_publisher.publish(msg)
        self.publish_status(
            "Published route data for %s with %d waypoints." % (
                route_label,
                len(self.waypoints),
            )
        )

    def publish_status(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.status_publisher.publish(msg)
        self.get_logger().info(text)

    def publish_manual_override(self, command: str) -> None:
        msg = String()
        msg.data = command
        self.manual_override_publisher.publish(msg)

    def monitor_teleop_process(self) -> None:
        if self.teleop_process is None:
            return
        if self.teleop_process.poll() is not None:
            self.publish_status("Teleop terminal closed.")
            self.teleop_process = None
            if self.active:
                self.stop_recording("Teleop closed. Recording ended.")

    def launch_teleop_terminal(self) -> None:
        if self.teleop_process is not None and self.teleop_process.poll() is None:
            return

        teleop_cmd = [
            "ros2",
            "run",
            "turtlebot_llm_control",
            "tour_teleop_session",
            "--ros-args",
            "-p",
            "route_label:=%s" % self.route_label,
        ]

        terminal_cmd = self.build_terminal_command(teleop_cmd)
        if terminal_cmd is None:
            self.publish_status(
                "No supported terminal emulator was found. Running teleop in the current process."
            )
            self.teleop_process = subprocess.Popen(teleop_cmd)
            return

        self.teleop_process = subprocess.Popen(terminal_cmd)
        self.publish_status("Started teleop terminal for %s." % self.route_label)

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

    def quaternion_to_yaw(self, x: float, y: float, z: float, w: float) -> float:
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)


def main(args=None):
    rclpy.init(args=args)
    node = TourRecordingManager()
    try:
        rclpy.spin(node)
    finally:
        node.terminate_teleop_terminal()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
