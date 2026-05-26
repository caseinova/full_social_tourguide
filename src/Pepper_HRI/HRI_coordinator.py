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

        # --- DYNAMIC DATABASE INITIALIZATION ---
        self.exhibit_database = {}
        self.load_dynamic_database()

        # --- SUBSCRIBERS ---
        self.create_subscription(String, '/current_tour', self.current_command, 10)
        self.create_subscription(UInt8MultiArray, '/audio/audio', self.audio_callback, 10)
        self.create_subscription(String, '/human_present', self.human_present_callback, 10)
        self.create_subscription(String, '/done_talking', self.done_talking_callback, 10)

        # --- PUBLISHERS ---
        self.spoken_words_pub = self.create_publisher(String, '/pepper/spoken_words', 10)
        self.gesture_pub = self.create_publisher(String, '/pepper/gesture_command', 10)
        self.tablet_display = self.create_publisher(String, '/pepper/explain_exhibit', 10)

        self.get_logger().info("HRI Coordinator Node successfully updated with a fully dynamic database map.")

    def load_dynamic_database(self):
        """Reads exhibition_commands.json from tablet_assets on startup."""
        # CHANGE THIS LINE: include 'tablet_assets' in the asset path resolution
        manifest_path = get_package_asset_path('tablet_assets', 'exhibition_commands.json')
        
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    self.exhibit_database = json.load(f)
                self.get_logger().info(f"Successfully mapped {len(self.exhibit_database)} exhibits from manifest.")
            else:
                self.get_logger().error(f"Manifest file missing: {manifest_path}. Coordinator running with empty database.")
        except Exception as e:
            self.get_logger().error(f"Failed parsing dynamic manifest updates: {str(e)}")

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
                else:
                    self.get_logger().warn(f"Received unknown exhibit target: '{exhibit_name}'")
        except Exception as e:
            self.get_logger().error(f"Error processing single exhibit input: {str(e)}")

    def human_present_callback(self, msg):
        """Tracks raw variant inputs and triggers wave_hello updates anytime it is refreshed."""
        self.human_present_raw = msg.data.strip()
        is_present = bool(self.human_present_raw) and self.human_present_raw.lower() not in ['false', '0', 'no', 'none', 'empty']
        
        if is_present:
            self.last_human_time = time.time()
            if not self.is_explaining:
                self.get_logger().info(f"Presence update detected ({self.human_present_raw})! Waving hello.")
                self.publish_gesture("wave_hello")

    def audio_callback(self, msg):
        """Handles responsive listening states based on presence updates and audio amplitude thresholds."""
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

    def done_talking_callback(self, msg):
        """Terminates explanation loops immediately when 'done_speaking' signal is captured."""
        signal = msg.data.strip()
        
        if signal == "done_speaking" and self.is_explaining:
            self.get_logger().info(f"Received 'done_speaking' signal. Wrapping up {self.current_exhibit}.")
            
            self.is_explaining = False
            exhibit_that_finished = self.current_exhibit
            self.current_exhibit = None

            self.publish_gesture("default")
            self.get_logger().info(f"Successfully finished explanation for {exhibit_that_finished}.")

    # --- CORE HRI ACTIONS ---

    def start_explanation(self):
        """Loads text files, parses the explanation segment out, and flags the display."""
        if self.is_explaining:
            self.get_logger().warn("Already explaining an artifact. Ignoring duplicate trigger.")
            return

        self.get_logger().info(f"Starting event-driven presentation for: {self.current_exhibit}")

        exhibit_info = self.exhibit_database.get(self.current_exhibit, {"text_file": None})
        text_file = exhibit_info["text_file"]
        explanation_text = ""

        if text_file:
            # Paths inside the JSON generated by launch are already formatted clean relative strings
            abs_text_path = get_package_asset_path('tablet_assets', text_file) if not text_file.startswith('tablet_assets') else get_package_asset_path(text_file)
            try:
                with open(abs_text_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read().strip()
                
                # Split using the pipeline delimiter: [index]|[title]|[explanation]
                parts = raw_content.split('|')
                if len(parts) >= 3:
                    explanation_text = parts[2].strip()
                else:
                    explanation_text = raw_content
                    self.get_logger().warn(f"Text file {text_file} lacked explicit '|' delimiters. Using full raw text.")

                # 1. Send the extracted description text out to Pepper's TTS Engine
                words_msg = String()
                words_msg.data = explanation_text
                self.spoken_words_pub.publish(words_msg)

            except Exception as e:
                self.get_logger().error(f"Could not read/parse speech file {text_file}: {str(e)}")

        # 2. Enter active explaining state and drop into pose
        self.is_explaining = True
        self.publish_gesture("explain")

        # 3. Publish only the extracted [description] payload to the tablet view pipeline
        self.get_logger().info(f"Publishing extracted description text to /pepper/explain_exhibit")
        self.publish_tablet_exhibit(explanation_text if explanation_text else self.current_exhibit)

    # --- HELPER UTILITIES ---

    def publish_gesture(self, gesture_name):
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