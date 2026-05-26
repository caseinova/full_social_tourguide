import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    # 1. Paths
    pkg_share = FindPackageShare('pepper_robot_description').find('pepper_robot_description')
    sdf_path = os.path.join(pkg_share, 'pepper_robot', 'model.sdf')
    xacro_path = os.path.join(pkg_share, 'urdf', 'pepper_robot.urdf.xacro')
    
    # 2. Launch Gazebo
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(FindPackageShare('ros_gz_sim').find('ros_gz_sim'), 
                         'launch', 'gz_sim.launch.py')
        ]),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
    )

    # 3. NEW: Robot State Publisher (This fixes the "service not available" error)
    robot_description_content = ParameterValue(
        Command([FindExecutable(name="xacro"), " ", xacro_path, " ros2_control:=true"]),
        value_type=str
    )

    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[{'robot_description': robot_description_content, 'use_sim_time': True}],
    )

    # 4. Spawn the Robot
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-file', sdf_path, '-name', 'pepper'],
        output='screen',
    )

    # 5. Spawners (JSB and Head)
    load_jsb = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster"],
    )

    # Existing Head Controller
    load_head_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["head_controller"],
    )

    load_torso_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["torso_controller"],
    )

    # NEW: Left Arm Controller Node
    load_left_arm_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["left_arm_controller"],
    )

    load_left_hand_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["left_hand_controller"],
    )

    load_right_arm_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["right_arm_controller"],
    )

    load_right_hand_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["right_hand_controller"],
    )

    # 6. Bridge
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
        ],
    )

    return LaunchDescription([
        gazebo,
        rsp_node, 
        spawn_robot,
        bridge,
        # You need to add load_left_arm_ctrl inside this list!
        TimerAction(period=8.0, actions=[
            load_jsb, 
            load_head_ctrl, 
            load_torso_ctrl, 
            load_left_arm_ctrl,
            load_left_hand_ctrl, 
            load_right_arm_ctrl, 
            load_right_hand_ctrl
        ]),
    ])