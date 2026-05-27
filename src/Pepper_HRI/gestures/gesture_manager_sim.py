import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String

from . import default_pose
from . import explain_gesture
from . import listening_gesture
from . import nodding_gesture
from . import wave_hello_gesture


class SimGestureManager(Node):

    def __init__(self):
        super().__init__('gesture_manager_sim')

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

        self.create_subscription(
            String,
            '/pepper/gesture_command',
            self.command_callback,
            10)

        self.explain_timer = self.create_timer(4.5, self.explain_loop_callback)
        self.get_logger().info('Simulated Pepper gesture manager is ready.')

    def command_callback(self, msg):
        command = msg.data.lower().strip()
        self.get_logger().info(f'Received simulated gesture command: {command}')

        if command not in ['default', 'listen', 'nod', 'wave_hello', 'explain']:
            self.get_logger().warn(f'Unknown gesture command: {command}')
            return

        self.current_cmd = command
        if command != 'explain':
            self.execute_gesture(command)

    def explain_loop_callback(self):
        if self.current_cmd == 'explain':
            self.execute_gesture('explain')

    def execute_gesture(self, command):
        if command == 'default':
            default_pose.execute(self)
        elif command == 'listen':
            listening_gesture.execute(self)
        elif command == 'nod':
            nodding_gesture.execute(self)
        elif command == 'wave_hello':
            wave_hello_gesture.execute(self)
        elif command == 'explain':
            explain_gesture.execute(self)


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
