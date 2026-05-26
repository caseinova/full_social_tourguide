from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    image_topic = LaunchConfiguration('image_topic')
    alternate_image_topic = LaunchConfiguration('alternate_image_topic')
    camera_info_topic = LaunchConfiguration('camera_info_topic')
    camera_frame_override = LaunchConfiguration('camera_frame_override')
    follow_command_topic = LaunchConfiguration('follow_command_topic')
    follow_mode = LaunchConfiguration('follow_mode')
    cmd_vel_topic = LaunchConfiguration('cmd_vel_topic')
    enabled = LaunchConfiguration('enabled')

    default_params_file = PathJoinSubstitution([
        FindPackageShare('qr_code_follower'),
        'config',
        'qr_follower.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='QR follower parameter file.'),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation time.'),
        DeclareLaunchArgument(
            'image_topic',
            default_value='/camera/image_raw',
            description='Camera image topic to subscribe to.'),
        DeclareLaunchArgument(
            'alternate_image_topic',
            default_value='/image',
            description='Optional second camera image topic to subscribe to.'),
        DeclareLaunchArgument(
            'camera_info_topic',
            default_value='/camera/camera_info',
            description='Camera info topic used for QR pose estimation.'),
        DeclareLaunchArgument(
            'camera_frame_override',
            default_value='camera_rgb_optical_frame',
            description='TF frame to use for QR pose estimation. Empty uses image header frame_id.'),
        DeclareLaunchArgument(
            'follow_command_topic',
            default_value='follow_command',
            description='std_msgs/String topic that starts and stops QR following.'),
        DeclareLaunchArgument(
            'follow_mode',
            default_value='direct',
            description='pose uses NavigateThroughPoses; direct publishes cmd_vel.'),
        DeclareLaunchArgument(
            'cmd_vel_topic',
            default_value='/cmd_vel',
            description='Velocity command topic used only in direct follow mode.'),
        DeclareLaunchArgument(
            'enabled',
            default_value='false',
            description='Start the behavior enabled.'),

        Node(
            package='qr_code_follower',
            executable='qr_follower',
            name='qr_follower',
            output='screen',
            parameters=[
                params_file,
                {
                    'use_sim_time': use_sim_time,
                    'image_topic': image_topic,
                    'alternate_image_topic': alternate_image_topic,
                    'camera_info_topic': camera_info_topic,
                    'camera_frame_override': camera_frame_override,
                    'follow_command_topic': follow_command_topic,
                    'follow_mode': follow_mode,
                    'cmd_vel_topic': cmd_vel_topic,
                    'enabled': enabled,
                },
            ],
        ),
    ])
