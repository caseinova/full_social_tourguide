import os
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint

def create_goal(joint_names, waypoints):
    """Converts waypoint lists into a FollowJointTrajectory Goal."""
    goal_msg = FollowJointTrajectory.Goal()
    goal_msg.trajectory.joint_names = joint_names

    for wp in waypoints:
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in wp[:-1]] # Ensure floats
        total_time = float(wp[-1])
        point.time_from_start.sec = int(total_time)
        point.time_from_start.nanosec = int((total_time % 1) * 1e9)
        goal_msg.trajectory.points.append(point)
    return goal_msg

def execute(node):
    """Called by GestureManager. 'node' is the manager instance."""
    node.get_logger().info('Executing Nodding gesture...')

    # 1. Define Motion
    head_joints = ['HeadYaw', 'HeadPitch']
    # Format: [Yaw, Pitch, Time]
    head_wps = [
        [0.0, 0.25, 0.6],   # Chin down
        [0.0, -0.1, 1.2],   # Chin up
        [0.0, 0.25, 1.8],   # Chin down
        [0.0, 0.0, 2.4],    # Reset to neutral
    ]

    # 2. Build and Send
    head_goal = create_goal(head_joints, head_wps)
    
    # We return the future so the manager could wait for it if needed
    future = node.head_client.send_goal_async(head_goal)
    
    # 3. Update State File
    try:
        with open(node.state_file, 'w') as f:
            f.write("nodding_gesture")
    except Exception as e:
        node.get_logger().error(f"Failed to update state file: {e}")
        
    return future










""" import os
import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint

class PepperWaveHand(Node):
    def __init__(self):
        super().__init__('pepper_explain')
        # Initialize all your clients here
        self.left_arm_client = ActionClient(self, FollowJointTrajectory, '/left_arm_controller/follow_joint_trajectory')
        self.right_arm_client = ActionClient(self, FollowJointTrajectory, '/right_arm_controller/follow_joint_trajectory')

        self.right_hand_client = ActionClient(self, FollowJointTrajectory, '/right_hand_controller/follow_joint_trajectory')
        self.left_hand_client = ActionClient(self, FollowJointTrajectory, '/left_hand_controller/follow_joint_trajectory')
        
        self.head_client = ActionClient(self, FollowJointTrajectory, '/head_controller/follow_joint_trajectory')

    # loop through waypoints and turn them into motor outputs
    def create_goal(self, joint_names, waypoints):
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = joint_names

        for wp in waypoints:
            point = JointTrajectoryPoint()
            point.positions = wp[:-1]  # All values except the last one
            
            total_time = wp[-1]        # The last value is the time
            point.time_from_start.sec = int(total_time)
            point.time_from_start.nanosec = int((total_time % 1) * 1e9)
            
            goal_msg.trajectory.points.append(point)
        return goal_msg

    # Function to define the parameters for each joint
    def explaining_motions(self):

        head_joints = ['HeadYaw', 'HeadPitch']

        head_wps = [
            [0.0, -0.1, 0.5],
            [0.0, -0.3, 1.0],
            [0.0, -0.1, 1.5],
            [0.0, -0.3, 2.0],
        ]

        # 3. Create goals using the helper
        head_goal = self.create_goal(head_joints, head_wps)

        # 4. Fire them off simultaneously
        self.get_logger().info('Executing head gesture...')

        self.head_client.send_goal_async(head_goal)
        return self.head_client.send_goal_async(head_goal)


def main(args=None):
    rclpy.init(args=args)
    node = PepperWaveHand()
    future = node.explaining_motions()
    rclpy.spin_until_future_complete(node, future)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
 """