from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Start the Tablet Builder & Localhost Server
        Node(
            package='pepper_hri',
            executable='tablet_builder',
            output='screen',
            name='tablet_builder_node'
        ),
        
        # 2. Start the Master Brain Coordinator
        Node(
            package='pepper_hri',
            executable='hri_coordinator',
            output='screen',
            name='hri_coordinator_node'
        ),
        
        # 3. Start the Physical Action/Gesture Node
        Node(
            package='pepper_hri',
            executable='gesture_manager',
            output='screen',
            name='pepper_gesture_node'
        )
    ])
