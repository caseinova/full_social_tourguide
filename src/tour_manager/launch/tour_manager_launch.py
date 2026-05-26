from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = PathJoinSubstitution([
        FindPackageShare('tour_manager'),
        'config',
        'tour_manager_params.yaml',
    ])

    return LaunchDescription([
        Node(
            package='tour_manager',
            namespace='',
            executable='tour_manager',
            name='tour_manager',
            parameters=[params_file],
        ),
        Node(
            package='tour_manager',
            namespace='',
            executable='tour_saver',
            name='tour_saver',
            parameters=[params_file],
        ),
        Node(
            package='robot_tour',
            namespace='',
            executable='tour_guide_start',
            parameters=[params_file],
        ),
        Node(
            package='robot_tour',
            namespace='',
            executable='subtour_start',
            name='subtour',
            parameters=[params_file],
        ),
        Node(
            package='opennav_docking',
            namespace='',
            executable='opennav_docking',
            name='docking_server',
            output='screen',
            parameters=[params_file],
        ),
        Node(
            package='nav2_lifecycle_manager',
            namespace='',
            executable='lifecycle_manager',
            name='lifecycle_manager_docking',
            output='screen',
            parameters=[params_file],
        ),
        Node(
            package='docking',
            namespace='',
            executable='dock_listener',
            name='dock_listener',
            parameters=[params_file],
        ),
        Node(
            package='speech_locomotion_interface',
            namespace='',
            executable='listening',
            parameters=[params_file],
        )
    ])
