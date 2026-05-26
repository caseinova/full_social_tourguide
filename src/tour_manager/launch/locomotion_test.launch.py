from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    model = LaunchConfiguration('model')
    use_sim_time = LaunchConfiguration('use_sim_time')
    nav2_params_file = LaunchConfiguration('nav2_params_file')

    tour_manager_launch = PathJoinSubstitution([
        FindPackageShare('tour_manager'),
        'launch',
        'tour_manager_launch.py',
    ])
    navigation2_launch = PathJoinSubstitution([
        FindPackageShare('turtlebot3_navigation2'),
        'launch',
        'navigation2.launch.py',
    ])
    turtlebot3_world_launch = PathJoinSubstitution([
        FindPackageShare('turtlebot3_gazebo'),
        'launch',
        'turtlebot3_world.launch.py',
    ])
    default_nav2_params_file = PathJoinSubstitution([
        FindPackageShare('turtlebot3_navigation2'),
        'param',
        'humble',
        'waffle_pi.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'model',
            default_value='waffle_pi',
            description='TurtleBot3 model to simulate'),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use Gazebo simulation time'),
        DeclareLaunchArgument(
            'nav2_params_file',
            default_value=default_nav2_params_file,
            description='Full path to the Navigation2 parameter file'),

        SetEnvironmentVariable('TURTLEBOT3_MODEL', model),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot3_world_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(navigation2_launch),
            launch_arguments={
                'params_file': nav2_params_file,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(tour_manager_launch),
        ),
    ])
