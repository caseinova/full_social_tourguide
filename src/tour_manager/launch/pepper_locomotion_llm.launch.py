from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch.substitutions import PythonExpression
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    model = LaunchConfiguration('model')
    lds_model = LaunchConfiguration('lds_model')
    turtlebot_mode = LaunchConfiguration('turtlebot_mode')
    use_sim_time = LaunchConfiguration('use_sim_time')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    usb_port = LaunchConfiguration('usb_port')
    namespace = LaunchConfiguration('namespace')
    enable_pepper = LaunchConfiguration('enable_pepper')
    enable_intent = LaunchConfiguration('enable_intent')

    sim_condition = IfCondition(
        PythonExpression(["'", turtlebot_mode, "' == 'sim'"]))
    real_condition = IfCondition(
        PythonExpression(["'", turtlebot_mode, "' == 'real'"]))

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
    turtlebot3_robot_launch = PathJoinSubstitution([
        FindPackageShare('turtlebot3_bringup'),
        'launch',
        'robot.launch.py',
    ])
    pepper_real_launch = PathJoinSubstitution([
        FindPackageShare('pepper_hri'),
        'launch',
        'pepper_real.launch.py',
    ])
    intent_only_launch = PathJoinSubstitution([
        FindPackageShare('turtlebot_llm_control'),
        'launch',
        'intent_only.launch.py',
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
            description='TurtleBot3 model to run.'),
        DeclareLaunchArgument(
            'lds_model',
            default_value='LDS-01',
            description='LDS model used by the real TurtleBot3 bringup.'),
        DeclareLaunchArgument(
            'turtlebot_mode',
            default_value='sim',
            description='Choose sim for Gazebo or real for the physical TurtleBot3.'),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value=PythonExpression(
                ["'true' if '", turtlebot_mode, "' == 'sim' else 'false'"]),
            description='Use simulation time. Defaults to true in sim mode and false in real mode.'),
        DeclareLaunchArgument(
            'nav2_params_file',
            default_value=default_nav2_params_file,
            description='Full path to the Navigation2 parameter file.'),
        DeclareLaunchArgument(
            'usb_port',
            default_value='/dev/ttyACM0',
            description='OpenCR USB port for real TurtleBot3 mode.'),
        DeclareLaunchArgument(
            'namespace',
            default_value='',
            description='Namespace forwarded to real TurtleBot3 bringup.'),
        DeclareLaunchArgument(
            'enable_pepper',
            default_value='true',
            description='Launch Pepper_HRI real Pepper support.'),
        DeclareLaunchArgument(
            'enable_intent',
            default_value='true',
            description='Launch turtlebot_llm_control intent-only speech and LLM support.'),

        SetEnvironmentVariable('TURTLEBOT3_MODEL', model),
        SetEnvironmentVariable('LDS_MODEL', lds_model),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot3_world_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
            }.items(),
            condition=sim_condition,
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(turtlebot3_robot_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'usb_port': usb_port,
                'namespace': namespace,
            }.items(),
            condition=real_condition,
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
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(pepper_real_launch),
            condition=IfCondition(enable_pepper),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(intent_only_launch),
            launch_arguments={
                'enable_microphone': 'true',
                'llm_provider': 'groq',
                'llm_model': 'llama-3.1-8b-instant',
                'use_sim_time': use_sim_time,
            }.items(),
            condition=IfCondition(enable_intent),
        ),
    ])
