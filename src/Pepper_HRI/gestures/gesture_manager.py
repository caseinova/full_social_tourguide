import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


GESTURES = {
    'default': {
        'HeadYaw': [0.0],
        'HeadPitch': [0.0],
        'LShoulderPitch': [1.35],
        'LShoulderRoll': [0.15],
        'LElbowYaw': [-1.2],
        'LElbowRoll': [-0.5],
        'LWristYaw': [0.0],
        'LHand': [0.2],
        'RShoulderPitch': [1.35],
        'RShoulderRoll': [-0.15],
        'RElbowYaw': [1.2],
        'RElbowRoll': [0.5],
        'RWristYaw': [0.0],
        'RHand': [0.2],
    },
    'listen': {
        'HeadYaw': [0.25],
        'HeadPitch': [0.25],
        'LShoulderPitch': [1.25],
        'LShoulderRoll': [0.1],
        'LElbowYaw': [-0.8],
        'LElbowRoll': [-0.8],
        'LHand': [0.4],
        'RShoulderPitch': [0.45],
        'RShoulderRoll': [-0.35],
        'RElbowYaw': [1.35],
        'RElbowRoll': [1.2],
        'RWristYaw': [-0.3],
        'RHand': [0.6],
    },
    'nod': {
        'HeadYaw': [0.0, 0.0, 0.0, 0.0],
        'HeadPitch': [0.25, -0.1, 0.25, 0.0],
    },
    'wave_hello': {
        'HeadYaw': [0.0],
        'HeadPitch': [-0.05],
        'RShoulderPitch': [0.65, 0.65, 0.65, 0.65, 1.25],
        'RShoulderRoll': [-0.25, -0.25, -0.25, -0.25, -0.15],
        'RElbowYaw': [1.25, 1.25, 1.25, 1.25, 1.2],
        'RElbowRoll': [1.2, 1.2, 1.2, 1.2, 0.5],
        'RWristYaw': [-0.7, 0.7, -0.7, 0.7, 0.0],
        'RHand': [1.0, 1.0, 1.0, 1.0, 0.2],
    },
    'explain': {
        'HeadYaw': [0.0],
        'HeadPitch': [0.0],
        'LShoulderPitch': [0.958, 0.958, 1.274],
        'LShoulderRoll': [0.151, 0.151, 0.067],
        'LElbowYaw': [-0.981, -0.981, -0.485],
        'LElbowRoll': [-0.790, -0.790, -0.706],
        'LWristYaw': [-1.824, -1.824, -0.424],
        'LHand': [0.0, 1.0, 0.0],
        'RShoulderPitch': [0.958, 0.958, 1.274],
        'RShoulderRoll': [0.151, 0.151, 0.067],
        'RElbowYaw': [0.981, 0.981, 0.485],
        'RElbowRoll': [0.790, 0.790, 0.706],
        'RWristYaw': [1.824, 1.824, 0.424],
        'RHand': [0.0, 1.0, 0.0],
    },
}

GESTURE_DURATIONS = {
    'default': [1.2],
    'listen': [1.0],
    'nod': [0.5, 1.0, 1.5, 2.0],
    'wave_hello': [0.6, 1.0, 1.4, 1.8, 2.4],
    'explain': [1.0, 2.0, 3.0],
}


class GestureManager(Node):

    def __init__(self):
        super().__init__('gesture_manager')

        self.declare_parameter('pepper_ip', '192.168.1.100')
        self.declare_parameter('naoqi_port', 9559)
        self.declare_parameter('enable_stiffness', True)

        self.motion = None
        self.posture = None
        self.session = None
        self.last_connection_error = None
        self.motion_lock = threading.Lock()
        self.current_cmd = 'default'
        self.active_thread = None

        self.connect_to_pepper()

        self.create_subscription(
            String,
            '/pepper/gesture_command',
            self.command_callback,
            10)

        self.explain_timer = self.create_timer(4.5, self.explain_loop_callback)
        self.get_logger().info("NAOqi gesture manager is ready.")

    def connect_to_pepper(self):
        try:
            import qi

            pepper_ip = self.get_parameter('pepper_ip').value
            naoqi_port = int(self.get_parameter('naoqi_port').value)

            session = qi.Session()
            session.connect(f'tcp://{pepper_ip}:{naoqi_port}')
            motion = session.service('ALMotion')
            posture = session.service('ALRobotPosture')

            if self.get_parameter('enable_stiffness').value:
                motion.wakeUp()

            self.session = session
            self.motion = motion
            self.posture = posture
            self.last_connection_error = None

            self.get_logger().info(f"Connected to Pepper NAOqi at {pepper_ip}:{naoqi_port}")
            return True
        except Exception as exc:
            self.motion = None
            self.posture = None
            self.session = None
            self.last_connection_error = str(exc)
            self.get_logger().error(f"Could not connect to Pepper NAOqi: {exc}")
            return False

    def command_callback(self, msg):
        command = msg.data.lower().strip()
        if command not in GESTURES:
            self.get_logger().warn(f"Unknown gesture command: {command}")
            return

        self.current_cmd = command
        if command != 'explain':
            self.start_gesture(command)

    def explain_loop_callback(self):
        if self.current_cmd == 'explain':
            self.start_gesture('explain')

    def start_gesture(self, command):
        if self.motion is None:
            self.get_logger().warn("ALMotion is not connected; retrying NAOqi connection.")
            if not self.connect_to_pepper():
                self.get_logger().warn(
                    f"Skipping gesture because ALMotion is not connected: {self.last_connection_error}")
                return

        if self.active_thread and self.active_thread.is_alive():
            return

        self.active_thread = threading.Thread(
            target=self.execute_gesture,
            args=(command,),
            daemon=True)
        self.active_thread.start()

    def execute_gesture(self, command):
        gesture = GESTURES[command]
        duration = GESTURE_DURATIONS[command]

        names = list(gesture.keys())
        angle_lists = [gesture[name] for name in names]
        time_lists = [duration if len(angles) > 1 else [duration[-1]] for angles in angle_lists]

        try:
            with self.motion_lock:
                self.get_logger().info(f"Executing Pepper gesture: {command}")
                self.motion.angleInterpolation(names, angle_lists, time_lists, True)
        except Exception as exc:
            self.get_logger().error(f"Failed to execute gesture '{command}': {exc}")


def main(args=None):
    rclpy.init(args=args)
    node = GestureManager()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
