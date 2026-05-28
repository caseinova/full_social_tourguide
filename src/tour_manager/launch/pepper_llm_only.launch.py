from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time')
    enable_pepper = LaunchConfiguration('enable_pepper')
    enable_intent = LaunchConfiguration('enable_intent')
    enable_microphone = LaunchConfiguration('enable_microphone')
    llm_provider = LaunchConfiguration('llm_provider')
    llm_model = LaunchConfiguration('llm_model')
    llm_api_key_path = LaunchConfiguration('llm_api_key_path')
    mute = LaunchConfiguration('mute')
    start_tablet = LaunchConfiguration('start_tablet')
    start_hri = LaunchConfiguration('start_hri')
    start_gestures = LaunchConfiguration('start_gestures')
    start_audio = LaunchConfiguration('start_audio')
    enable_tour_manager = LaunchConfiguration('enable_tour_manager')
    enable_speech_locomotion_interface = LaunchConfiguration(
        'enable_speech_locomotion_interface')
    enable_pepper_listen = LaunchConfiguration('enable_pepper_listen')

    tour_manager_params_file = PathJoinSubstitution([
        FindPackageShare('tour_manager'),
        'config',
        'tour_manager_params.yaml',
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

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use ROS simulation time. Keep false for the real Pepper.'),
        DeclareLaunchArgument(
            'enable_pepper',
            default_value='true',
            description='Launch Pepper_HRI real Pepper support.'),
        DeclareLaunchArgument(
            'enable_intent',
            default_value='true',
            description='Launch turtlebot_llm_control intent-only speech and LLM support.'),
        DeclareLaunchArgument(
            'enable_microphone',
            default_value='true',
            description='Enable microphone input in the LLM speech pipeline.'),
        DeclareLaunchArgument(
            'llm_provider',
            default_value='groq',
            description='LLM provider passed to turtlebot_llm_control.'),
        DeclareLaunchArgument(
            'llm_model',
            default_value='llama-3.1-8b-instant',
            description='LLM model passed to turtlebot_llm_control.'),
        DeclareLaunchArgument(
            'llm_api_key_path',
            default_value='',
            description='Optional path to the LLM API key file.'),
        DeclareLaunchArgument(
            'mute',
            default_value='false',
            description='Mute local speech_response TTS while still publishing done_talking.'),
        DeclareLaunchArgument(
            'start_tablet',
            default_value='true',
            description='Start the Pepper tablet builder and local web server.'),
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
            description='Start the real Pepper audio pipeline. Configure IPs first.'),
        DeclareLaunchArgument(
            'enable_tour_manager',
            default_value='true',
            description='Start tour_manager and tour_saver without robot_tour/Nav2/TurtleBot.'),
        DeclareLaunchArgument(
            'enable_speech_locomotion_interface',
            default_value='true',
            description='Start the /speech/intent to locomotion command bridge.'),
        DeclareLaunchArgument(
            'enable_pepper_listen',
            default_value='true',
            description='Start pepper_llm pepper_listen to publish LLM responses to /speech_content.'),

        Node(
            package='tour_manager',
            namespace='',
            executable='tour_manager',
            name='tour_manager',
            parameters=[tour_manager_params_file],
            condition=IfCondition(enable_tour_manager),
        ),
        Node(
            package='tour_manager',
            namespace='',
            executable='tour_saver',
            name='tour_saver',
            parameters=[tour_manager_params_file],
            condition=IfCondition(enable_tour_manager),
        ),
        Node(
            package='speech_locomotion_interface',
            namespace='',
            executable='listening',
            name='speech_locomotion_interface',
            parameters=[tour_manager_params_file],
            condition=IfCondition(enable_speech_locomotion_interface),
        ),
        Node(
            package='pepper_llm',
            namespace='',
            executable='pepper_listen',
            name='pepper_listen',
            output='screen',
            condition=IfCondition(enable_pepper_listen),
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(pepper_real_launch),
            launch_arguments={
                'start_tablet': start_tablet,
                'start_hri': start_hri,
                'start_gestures': start_gestures,
                'start_audio': start_audio,
            }.items(),
            condition=IfCondition(enable_pepper),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(intent_only_launch),
            launch_arguments={
                'enable_microphone': enable_microphone,
                'llm_provider': llm_provider,
                'llm_model': llm_model,
                'llm_api_key_path': llm_api_key_path,
                'mute': mute,
                'use_sim_time': use_sim_time,
            }.items(),
            condition=IfCondition(enable_intent),
        ),
    ])
