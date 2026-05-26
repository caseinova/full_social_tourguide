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
        head_joints = ['HeadYaw', 'HeadPitch']

        head_wps = [
            [1.0, 0.4, 0.5],
        ]


        L_arm_joints = ['LShoulderPitch', 'LShoulderRoll', 'LElbowYaw', 'LElbowRoll', 'LWristYaw']
        R_arm_joints = ['RShoulderPitch', 'RShoulderRoll', 'RElbowYaw', 'RElbowRoll', 'RWristYaw']

        L_arm_wps = [
            [1.3, 0.07, -0.5, -0.7, -0.42, 0.0],
        ]

        R_arm_wps = [
            [0.169, -1.0, 1.184, 1.562, -0.522, 0.5],
            [0.169, 0.059, 1.184, 1.562, -0.522, 1.0],
        ]

        r_hand_joints = [
            'RFinger11',
            'RFinger12',
            'RFinger13',
            'RFinger21',
            'RFinger22',
            'RFinger23',
            'RFinger31',
            'RFinger32',
            'RFinger33',
            'RFinger41',
            'RFinger42',
            'RFinger43',
            'RThumb1',
            'RThumb2'
            
        ]


        l_hand_joints = [
            'LFinger11',
            'LFinger12',
            'LFinger13',
            'LFinger21',
            'LFinger22',
            'LFinger23',
            'LFinger31',
            'LFinger32',
            'LFinger33',
            'LFinger41',
            'LFinger42',
            'LFinger43',
            'LThumb1',
            'LThumb2'
            
        ]
        # 11 12 13      21 22 23        31 32 33        41 42 43        T1 T2
        l_hand_wps = [
            [-0.0, -0.0,-0.0,    -0.25, -0.25, -0.25,    -0.5, -0.5, -0.5,    -0.75, -0.75, -0.75,   0.5, 0.5,   0.5],
        ]

        r_hand_wps = [
            [ 1.0, 0.9, 0.9,     0.9, 0.8, 0.8,    0.8, 0.7, 0.7,    0.7, 0.6, 0.6,    0.5, 0.25,   0.5],
        ]

        # 3. Create goals using the helper
        head_goal = create_goal(head_joints, head_wps)

        L_arm_goal = create_goal(L_arm_joints, L_arm_wps)
        R_arm_goal = create_goal(R_arm_joints, R_arm_wps)

        l_hand_goal = create_goal(l_hand_joints, l_hand_wps)
        r_hand_goal = create_goal(r_hand_joints, r_hand_wps)

        # 4. Fire them off simultaneously
        node.get_logger().info('Executing synchronized gesture...')


        # idk why exactly, but putting them in a list allows me to know when they start and end?
        future = []
        
        future.append(node.head_client.send_goal_async(head_goal))

        future.append(node.left_arm_client.send_goal_async(L_arm_goal))
        future.append(node.right_arm_client.send_goal_async(R_arm_goal))

        future.append(node.right_hand_client.send_goal_async(r_hand_goal))
        future.append(node.left_hand_client.send_goal_async(l_hand_goal))
    
        # 3. Update State File
        try:
            with open(node.state_file, 'w') as f:
                f.write("listening_gesture")
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

        self.state_file = "/home/hayden/ros_ws/src/pepper_ign_moveit2/pepper_robot_description/launch/previous_gesture.txt"
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)


    # Function to process the waypoints
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
            [1.0, 0.4, 0.5],
        ]


        L_arm_joints = ['LShoulderPitch', 'LShoulderRoll', 'LElbowYaw', 'LElbowRoll', 'LWristYaw']
        R_arm_joints = ['RShoulderPitch', 'RShoulderRoll', 'RElbowYaw', 'RElbowRoll', 'RWristYaw']

        L_arm_wps = [
            [1.3, 0.07, -0.5, -0.7, -0.42, 0.0],
        ]

        R_arm_wps = [
            [0.169, -1.0, 1.184, 1.562, -0.522, 0.4],
            [0.169, 0.059, 1.184, 1.562, -0.522, 0.8],
        ]

        r_hand_joints = [
            'RFinger11',
            'RFinger12',
            'RFinger13',
            'RFinger21',
            'RFinger22',
            'RFinger23',
            'RFinger31',
            'RFinger32',
            'RFinger33',
            'RFinger41',
            'RFinger42',
            'RFinger43',
            'RThumb1',
            'RThumb2'
            
        ]


        l_hand_joints = [
            'LFinger11',
            'LFinger12',
            'LFinger13',
            'LFinger21',
            'LFinger22',
            'LFinger23',
            'LFinger31',
            'LFinger32',
            'LFinger33',
            'LFinger41',
            'LFinger42',
            'LFinger43',
            'LThumb1',
            'LThumb2'
            
        ]
        # 11 12 13      21 22 23        31 32 33        41 42 43        T1 T2
        l_hand_wps = [
            [-0.0, -0.0,-0.0,    -0.25, -0.25, -0.25,    -0.5, -0.5, -0.5,    -0.75, -0.75, -0.75,   0.5, 0.5,   0.5],
        ]

        r_hand_wps = [
            [ 1.0, 0.9, 0.9,     0.9, 0.8, 0.8,    0.8, 0.7, 0.7,    0.7, 0.6, 0.6,    0.5, 0.25,   0.5],
        ]

        # 3. Create goals using the helper
        head_goal = self.create_goal(head_joints, head_wps)

        L_arm_goal = self.create_goal(L_arm_joints, L_arm_wps)
        R_arm_goal = self.create_goal(R_arm_joints, R_arm_wps)

        l_hand_goal = self.create_goal(l_hand_joints, l_hand_wps)
        r_hand_goal = self.create_goal(r_hand_joints, r_hand_wps)

        # 4. Fire them off simultaneously
        self.get_logger().info('Executing synchronized gesture...')

        self.head_client.send_goal_async(head_goal)

        self.left_arm_client.send_goal_async(L_arm_goal)
        self.right_arm_client.send_goal_async(R_arm_goal)

        self.right_hand_client.send_goal_async(r_hand_goal)
        self.left_hand_client.send_goal_async(l_hand_goal)


        # Return the longest duration future so the script stays alive until it's done
        return self.left_hand_client.send_goal_async(l_hand_goal)


    def set_current_gesture_name(self, name):
        # Saves the current script name for the next one to find
        with open(self.state_file, 'w') as f:
            f.write(name)


def main(args=None):
    rclpy.init(args=args)
    node = PepperWaveHand()
    future = node.explaining_motions()
    rclpy.spin_until_future_complete(node, future)
    node.set_current_gesture_name("listening_gesture.launch.py")
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
 """