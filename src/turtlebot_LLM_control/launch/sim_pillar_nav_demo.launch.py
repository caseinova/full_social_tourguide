import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    enable_microphone = LaunchConfiguration("enable_microphone")
    enable_llm = LaunchConfiguration("enable_llm")
    llm_provider = LaunchConfiguration("llm_provider")
    llm_model = LaunchConfiguration("llm_model")
    llm_api_key_path = LaunchConfiguration("llm_api_key_path")
    mute = LaunchConfiguration("mute")
    enable_speech_debug = LaunchConfiguration("enable_speech_debug")
    enable_direct_locomotion_interface = LaunchConfiguration(
        "enable_direct_locomotion_interface"
    )

    turtlebot3_model = os.environ.get("TURTLEBOT3_MODEL", "burger")

    turtlebot3_gazebo_dir = get_package_share_directory("turtlebot3_gazebo")
    turtlebot_llm_control_dir = get_package_share_directory("turtlebot_llm_control")
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")

    map_file = os.path.join(turtlebot_llm_control_dir, "maps", "demo", "map.yaml")
    params_file = os.path.join(
        turtlebot_llm_control_dir, "config", "demo_nav2", "{}.yaml".format(turtlebot3_model)
    )
    rviz_config = os.path.join(turtlebot_llm_control_dir, "rviz", "tb3_navigation2.rviz")

    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(turtlebot3_gazebo_dir, "launch", "turtlebot3_world.launch.py")
        ),
        launch_arguments={"use_sim_time": "true", "x_pose": "-2.0", "y_pose": "-0.5"}.items(),
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, "launch", "bringup_launch.py")
        ),
        launch_arguments={
            "map": map_file,
            "params_file": params_file,
            "use_sim_time": "true",
        }.items(),
    )

    llm_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(turtlebot_llm_control_dir, "launch", "bringup.launch.py")),
        launch_arguments={
            "hardware": "false",
            "enable_microphone": enable_microphone,
            "enable_llm": enable_llm,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key_path": llm_api_key_path,
            "mute": mute,
            "enable_speech_debug": enable_speech_debug,
            "enable_direct_locomotion_interface": (
                enable_direct_locomotion_interface
            ),
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("enable_microphone", default_value="true"),
            DeclareLaunchArgument("enable_llm", default_value="true"),
            DeclareLaunchArgument("llm_provider", default_value="ollama"),
            DeclareLaunchArgument("llm_model", default_value="qwen2.5-coder:latest"),
            DeclareLaunchArgument("llm_api_key_path", default_value=""),
            DeclareLaunchArgument("mute", default_value="false"),
            DeclareLaunchArgument("enable_speech_debug", default_value="true"),
            DeclareLaunchArgument(
                "enable_direct_locomotion_interface",
                default_value="false",
            ),
            gazebo_launch,
            nav2_launch,
            llm_bringup,
            Node(
                package="turtlebot_llm_control",
                executable="sim_initial_pose_node",
                name="sim_initial_pose_node",
                output="screen",
                parameters=[
                    {
                        "use_sim_time": True,
                        "x": -2.0,
                        "y": -0.5,
                        "yaw": 0.0,
                    }
                ],
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                arguments=["-d", rviz_config],
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),
        ]
    )
