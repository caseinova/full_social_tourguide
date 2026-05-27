from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    start_sim = LaunchConfiguration('start_sim')
    start_tablet = LaunchConfiguration('start_tablet')
    start_hri = LaunchConfiguration('start_hri')
    start_gestures = LaunchConfiguration('start_gestures')
    show_local_browser = LaunchConfiguration('show_local_browser')

    pepper_hri_share = FindPackageShare('pepper_hri')
    move_pepper_launch = PathJoinSubstitution([
        pepper_hri_share,
        'launch',
        'move_pepper.launch.py',
    ])

    sim_parameters = [{'use_sim_time': True}]
    tablet_sim_parameters = [{
        'use_sim_time': True,
        'use_tablet_service': False,
        'show_local_browser': ParameterValue(show_local_browser, value_type=bool),
    }]
    gesture_sim_parameters = [{
        'use_sim_time': True,
        'simulate_speech_done': True,
    }]

    return LaunchDescription([
        DeclareLaunchArgument(
            'start_sim',
            default_value='true',
            description='Start Gazebo and simulated Pepper controllers.'),
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
            description='Start the simulated Pepper trajectory gesture manager.'),
        DeclareLaunchArgument(
            'show_local_browser',
            default_value='true',
            description='Open the simulated tablet page in a local browser.'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(move_pepper_launch),
            condition=IfCondition(start_sim)),

        Node(
            package='pepper_hri',
            executable='tablet_builder',
            name='tablet_builder_node',
            output='screen',
            parameters=tablet_sim_parameters,
            condition=IfCondition(start_tablet)),

        Node(
            package='pepper_hri',
            executable='hri_coordinator',
            name='hri_coordinator_node',
            output='screen',
            parameters=sim_parameters,
            condition=IfCondition(start_hri)),

        Node(
            package='pepper_hri',
            executable='gesture_manager_sim',
            name='pepper_gesture_node',
            output='screen',
            parameters=gesture_sim_parameters,
            condition=IfCondition(start_gestures)),
    ])
