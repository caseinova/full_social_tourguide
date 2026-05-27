import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from std_msgs.msg import String

from . import default_pose
from . import explain_gesture
from . import listening_gesture
from . import nodding_gesture
from . import wave_hello_gesture


GESTURE_MODULES = {
    'default': default_pose,
    'listen': listening_gesture,
    'nod': nodding_gesture,
    'wave_hello': wave_hello_gesture,
    'explain': explain_gesture,
}

GESTURE_DURATIONS = {
    'default': 1.2,
    'listen': 1.0,
    'nod': 2.4,
    'wave_hello': 3.0,
    'explain': 3.0,
}


class SimGestureManager(Node):

    def __init__(self):
        super().__init__('gesture_manager_sim')

        self.declare_parameter('simulate_speech_done', True)
        self.declare_parameter('simulated_speech_wpm', 150.0)
        self.declare_parameter('min_speech_duration_sec', 2.0)
        self.declare_parameter('max_speech_duration_sec', 120.0)
        self.declare_parameter('action_server_wait_sec', 0.2)

        self.left_arm_client = ActionClient(
            self, FollowJointTrajectory, '/left_arm_controller/follow_joint_trajectory')
        self.right_arm_client = ActionClient(
            self, FollowJointTrajectory, '/right_arm_controller/follow_joint_trajectory')
        self.left_hand_client = ActionClient(
            self, FollowJointTrajectory, '/left_hand_controller/follow_joint_trajectory')
        self.right_hand_client = ActionClient(
            self, FollowJointTrajectory, '/right_hand_controller/follow_joint_trajectory')
        self.head_client = ActionClient(
            self, FollowJointTrajectory, '/head_controller/follow_joint_trajectory')

        self.state_file = '/tmp/pepper_hri_previous_gesture.txt'
        self.current_cmd = 'default'
        self.active_until = self.get_clock().now()
        self.speech_done_timer = None

        self.create_subscription(
            String,
            '/pepper/gesture_command',
            self.command_callback,
            10)

        self.create_subscription(
            String,
            '/pepper/spoken_words',
            self.spoken_words_callback,
            10)

        self.done_talking_pub = self.create_publisher(
            String,
            '/done_talking',
            10)

        self.explain_timer = self.create_timer(4.5, self.explain_loop_callback)
        self.get_logger().info(
            'Simulated Pepper gesture manager is ready on /pepper/gesture_command.')

    def command_callback(self, msg):
        command = msg.data.lower().strip()
        self.get_logger().info(f'Received simulated gesture command: {command}')

        if command not in GESTURE_MODULES:
            self.get_logger().warn(f'Unknown gesture command: {command}')
            return

        self.current_cmd = command
        if command != 'explain':
            self.start_gesture(command)

    def explain_loop_callback(self):
        if self.current_cmd == 'explain':
            self.start_gesture('explain')

    def spoken_words_callback(self, msg):
        if not self.get_parameter('simulate_speech_done').value:
            return

        speech_text = msg.data.strip()
        duration = self.estimate_speech_duration(speech_text)
        self.get_logger().info(
            f"Simulating speech for {duration:.1f}s before publishing /done_talking.")

        if self.speech_done_timer is not None:
            self.speech_done_timer.cancel()
            self.destroy_timer(self.speech_done_timer)

        self.speech_done_timer = self.create_timer(duration, self.publish_done_talking)

    def estimate_speech_duration(self, speech_text):
        words = len(speech_text.split())
        words_per_minute = max(1.0, float(self.get_parameter('simulated_speech_wpm').value))
        duration = (words / words_per_minute) * 60.0
        min_duration = float(self.get_parameter('min_speech_duration_sec').value)
        max_duration = float(self.get_parameter('max_speech_duration_sec').value)
        return max(min_duration, min(max_duration, duration))

    def publish_done_talking(self):
        msg = String()
        msg.data = 'done_speaking'
        self.done_talking_pub.publish(msg)
        self.get_logger().info("Published simulated done_speaking on /done_talking.")

        if self.speech_done_timer is not None:
            self.speech_done_timer.cancel()
            self.destroy_timer(self.speech_done_timer)
            self.speech_done_timer = None

    def start_gesture(self, command):
        now = self.get_clock().now()
        if command == 'explain' and now < self.active_until:
            return

        if not self.wait_for_action_servers(command):
            return

        self.get_logger().info(f'Executing simulated Pepper gesture: {command}')
        GESTURE_MODULES[command].execute(self)
        duration_ns = int(GESTURE_DURATIONS[command] * 1e9)
        self.active_until = now + Duration(nanoseconds=duration_ns)

    def wait_for_action_servers(self, command):
        timeout = float(self.get_parameter('action_server_wait_sec').value)
        clients = [self.head_client]

        if command != 'nod':
            clients.extend([
                self.left_arm_client,
                self.right_arm_client,
                self.left_hand_client,
                self.right_hand_client,
            ])

        for client in clients:
            if not client.wait_for_server(timeout_sec=timeout):
                self.get_logger().warn(
                    f"Skipping '{command}' because an action server is not available.")
                return False

        return True


def main(args=None):
    rclpy.init(args=args)
    node = SimGestureManager()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
