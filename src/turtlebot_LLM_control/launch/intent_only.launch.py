from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    enable_microphone = LaunchConfiguration("enable_microphone")
    enable_llm = LaunchConfiguration("enable_llm")
    llm_provider = LaunchConfiguration("llm_provider")
    llm_model = LaunchConfiguration("llm_model")
    llm_api_key_path = LaunchConfiguration("llm_api_key_path")
    intent_topic = LaunchConfiguration("intent_topic")
    enable_speech_debug = LaunchConfiguration("enable_speech_debug")
    enable_speech_response = LaunchConfiguration("enable_speech_response")
    enable_tour_teleop_trigger = LaunchConfiguration("enable_tour_teleop_trigger")
    enable_tsp_gui = LaunchConfiguration("enable_tsp_gui")
    enable_emotion = LaunchConfiguration("enable_emotion")
    enable_waypoint_speaker = LaunchConfiguration("enable_waypoint_speaker")
    default_route_label = LaunchConfiguration("default_route_label")
    mute = LaunchConfiguration("mute")
    use_sim_time = LaunchConfiguration("use_sim_time")
    mic_device_index = LaunchConfiguration("mic_device_index")
    energy_threshold = LaunchConfiguration("energy_threshold")
    dynamic_energy_threshold = LaunchConfiguration("dynamic_energy_threshold")
    calibrate_ambient_noise = LaunchConfiguration("calibrate_ambient_noise")
    phrase_time_limit = LaunchConfiguration("phrase_time_limit")
    require_wake_word = LaunchConfiguration("require_wake_word")
    wake_command_window_seconds = LaunchConfiguration("wake_command_window_seconds")

    intent_remapping = [("/speech/intent", intent_topic)]

    return LaunchDescription(
        [
            DeclareLaunchArgument("enable_microphone", default_value="true"),
            DeclareLaunchArgument("enable_llm", default_value="true"),
            DeclareLaunchArgument("llm_provider", default_value="ollama"),
            DeclareLaunchArgument("llm_model", default_value="qwen2.5-coder:latest"),
            DeclareLaunchArgument("llm_api_key_path", default_value=""),
            DeclareLaunchArgument("intent_topic", default_value="/speech/intent"),
            DeclareLaunchArgument("enable_speech_debug", default_value="true"),
            DeclareLaunchArgument("enable_speech_response", default_value="true"),
            DeclareLaunchArgument("enable_tour_teleop_trigger", default_value="true"),
            DeclareLaunchArgument("enable_tsp_gui", default_value="true"),
            DeclareLaunchArgument("enable_emotion", default_value="true"),
            DeclareLaunchArgument("enable_waypoint_speaker", default_value="true"),
            DeclareLaunchArgument("default_route_label", default_value="saved_route"),
            DeclareLaunchArgument("mute", default_value="false"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("mic_device_index", default_value="-1"),
            DeclareLaunchArgument("energy_threshold", default_value="150"),
            DeclareLaunchArgument("dynamic_energy_threshold", default_value="false"),
            DeclareLaunchArgument("calibrate_ambient_noise", default_value="false"),
            DeclareLaunchArgument("phrase_time_limit", default_value="5.0"),
            DeclareLaunchArgument("require_wake_word", default_value="true"),
            DeclareLaunchArgument("wake_command_window_seconds", default_value="45.0"),
            Node(
                package="turtlebot_llm_control",
                executable="speech_to_text_node",
                name="speech_to_text_node",
                output="screen",
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "enable_microphone": enable_microphone,
                        "mic_device_index": mic_device_index,
                        "energy_threshold": energy_threshold,
                        "dynamic_energy_threshold": dynamic_energy_threshold,
                        "calibrate_ambient_noise": calibrate_ambient_noise,
                        "phrase_time_limit": phrase_time_limit,
                        "require_wake_word": require_wake_word,
                        "wake_command_window_seconds": wake_command_window_seconds,
                    }
                ],
            ),
            Node(
                package="turtlebot_llm_control",
                executable="speech_command_node",
                name="speech_command_node",
                output="screen",
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "enable_llm": enable_llm,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "llm_api_key_path": llm_api_key_path,
                    }
                ],
                remappings=intent_remapping,
            ),
            Node(
                package="turtlebot_llm_control",
                executable="speech_debug_node",
                name="speech_debug_node",
                output="screen",
                condition=IfCondition(enable_speech_debug),
                parameters=[{"use_sim_time": use_sim_time}],
                remappings=intent_remapping,
            ),
            Node(
                package="turtlebot_llm_control",
                executable="speech_response_node",
                name="speech_response_node",
                output="screen",
                condition=IfCondition(enable_speech_response),
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "mute": mute,
                    }
                ],
            ),
            Node(
                package="turtlebot_llm_control",
                executable="tour_intent_bridge_node",
                name="tour_intent_bridge_node",
                output="screen",
                condition=IfCondition(enable_tour_teleop_trigger),
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                        "default_route_label": default_route_label,
                    }
                ],
                remappings=intent_remapping,
            ),
            Node(
                package="turtlebot_llm_control",
                executable="tsp_gui",
                name="tsp_gui_node",
                output="screen",
                condition=IfCondition(enable_tsp_gui),
                parameters=[{"use_sim_time": use_sim_time}],
            ),
            Node(
                package="turtlebot_llm_control",
                executable="emotion_node",
                name="emotion_node",
                output="screen",
                condition=IfCondition(enable_emotion),
                parameters=[{"use_sim_time": use_sim_time}],
            ),
            Node(
                package="turtlebot_llm_control",
                executable="waypoint_speaker",
                name="waypoint_speaker_node",
                output="screen",
                condition=IfCondition(enable_waypoint_speaker),
                parameters=[{"use_sim_time": use_sim_time}],
            ),
        ]
    )
