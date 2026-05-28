import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class NavigationSpeech(Node):
    def __init__(self):
        super().__init__('speech_listener')
        self.subscriber_ = self.create_subscription(String, '/speech/debug',self.debug_callback_,10)
        self.string_publisher_ = self.create_publisher(String, '/speech_content',10)
        self.subscriber_


    
    def debug_callback_(self,msg):
        self.get_logger().info('I heard: "%s"' % msg.data)
        data = msg.data
        if ("[response]" in data):
            self.get_logger().info('Response received')
            self.string_publisher_.publish(String(data=data[10:]))
            return
        return
        

        


def main(args=None):
    rclpy.init(args=args)
    minimal_subscriber = NavigationSpeech()
    rclpy.spin(minimal_subscriber)
    minimal_subscriber.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
    

        
