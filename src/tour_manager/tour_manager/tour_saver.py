import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from std_msgs.msg import String


class TourSaver(Node):
    def __init__(self):
        super().__init__('tour_saver')
        self.get_logger().info('Initializing tour saver')
        self.publisher_ = self.create_publisher(PoseStamped, 'save_tour', 10)
        self.subscriber_ = self.create_subscription(String, 'save_tour_command', self.save_tour_callback, 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.current_pose_ = PoseStamped()
        self.current_pose_.header.frame_id = "map"
    def save_tour_callback(self, msg):
        try:
            t = self.tf_buffer.lookup_transform(
                "map",
                "base_link",
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0))
            print(t)
            self.current_pose_.pose.position.x = t.transform.translation.x
            self.current_pose_.pose.position.y = t.transform.translation.y
            self.current_pose_.pose.position.z = t.transform.translation.z
            self.current_pose_.pose.orientation.x = t.transform.rotation.x
            self.current_pose_.pose.orientation.y = t.transform.rotation.y
            self.current_pose_.pose.orientation.z = t.transform.rotation.z
            self.current_pose_.pose.orientation.w = t.transform.rotation.w
            self.publisher_.publish(self.current_pose_)
        except TransformException as ex:
            self.get_logger().info(
                f'Could not transform map to base_link: {ex}')
            return



def main(args=None):
    rclpy.init(args=args)
    tour_saver = TourSaver()
    rclpy.spin(tour_saver)

    # while(True):
    #     x=input()
    #     if x=='x':
    #         break
        # pose = PoseStamped()
    #     try:
    #         t = tour_saver.tf_buffer.lookup_transform(
    #             "base_link",
    #             "map",
    #             rclpy.time.Time())
    #         print(t)
    #         tour_saver.publisher_.publish(pose)
    #     except TransformException as ex:
    #         tour_saver.get_logger().info(
    #             f'Could not transform map to base_link: {ex}')
    #         break
            
    tour_saver.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()