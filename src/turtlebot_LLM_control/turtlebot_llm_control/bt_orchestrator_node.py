from typing import Dict, List, Optional

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String

import rclpy
from rclpy.action import ActionClient
from rclpy.action.client import ClientGoalHandle
from rclpy.node import Node

from turtlebot_llm_control.behavior_tree import (
    ActionNode,
    ConditionNode,
    FallbackNode,
    NodeStatus,
    SequenceNode,
)
from turtlebot_llm_control.models import ControllerStatus, DialogueMemory, IntentToken, TaskState


class BehaviorTreeOrchestrator(Node):
    def __init__(self):
        super().__init__("bt_orchestrator_node")
        self.status = ControllerStatus()
        self.memory = DialogueMemory()
        self.route_cache: Dict[str, List[dict]] = {}
        self.pending_intent: Optional[IntentToken] = None
        self.pending_goal_location: str = ""
        self.pending_goal_pose: Optional[tuple[float, float, str]] = None
        self.nav_goal_handle: Optional[ClientGoalHandle] = None
        self.nav_result_future = None
        self.nav_in_progress = False
        self.nav_request_token = 0
        self.localization_ok = True
        self.tour_route_requested = False

        self.intent_subscription = self.create_subscription(
            String, "/speech/intent", self.handle_intent, 10
        )
        self.route_subscription = self.create_subscription(
            String, "/route/data", self.handle_route_data, 10
        )
        self.response_publisher = self.create_publisher(String, "/speech/response", 10)
        self.status_publisher = self.create_publisher(String, "/tour/status", 10)
        self.route_record_publisher = self.create_publisher(String, "/route/record", 10)
        self.save_tour_command_publisher = self.create_publisher(String, "/save_tour_command", 10)
        self.route_replay_publisher = self.create_publisher(String, "/route/replay", 10)
        self.reactive_nav_control_publisher = self.create_publisher(String, "/reactive_nav/control", 10)
        self.manual_override_publisher = self.create_publisher(String, "/manual_override/control", 10)

        self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        self.timer = self.create_timer(1.0, self.tick_tree)
        self.behavior_tree = self.build_tree()
        self.get_logger().info("Behavior-tree orchestrator ready.")

    def build_tree(self):
        return FallbackNode(
            [
                SequenceNode(
                    [
                        ConditionNode(lambda: not self.localization_ok),
                        ActionNode(self.recover_localization),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(self.has_interruption),
                        ActionNode(self.pause_current_task),
                        ActionNode(self.respond_to_user),
                        ActionNode(self.resume_previous_task),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(lambda: self.status.task_state == TaskState.TOURING),
                        ActionNode(self.replay_active_route),
                        ActionNode(self.explain_current_stop),
                        ActionNode(self.sync_gesture_stub),
                    ]
                ),
                SequenceNode(
                    [
                        ConditionNode(lambda: self.status.task_state == TaskState.NAVIGATING),
                        ActionNode(self.navigate_to_pending_goal),
                    ]
                ),
            ]
        )

    def handle_intent(self, msg: String) -> None:
        token = IntentToken.from_json(msg.data)
        self.pending_intent = token
        self.apply_intent(token)
        self.publish_status()

    def handle_route_data(self, msg: String) -> None:
        import json

        payload = json.loads(msg.data)
        self.route_cache[payload["label"]] = payload.get("waypoints", [])

    def apply_intent(self, token: IntentToken) -> None:
        if token.intent == "is_alive":
            self.say(token.response)
            return

        if token.intent == "no_action":
            self.status.task_state = TaskState.IDLE
            self.say(token.response)
            return

        if token.intent == "stop":
            self.memory.paused_task = self.status.task_state
            self.status.task_state = TaskState.IDLE
            self.status.is_paused = False
            self.status.current_target = ""
            self.cancel_navigation_goal()
            self.publish_reactive_nav_control("stop")
            self.say(token.response)
            return

        if token.intent == "stop_navigation":
            self.cancel_navigation_goal()
            self.status.task_state = TaskState.IDLE
            self.status.current_target = ""
            self.say(token.response)
            return

        if token.intent == "pause":
            self.memory.paused_task = self.status.task_state
            self.status.task_state = TaskState.PAUSED
            self.status.is_paused = True
            self.publish_reactive_nav_control("stop")
            self.say(token.response)
            return

        if token.intent == "resume":
            paused = self.memory.paused_task or TaskState.IDLE
            self.status.task_state = paused
            self.status.is_paused = False
            self.say(token.response)
            return

        if token.intent == "navigate":
            self.pending_goal_location = token.location
            self.pending_goal_pose = None
            self.status.current_location = token.location
            self.status.task_state = TaskState.NAVIGATING
            self.say(token.response)
            return

        if token.intent == "manual_override_on":
            self.status.task_state = TaskState.PAUSED
            self.publish_manual_override("on")
            self.say(token.response)
            return

        if token.intent == "manual_override_off":
            self.status.task_state = TaskState.IDLE
            self.publish_manual_override("off")
            self.say(token.response)
            return

        if token.intent == "start_recording":
            self.memory.paused_task = self.status.task_state
            self.cancel_navigation_goal()
            self.publish_reactive_nav_control("stop")
            self.status.task_state = TaskState.RECORDING
            self.status.is_recording = True
            self.status.current_route = token.label
            record_msg = String()
            record_msg.data = "start:{}".format(token.label)
            self.route_record_publisher.publish(record_msg)
            self.say(token.response)
            return

        if token.intent == "stop_recording":
            self.status.is_recording = False
            self.status.task_state = TaskState.IDLE
            self.publish_reactive_nav_control("stop")
            stop_msg = String()
            stop_msg.data = "stop"
            self.route_record_publisher.publish(stop_msg)
            self.say(token.response)
            return

        if token.intent == "save_route":
            source = self.status.current_route or token.label or self.memory.active_route or "saved_route"
            save_msg = String()
            save_msg.data = source
            self.save_tour_command_publisher.publish(save_msg)
            self.status.current_route = source
            self.say(token.response)
            return

        if token.intent == "replay_route":
            self.status.current_route = token.label
            self.status.task_state = TaskState.TOURING
            self.memory.active_route = token.label
            self.memory.current_stop_index = 0
            self.tour_route_requested = True
            replay_msg = String()
            replay_msg.data = token.label
            self.route_replay_publisher.publish(replay_msg)
            self.say(token.response)
            return

        if token.intent == "start_tour":
            route_label = self.status.current_route or self.memory.active_route or "saved_route"
            self.status.current_route = route_label
            self.memory.active_route = route_label
            self.status.task_state = TaskState.TOURING
            self.memory.current_stop_index = 0
            self.tour_route_requested = True
            replay_msg = String()
            replay_msg.data = route_label
            self.route_replay_publisher.publish(replay_msg)
            self.say(token.response)
            return

        if token.intent == "explain":
            self.memory.last_question = token.utterance
            self.memory.last_response = "{} is one of the key tour stops.".format(token.location)
            self.say(self.memory.last_response)
            return

        self.say(token.response)

    def tick_tree(self) -> None:
        self.behavior_tree.tick()
        self.publish_status()

    def has_interruption(self) -> bool:
        return self.status.task_state == TaskState.PAUSED

    def pause_current_task(self) -> NodeStatus:
        return NodeStatus.SUCCESS

    def respond_to_user(self) -> NodeStatus:
        return NodeStatus.SUCCESS

    def resume_previous_task(self) -> NodeStatus:
        return NodeStatus.SUCCESS

    def replay_active_route(self) -> NodeStatus:
        route = self.route_cache.get(self.memory.active_route, [])
        if self.tour_route_requested and not route:
            return NodeStatus.RUNNING

        if not route:
            self.status.task_state = TaskState.IDLE
            return NodeStatus.FAILURE

        if self.memory.current_stop_index >= len(route):
            self.status.task_state = TaskState.IDLE
            self.tour_route_requested = False
            return NodeStatus.SUCCESS

        waypoint = route[self.memory.current_stop_index]
        self.pending_goal_pose = (
            float(waypoint.get("x", 0.0)),
            float(waypoint.get("y", 0.0)),
            self.memory.active_route or "tour_waypoint",
        )
        self.status.task_state = TaskState.NAVIGATING
        self.memory.current_stop_index += 1
        self.tour_route_requested = False
        return NodeStatus.RUNNING

    def explain_current_stop(self) -> NodeStatus:
        if self.status.task_state != TaskState.TOURING:
            return NodeStatus.FAILURE
        route_name = self.memory.active_route or "the route"
        self.memory.last_response = (
            "We are currently touring {}. Waypoint {} is an explanation stop.".format(
                route_name,
                self.memory.current_stop_index,
            )
        )
        self.say(self.memory.last_response)
        return NodeStatus.SUCCESS

    def sync_gesture_stub(self) -> NodeStatus:
        self.get_logger().debug("Gesture sync placeholder triggered.")
        return NodeStatus.SUCCESS

    def navigate_to_pending_goal(self) -> NodeStatus:
        if self.nav_in_progress:
            return NodeStatus.RUNNING

        if self.pending_goal_pose is not None:
            x, y, label = self.pending_goal_pose
            if self.send_navigation_goal(x, y, label):
                self.pending_goal_pose = None
                return NodeStatus.RUNNING
            return NodeStatus.FAILURE

        if not self.pending_goal_location:
            return NodeStatus.FAILURE

        location_map = {
            "lab": (1.0, 2.0),
            "entrance": (0.0, 0.0),
            "kitchen": (2.0, -1.0),
            "pillar_1": (-1.6, -1.1),
            "pillar_2": (-1.6, 0.0),
            "pillar_3": (-1.6, 1.1),
            "pillar_4": (-0.5, -1.1),
            "pillar_5": (-0.5, 0.0),
            "pillar_6": (-0.5, 1.1),
            "pillar_7": (0.6, -1.1),
            "pillar_8": (0.6, 0.0),
            "pillar_9": (0.6, 1.1),
        }
        goal = location_map.get(self.pending_goal_location)
        if goal is None:
            self.say("I do not know where {} is yet.".format(self.pending_goal_location or "that place"))
            self.status.task_state = TaskState.IDLE
            self.pending_goal_location = ""
            return NodeStatus.FAILURE
        if self.send_navigation_goal(goal[0], goal[1], self.pending_goal_location):
            self.pending_goal_location = ""
            return NodeStatus.RUNNING
        return NodeStatus.FAILURE

    def recover_localization(self) -> NodeStatus:
        self.status.task_state = TaskState.RECOVERING
        self.say("Localization confidence is low. Starting recovery routine.")
        self.localization_ok = True
        self.status.task_state = TaskState.IDLE
        return NodeStatus.SUCCESS

    def send_navigation_goal(self, x: float, y: float, target_label: str = "") -> bool:
        if not self.nav_client.server_is_ready():
            self.get_logger().warning("Nav2 action server is not ready yet.")
            return False

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.w = 1.0
        self.nav_request_token += 1
        request_token = self.nav_request_token
        self.nav_in_progress = True
        self.status.task_state = TaskState.NAVIGATING
        self.status.current_target = target_label
        send_future = self.nav_client.send_goal_async(goal)
        send_future.add_done_callback(
            lambda future, token=request_token: self.handle_navigation_goal_response(future, token)
        )
        self.say("Starting navigation to {}.".format(target_label or "the requested location"))
        return True

    def handle_navigation_goal_response(self, future, request_token: int) -> None:
        if request_token != self.nav_request_token or self.status.task_state != TaskState.NAVIGATING:
            try:
                goal_handle = future.result()
            except Exception:
                return
            if goal_handle is not None and getattr(goal_handle, "accepted", False):
                goal_handle.cancel_goal_async()
            return

        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.nav_goal_handle = None
            self.nav_in_progress = False
            self.status.task_state = TaskState.IDLE
            self.say("Navigation goal was rejected.")
            return

        self.nav_goal_handle = goal_handle
        self.nav_result_future = goal_handle.get_result_async()
        self.nav_result_future.add_done_callback(
            lambda future, token=request_token: self.handle_navigation_result(future, token)
        )

    def handle_navigation_result(self, future, request_token: int) -> None:
        if request_token != self.nav_request_token:
            return
        self.nav_in_progress = False
        self.nav_goal_handle = None
        self.nav_result_future = None
        result = future.result()
        status = getattr(result, "status", None)
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.say("Navigation goal reached.")
        elif status == GoalStatus.STATUS_CANCELED:
            self.say("Navigation was canceled.")
        elif status is not None:
            self.say("Navigation finished with status {}.".format(status))
        self.status.task_state = TaskState.IDLE
        self.status.current_target = ""

    def cancel_navigation_goal(self) -> None:
        self.nav_request_token += 1
        if self.nav_goal_handle is None:
            self.pending_goal_location = ""
            self.pending_goal_pose = None
            self.nav_result_future = None
            self.nav_in_progress = False
            return
        self.nav_goal_handle.cancel_goal_async()
        self.pending_goal_location = ""
        self.pending_goal_pose = None
        self.nav_in_progress = False
        self.nav_result_future = None

    def publish_reactive_nav_control(self, command: str) -> None:
        msg = String()
        msg.data = command
        self.reactive_nav_control_publisher.publish(msg)

    def publish_manual_override(self, command: str) -> None:
        msg = String()
        msg.data = command
        self.manual_override_publisher.publish(msg)

    def say(self, text: str) -> None:
        if not text:
            return
        response_msg = String()
        response_msg.data = text
        self.response_publisher.publish(response_msg)
        self.get_logger().info(text)

    def publish_status(self) -> None:
        status_msg = String()
        status_msg.data = self.status.to_json()
        self.status_publisher.publish(status_msg)


def main(args=None):
    rclpy.init(args=args)
    node = BehaviorTreeOrchestrator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
