from geometry_msgs.msg import PoseWithCovarianceStamped

import rclpy
from rclpy.node import Node


class SimInitialPoseNode(Node):
    def __init__(self):
        super().__init__("sim_initial_pose_node")
        self.publisher = self.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
        self.publish_count = 0
        self.max_publishes = 5
        self.target_x = float(self.declare_parameter("x", -2.0).value)
        self.target_y = float(self.declare_parameter("y", -0.5).value)
        self.target_yaw = float(self.declare_parameter("yaw", 0.0).value)
        self.timer = self.create_timer(2.0, self.publish_initial_pose)

    def publish_initial_pose(self) -> None:
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = self.target_x
        msg.pose.pose.position.y = self.target_y
        msg.pose.pose.orientation.w = 1.0
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.0685
        self.publisher.publish(msg)
        self.publish_count += 1
        self.get_logger().info(
            "Published initial pose x=%.2f y=%.2f (%d/%d)"
            % (self.target_x, self.target_y, self.publish_count, self.max_publishes)
        )
        if self.publish_count >= self.max_publishes:
            self.timer.cancel()


def main(args=None):
    rclpy.init(args=args)
    node = SimInitialPoseNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
