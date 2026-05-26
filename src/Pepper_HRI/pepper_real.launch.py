from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    start_tablet = LaunchConfiguration('start_tablet')
    start_hri = LaunchConfiguration('start_hri')
    start_gestures = LaunchConfiguration('start_gestures')
    start_audio = LaunchConfiguration('start_audio')
    params_file = LaunchConfiguration('params_file')

    default_params_file = PathJoinSubstitution([
        FindPackageShare('pepper_hri'),
        'config',
        'pepper_real.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='YAML file containing Pepper HRI real-robot parameters.'),
        DeclareLaunchArgument(
            'start_tablet',
            default_value='true',
            description='Start the tablet builder and local web server.'),
        DeclareLaunchArgument(
            'start_hri',
            default_value='true',
            description='Start the Pepper HRI coordinator.'),
        DeclareLaunchArgument(
            'start_gestures',
            default_value='true',
            description='Start the NAOqi gesture manager for the real Pepper robot.'),
        DeclareLaunchArgument(
            'start_audio',
            default_value='false',
            description='Start the real Pepper audio pipeline. Configure IPs in audio_processor_node.py first.'),

        Node(
            package='pepper_hri',
            executable='tablet_builder',
            name='tablet_builder_node',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(start_tablet)),

        Node(
            package='pepper_hri',
            executable='hri_coordinator',
            name='hri_coordinator_node',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(start_hri)),

        Node(
            package='pepper_hri',
            executable='gesture_manager',
            name='pepper_gesture_node',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(start_gestures)),

        Node(
            package='pepper_hri',
            executable='audio_processor',
            name='realtime_audio_processor_node',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(start_audio)),
    ])
