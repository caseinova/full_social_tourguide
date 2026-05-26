import rclpy
from rclpy.node import Node
from rclpy.task import Future
from geometry_msgs.msg import  PoseStamped
from std_msgs.msg import String
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from social_robot_interfaces.msg import TspCommand
from social_robot_interfaces.srv import Tours
from json import dumps, loads

LOCATION_DICT = {'pillar': [1.0,1.0]}

class NavigationSpeech(Node):
    def __init__(self):
        super().__init__('speech_listener')
        self.subscriber_ = self.create_subscription(String, '/speech/intent',self.intent_callback_,10)
        self.start_tour_ = self.create_publisher(String, '/tour_command',10)
        self.tsp_command_ = self.create_publisher(TspCommand, '/tsp_command', 10)
        self.dock_command_ = self.create_publisher(String, '/dock_command', 10)
        self.nav = BasicNavigator()
        self.subscriber_
        self.current_goal = PoseStamped()

        self.cli = self.create_client(Tours, 'tour_retrieve')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        self.req = Tours.Request()
        self.future : Future = None
    
    def request_waypoint(self):
        self.req.idx = 0
        self.future = self.cli.call_async(self.req)
        self.future.add_done_callback(self.go_to_waypoint)

    
    def intent_callback_(self,msg):
        self.get_logger().info('I heard: "%s"' % msg.data)
        data = loads(msg.data)
        if (data["intent"]=="navigate"):
            self.get_logger().info('Intent is not navigate, ignoring')
            self.get_logger().info('Requesting the location of the goal')
            try:
                self.idx = (int(data['location'][-1]))
            except:
                self.get_logger().info('Could not parse the location, ignoring')
                return
            self.request_waypoint()
            return
        elif (data["intent"]=="start_tour"):
            self.get_logger().info('Starting tour')
            self.start_tour_.publish(String(data="start"))
        elif (data["intent"]=="tsp"):
            try:
                waypoints = [int(waypoint) for waypoint in data["waypoints"]]
            except (KeyError, TypeError, ValueError):
                self.get_logger().info('Could not parse TSP waypoints, ignoring')
                return

            self.get_logger().info('Starting TSP tour')
            self.tsp_command_.publish(TspCommand(waypoints=waypoints))
        elif (data["intent"]=="dock"):
            self.get_logger().info('Docking')
            self.dock_command_.publish(String(data="dock"))
        elif (data['intent']=='stop_navigation'):
            self.get_logger().info('Stopping navigation')
            self.nav.cancelTask()

        
    
    def go_to_waypoint(self, future):
        response = future.result()
        self.get_logger().info('Got the location of the goal')
        goal = response.tour[self.idx]
        self.get_logger().info('Trying to go to goal')
        self.nav.goToPose(goal)
        


def main(args=None):
    rclpy.init(args=args)
    minimal_subscriber = NavigationSpeech()
    rclpy.spin(minimal_subscriber)
    minimal_subscriber.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
    

        
