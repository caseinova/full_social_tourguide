from setuptools import find_packages, setup


package_name = "turtlebot_llm_control"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (
            f"share/{package_name}/launch",
            [
                "launch/bringup.launch.py",
                "launch/intent_only.launch.py",
                "launch/sim_pillar_nav_demo.launch.py",
            ],
        ),
        (
            f"share/{package_name}/config/demo_nav2",
            [
                "config/demo_nav2/burger.yaml",
                "config/demo_nav2/waffle.yaml",
                "config/demo_nav2/waffle_pi.yaml",
            ],
        ),
        (
            f"share/{package_name}/maps/demo",
            [
                "maps/demo/map.yaml",
                "maps/demo/map.pgm",
            ],
        ),
        (
            f"share/{package_name}/rviz",
            ["rviz/tb3_navigation2.rviz"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="karan",
    maintainer_email="karan@example.com",
    description="LLM-driven speech, routing, and behavior-tree orchestration for TurtleBot.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "speech_command_node = turtlebot_llm_control.speech_command_node:main",
            "speech_to_text_node = turtlebot_llm_control.speech_to_text_node:main",
            "llm_intent_test = turtlebot_llm_control.llm_intent_test:main",
            "bt_orchestrator_node = turtlebot_llm_control.bt_orchestrator_node:main",
"sim_initial_pose_node = turtlebot_llm_control.sim_initial_pose_node:main",
            "speech_response_node = turtlebot_llm_control.speech_response_node:main",
            "speech_debug_node = turtlebot_llm_control.speech_debug_node:main",
            "tour_intent_bridge_node = turtlebot_llm_control.tour_intent_bridge_node:main",
            "tour_recording_manager = turtlebot_llm_control.tour_recording_manager:main",
            "tour_teleop_session = turtlebot_llm_control.tour_teleop_session:main",
            "tsp_gui = turtlebot_llm_control.tsp_gui_node:main",
            "emotion_node = turtlebot_llm_control.emotion_node:main",
            "waypoint_speaker = turtlebot_llm_control.waypoint_speaker_node:main",
        ],
    },
)
