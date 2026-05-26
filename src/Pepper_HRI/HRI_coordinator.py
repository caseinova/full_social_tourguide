import os
import json
import time
import numpy as np

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

PACKAGE_NAME = 'pepper_hri'


def get_package_asset_path(*parts):
    """Resolve installed package assets, falling back to the source tree."""
    # Importing dynamically to prevent deployment failures if share folder isn't fully linked
    from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
    try:
        base_path = get_package_share_directory(PACKAGE_NAME)
    except PackageNotFoundError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, *parts)

class HRICoordinatorNode(Node):

    def __init__(self):
        super().__init__('hri_coordinator_node')

        # --- STATE MANAGEMENT VARIABLES ---
        self.current_exhibit = None     # Name of the active single exhibit being processed
        self.human_present_raw = None   # Ambiguous data type storage from subsystem tracking
        self.last_human_time = 0.0      # Timestamp for "recently seen" logic
        self.is_explaining = False      # Track if an explanation session is active

        # COMPATIBILITY UPDATE: "duration" keys removed completely from database
        self.exhibit_database = {
            "walking_robot_exhibit": {"text_file": "tablet_assets/exhibition_explanation/walking_robot_exhibit_explanation.txt"},
            "combination_vault_exhibit": {"text_file": "tablet_assets/exhibition_explanation/combination_vault_exhibit_explanation.txt"},
            "LED_crystal_exhibit": {"text_file": "tablet_assets/exhibition_explanation/LED_crystal_exhibit_explanation.txt"},
            "glowing_double_peundulum_exhibit": {"text_file": "tablet_assets/exhibition_explanation/glowing_double_pendulum_exhibit_explanation.txt"},
            "crane_exhibit": {"text_file": "tablet_assets/exhibition_explanation/crane_exhibit_explanation.txt"},
            "articulated_lamp_exhibit": {"text_file": "tablet_assets/exhibition_explanation/articulated_lamp_exhibit_explanation.txt"}
        }

        # --- SUBSCRIBERS ---
        self.create_subscription(String, '/current_tour', self.current_command, 10)
        self.create_subscription(UInt8MultiArray, '/audio/audio', self.audio_callback, 10)
        self.create_subscription(String, '/human_present', self.human_present_callback, 10)
        self.create_subscription(String, '/done_talking', self.done_talking_callback, 10)

        # --- PUBLISHERS ---
        self.spoken_words_pub = self.create_publisher(String, '/pepper/spoken_words', 10)
        self.gesture_pub = self.create_publisher(String, '/pepper/gesture_command', 10)
        self.tablet_display = self.create_publisher(String, '/pepper/explain_exhibit', 10)

        self.get_logger().info("HRI Coordinator Node successfully updated to Event-Driven architecture.")

    # --- CALLBACK HANDLERS ---

    def current_command(self, msg):
        """Receives a single target exhibit command directly."""
        try:
            which_exhibit = msg.data.strip()
            if which_exhibit.startswith('{'):
                data = json.loads(which_exhibit)
                exhibit_name = data.get('exhibit', data.get('command', ''))
            else:
                exhibit_name = which_exhibit

            if exhibit_name:
                if exhibit_name in self.exhibit_database:
                    self.current_exhibit = exhibit_name
                    self.start_explanation()
                    self.get_logger().info(f"Publishing '{self.current_exhibit}' to /pepper/explain_exhibit")
                    self.publish_tablet_exhibit(self.current_exhibit)
                else:
                    self.get_logger().warn(f"Received unknown exhibit target: '{exhibit_name}'")
        except Exception as e:
            self.get_logger().error(f"Error processing single exhibit input: {str(e)}")

    def human_present_callback(self, msg):
        """Tracks raw variant inputs and triggers wave_hello updates anytime it is refreshed."""
        self.human_present_raw = msg.data.strip()
        
        # COMPATIBILITY UPDATE: Check if ambiguous data is non-empty and doesn't explicitly signify a negative state
        is_present = bool(self.human_present_raw) and self.human_present_raw.lower() not in ['false', '0', 'no', 'none', 'empty']
        
        if is_present:
            self.last_human_time = time.time()
            # COMPATIBILITY UPDATE: Fires wave gesture immediately when message updates (as long as it isn't explaining)
            if not self.is_explaining:
                self.get_logger().info(f"Presence update detected ({self.human_present_raw})! Waving hello.")
                self.publish_gesture("wave_hello")

    def audio_callback(self, msg):
        """Handles responsive listening states based on presence updates and audio amplitude thresholds."""
        # COMPATIBILITY UPDATE: Adapt presence boolean fallback to process the ambiguous data state
        is_present = bool(self.human_present_raw) and str(self.human_present_raw).lower() not in ['false', '0', 'no', 'none', 'empty']
        time_since_human = time.time() - self.last_human_time
        
        if not is_present and time_since_human > 10.0:
            return

        raw_data = np.array(msg.data, dtype=np.uint8)
        if len(raw_data) == 0:
            return
            
        audio_samples = (raw_data.astype(np.int16) - 128) * 256
        amplitude = np.max(np.abs(audio_samples))

        if amplitude > 3000 and not self.is_explaining:
            self.get_logger().info(f"Audio threshold breached ({amplitude}) with human near. Listening...")
            self.publish_gesture("listen")

    # COMPATIBILITY UPDATE: New Event-Driven callback termination logic
    def done_talking_callback(self, msg):
        """Terminates explanation loops immediately when 'done_speaking' signal is captured."""
        signal = msg.data.strip()
        
        if signal == "done_speaking" and self.is_explaining:
            self.get_logger().info(f"Received 'done_speaking' signal. Wrapping up {self.current_exhibit}.")
            
            # Reset active tracking state variables
            self.is_explaining = False
            exhibit_that_finished = self.current_exhibit
            self.current_exhibit = None

            # Reset Pepper's posture back to normal stance
            self.publish_gesture("default")
            self.get_logger().info(f"Successfully finished explanation for {exhibit_that_finished}.")

    # --- CORE HRI ACTIONS ---

    def start_explanation(self):
        """Loads text files and drops Pepper into explain stance without timing thresholds."""
        if self.is_explaining:
            self.get_logger().warn("Already explaining an artifact. Ignoring duplicate trigger.")
            return

        self.get_logger().info(f"Starting event-driven presentation for: {self.current_exhibit}")

        exhibit_info = self.exhibit_database.get(self.current_exhibit, {"text_file": None})
        text_file = exhibit_info["text_file"]

        if text_file:
            abs_text_path = get_package_asset_path(text_file)
            try:
                with open(abs_text_path, 'r') as f:
                    speech_text = f.read()
                
                words_msg = String()
                words_msg.data = speech_text
                self.spoken_words_pub.publish(words_msg)
            except Exception as e:
                self.get_logger().error(f"Could not read speech file {text_file}: {str(e)}")

        # Transition state machine and trigger stance posture
        self.is_explaining = True
        self.publish_gesture("explain")
        self.get_logger().info("Explanation gesture deployed. Waiting for /done_talking stream signal to wrap up.")

    # --- HELPER UTILITIES ---

    def publish_gesture(self, gesture_name):
        """Helper to quickly drop clean string data keys onto the gesture topic stream."""
        msg = String()
        msg.data = gesture_name
        self.gesture_pub.publish(msg)

    def publish_tablet_exhibit(self, tablet_subject):
        msg = String()
        msg.data = tablet_subject
        self.tablet_display.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = HRICoordinatorNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()