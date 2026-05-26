import math
import sqlite3

import rclpy
from geometry_msgs.msg import Pose, PoseStamped, PoseWithCovarianceStamped
from opennav_docking_msgs.action import DockRobot
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener


class DockingNode(Node):
    def __init__(self):
        super().__init__('dock_listener')

        self.declare_parameter('database_path', 'docks.db')
        self.declare_parameter('action_name', 'dock_robot')
        self.declare_parameter('dock_type', '')
        self.declare_parameter('max_staging_time', 1000.0)
        self.declare_parameter('navigate_to_staging_pose', True)
        self.declare_parameter('server_timeout_sec', 5.0)
        self.declare_parameter('use_dock_id', False)
        self.declare_parameter('default_dock_id', '')
        self.declare_parameter('current_pose_topic', '/amcl_pose')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')

        self.database_path = self.get_parameter('database_path').value
        self.action_name = self.get_parameter('action_name').value
        self.dock_type = self.get_parameter('dock_type').value
        self.max_staging_time = self.get_parameter('max_staging_time').value
        self.navigate_to_staging_pose = self.get_parameter('navigate_to_staging_pose').value
        self.server_timeout_sec = self.get_parameter('server_timeout_sec').value
        self.use_dock_id = self.get_parameter('use_dock_id').value
        self.default_dock_id = self.get_parameter('default_dock_id').value
        self.current_pose_topic = self.get_parameter('current_pose_topic').value
        self.global_frame = self.get_parameter('global_frame').value
        self.base_frame = self.get_parameter('base_frame').value

        self.current_pose = None
        self.goal_handle = None
        self.result_future = None
        self.dock_client = ActionClient(self, DockRobot, self.action_name)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.con = sqlite3.connect(self.database_path)
        cur = self.con.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS docks (px, py, pz, qx, qy, qz, qw)')
        self.con.commit()

        self.create_subscription(String, '/dock_command', self.dock_command_callback, 10)
        self.create_subscription(String, '/save_dock_command', self.save_dock_command_callback, 10)
        amcl_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(
            PoseWithCovarianceStamped,
            self.current_pose_topic,
            self.current_pose_callback,
            amcl_qos)

        self.get_logger().info(
            'Dock listener ready; using OpenNav docking action "%s"' % self.action_name)

    def current_pose_callback(self, msg):
        self.current_pose = msg.pose.pose

    def save_dock_command_callback(self, msg):
        self.get_logger().info('Received save dock command: "%s"' % msg.data)

        pose = self.current_pose or self.get_current_pose_from_tf()
        if pose is None:
            self.get_logger().warn('No current pose received yet; cannot save dock pose')
            return

        cur = self.con.cursor()
        cur.execute(
            'INSERT INTO docks (px, py, pz, qx, qy, qz, qw) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                pose.position.x,
                pose.position.y,
                pose.position.z,
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
                pose.orientation.w,
            ))
        self.con.commit()

        self.get_logger().info(
            'Saved dock pose to %s at x=%.3f, y=%.3f' %
            (self.database_path, pose.position.x, pose.position.y))

    def get_current_pose_from_tf(self):
        try:
            transform = self.tf_buffer.lookup_transform(
                self.global_frame,
                self.base_frame,
                rclpy.time.Time())
        except TransformException as exc:
            self.get_logger().warn(
                'No pose on %s and TF lookup %s -> %s failed: %s' %
                (self.current_pose_topic, self.global_frame, self.base_frame, exc))
            return None

        pose = Pose()
        pose.position.x = transform.transform.translation.x
        pose.position.y = transform.transform.translation.y
        pose.position.z = transform.transform.translation.z
        pose.orientation = transform.transform.rotation
        self.current_pose = pose
        return pose

    def dock_command_callback(self, msg):
        self.get_logger().info('Received dock command: "%s"' % msg.data)

        if self.result_future is not None and not self.result_future.done():
            self.get_logger().warn('Docking goal already in progress; ignoring new command')
            return

        goal = self.create_docking_goal(msg.data.strip())
        if goal is None:
            return

        if not self.dock_client.wait_for_server(timeout_sec=self.server_timeout_sec):
            self.get_logger().error(
                'OpenNav docking action server "%s" is not available' % self.action_name)
            return

        self.get_logger().info('Sending docking goal to OpenNav')
        send_goal_future = self.dock_client.send_goal_async(
            goal, feedback_callback=self.docking_feedback_callback)
        send_goal_future.add_done_callback(self.docking_goal_response_callback)

    def create_docking_goal(self, command):
        goal = DockRobot.Goal()
        goal.max_staging_time = float(self.max_staging_time)
        goal.navigate_to_staging_pose = bool(self.navigate_to_staging_pose)

        if self.use_dock_id:
            dock_id = command if command and command.lower() not in ('dock', 'nearest') else self.default_dock_id
            if not dock_id:
                self.get_logger().error(
                    'use_dock_id is true, but no dock ID was provided in the command or default_dock_id')
                return None

            goal.use_dock_id = True
            goal.dock_id = dock_id
            self.get_logger().info('Docking by OpenNav dock ID "%s"' % dock_id)
            return goal

        dock_pose = self.get_nearest_dock_pose()
        if dock_pose is None:
            return None

        goal.use_dock_id = False
        goal.dock_pose = dock_pose
        goal.dock_type = self.dock_type
        self.get_logger().info(
            'Docking to nearest stored pose with dock_type "%s"' % self.dock_type)
        return goal

    def docking_goal_response_callback(self, future):
        try:
            self.goal_handle = future.result()
        except Exception as exc:
            self.get_logger().error('Failed to send docking goal: %r' % exc)
            self.goal_handle = None
            self.result_future = None
            return

        if not self.goal_handle.accepted:
            self.get_logger().error('Docking goal was rejected')
            self.goal_handle = None
            self.result_future = None
            return

        self.get_logger().info('Docking goal accepted')
        self.result_future = self.goal_handle.get_result_async()
        self.result_future.add_done_callback(self.docking_result_callback)

    def docking_feedback_callback(self, feedback_msg):
        state_names = {
            DockRobot.Feedback.NONE: 'none',
            DockRobot.Feedback.NAV_TO_STAGING_POSE: 'navigating to staging pose',
            DockRobot.Feedback.INITIAL_PERCEPTION: 'initial perception',
            DockRobot.Feedback.CONTROLLING: 'controlling',
            DockRobot.Feedback.WAIT_FOR_CHARGE: 'waiting for charge',
            DockRobot.Feedback.RETRY: 'retrying',
        }
        feedback = feedback_msg.feedback
        state = state_names.get(feedback.state, 'unknown')
        self.get_logger().info(
            'Docking feedback: %s, retries=%d' % (state, feedback.num_retries))

    def docking_result_callback(self, future):
        try:
            action_result = future.result()
        except Exception as exc:
            self.get_logger().error('Failed to get docking result: %r' % exc)
            self.goal_handle = None
            self.result_future = None
            return

        result = action_result.result

        if result.success:
            self.get_logger().info(
                'Docking succeeded after %d retries' % result.num_retries)
        else:
            self.get_logger().error(
                'Docking failed with error_code=%d after %d retries' %
                (result.error_code, result.num_retries))

        self.goal_handle = None
        self.result_future = None

    def get_nearest_dock_pose(self):
        cur = self.con.cursor()
        docks = cur.execute('SELECT px, py, pz, qx, qy, qz, qw FROM docks').fetchall()

        if not docks:
            self.get_logger().warn('No dock poses found in %s' % self.database_path)
            return None

        if self.current_pose is None:
            self.get_logger().warn('No current pose received yet; using first dock pose')
            return self.row_to_pose(docks[0])

        nearest_dock = min(docks, key=self.distance_to_current_pose)
        return self.row_to_pose(nearest_dock)

    def distance_to_current_pose(self, dock):
        dx = self.current_pose.position.x - dock[0]
        dy = self.current_pose.position.y - dock[1]
        return math.hypot(dx, dy)

    def row_to_pose(self, row):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = row[0]
        pose.pose.position.y = row[1]
        pose.pose.position.z = row[2]
        pose.pose.orientation.x = row[3]
        pose.pose.orientation.y = row[4]
        pose.pose.orientation.z = row[5]
        pose.pose.orientation.w = row[6]
        return pose


def main(args=None):
    rclpy.init(args=args)
    docking_node = DockingNode()
    rclpy.spin(docking_node)
    docking_node.con.close()
    docking_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
