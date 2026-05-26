import os
import json
import time
import numpy as np

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, UInt8MultiArray
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory

PACKAGE_NAME = 'pepper_hri'


def get_package_asset_path(*parts):
    """Resolve installed package assets, falling back to the source tree."""
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
        self.human_present = False      # Tracking presence state
        self.last_human_time = 0.0      # Timestamp for "recently seen" logic
        self.is_explaining = False      # Track if a timed explanation session is running
        self.explanation_timer = None   # Reference to the active ROS explanation timer

        # Placeholder database for exhibit durations (and script file lookups)
        # Likely need to change the keys into a value in the dictionary pair, depending on input
        self.exhibit_database = {
            "walking_robot_exhibit": {"duration": 15.0, "text_file": "tablet_assets/exhibition_explanation/walking_robot_exhibit_explanation.txt"},
            "combination_vault_exhibit": {"duration": 22.5, "text_file": "tablet_assets/exhibition_explanation/combination_vault_exhibit_explanation.txt"},
            "LED_crystal_exhibit": {"duration": 18.0, "text_file": "tablet_assets/exhibition_explanation/LED_crystal_exhibit_explanation.txt"},
            "glowing_double_peundulum_exhibit": {"duration": 15.0, "text_file": "tablet_assets/exhibition_explanation/glowing_double_pendulum_exhibit_explanation.txt"},
            "crane_exhibit": {"duration": 15.0, "text_file": "tablet_assets/exhibition_explanation/crane_exhibit_explanation.txt"},
            "articulated_lamp_exhibit": {"duration": 15.0, "text_file": "tablet_assets/exhibition_explanation/articulated_lamp_exhibit_explanation.txt"}
        }

        # --- SUBSCRIBERS ---
        self.create_subscription(String, '/current_tour', self.current_command, 10)
        self.create_subscription(String, '/human_present', self.human_present_callback, 10)
        self.create_subscription(UInt8MultiArray, '/audio/audio', self.audio_callback, 10)

        # --- PUBLISHERS ---
        self.save_tour_pub = self.create_publisher(String, '/save_tour_command', 10)
        self.spoken_words_pub = self.create_publisher(String, '/pepper/spoken_words', 10)
        self.gesture_pub = self.create_publisher(String, '/pepper/gesture_command', 10)
        self.finished_explanation_pub = self.create_publisher(String, '/done_talking', 10)
        self.tablet_display = self.create_publisher(String, '/pepper/explain_exhibit', 10)

        self.get_logger().info("HRI Coordinator Node successfully initialized with single-exhibit targeting.")






    # --- CALLBACK HANDLERS ---

    def current_command(self, msg):
        """Receives a single target exhibit command directly."""
        try:
            # Try parsing as JSON first in case the frontend still encapsulates it
            which_exhibit = msg.data.strip()
            if which_exhibit.startswith('{'):
                data = json.loads(which_exhibit)
                # Fallback to check if it's passed as a single command key or string
                exhibit_name = data.get('exhibit', data.get('command', ''))
            else:
                # Otherwise, it's just a clean, raw string argument
                exhibit_name = which_exhibit

            if exhibit_name:
                if exhibit_name in self.exhibit_database:
                    self.current_exhibit = exhibit_name
                    
                    # Relay down to the database logger saving topic
                    # self.save_tour_pub.publish(msg) -- no longer needed, this will be published through the actual menu.html
                    
                    
                    self.start_explanation()
                    self.get_logger().info(f"Publishing ' {self.current_exhibit} ' to /pepper/explain_exhibit")
                    self.publish_tablet_exhibit(self.current_exhibit)

                else:
                    self.get_logger().warn(f"Received unknown exhibit target: '{exhibit_name}'")
        except Exception as e:
            self.get_logger().error(f"Error processing single exhibit input: {str(e)}")

    def human_present_callback(self, msg):
        """Tracks visitor presence and handles spatial greetings."""
        self.human_present = msg.data
        
        if self.human_present:
            self.last_human_time = time.time()
            if not self.is_explaining:
                self.get_logger().info("Human detected! Waving hello.")
                self.publish_gesture("wave_hello")

    def audio_callback(self, msg):
        """Handles responsive listening states based on presence and audio amplitude thresholds."""
        time_since_human = time.time() - self.last_human_time
        if not self.human_present and time_since_human > 10.0:
            return

        raw_data = np.array(msg.data, dtype=np.uint8)
        if len(raw_data) == 0:
            return
            
        audio_samples = (raw_data.astype(np.int16) - 128) * 256
        amplitude = np.max(np.abs(audio_samples))

        if amplitude > 3000 and not self.is_explaining:
            self.get_logger().info(f"Audio threshold breached ({amplitude}) with human near. Listening...")
            self.publish_gesture("listen")






    # --- CORE HRI ACTIONS & TIMERS ---

    def start_explanation(self):
        """Loads text and starts the timed gesture loop directly for the set current_exhibit."""
        if self.is_explaining:
            self.get_logger().warn("Already explaining an artifact. Ignoring duplicate trigger.")
            return

        self.get_logger().info(f"Starting explanation processing for: {self.current_exhibit}")

        # Fetch configuration details from the database map
        exhibit_info = self.exhibit_database.get(self.current_exhibit, {"duration": 10.0, "text_file": None})
        duration = exhibit_info["duration"]
        text_file = exhibit_info["text_file"]

        # 1. Read and publish the speech text content for Pepper's TTS engine
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

        # 2. Enter the explaining state and engage animation
        self.is_explaining = True
        self.publish_gesture("explain")

        # 3. Create a dynamic, non-blocking ROS timer customized for this specific exhibit duration
        self.get_logger().info(f"Setting explanation timer for {duration} seconds.")
        self.explanation_timer = self.create_timer(duration, self.exhibition_timeout_callback)

    def exhibition_timeout_callback(self):
        """Triggers automatically when the specific exhibit's presentation timer concludes."""
        self.get_logger().info(f"Explanation timeout reached for {self.current_exhibit}.")
        
        # 1. Clear out this specific timer instance instantly so it doesn't loop
        if self.explanation_timer:
            self.explanation_timer.destroy()
            self.explanation_timer = None

        # 2. Update operational states
        self.is_explaining = False
        exhibit_that_finished = self.current_exhibit
        self.current_exhibit = None  # Reset tracking state so it's ready for the next single input

        # 3. Publish finishing sequences to control topic listeners
        self.publish_gesture("default")
        
        finish_msg = Bool()
        finish_msg.data = True
        self.finished_explanation_pub.publish(finish_msg)
        self.get_logger().info(f"Successfully wrapped up presentation for {exhibit_that_finished}.")






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
