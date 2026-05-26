import os
import subprocess
import threading
import time
import json
import numpy as np

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray 

class RealTimeAudioProcessor(Node):

    def __init__(self):
        super().__init__('realtime_audio_processor_node')
        
        # --- CONFIGURATION CONSTANTS ---
        self.LAPTOP_IP = "192.168.1.50"  # Replace with your local laptop IP
        self.PEPPER_IP = "192.168.1.100" # Replace with your Pepper's IP
        self.PEPPER_USER = "nao"         # Default Pepper username
        
        # Keep track of background processes for cleanup
        self.pepper_ssh_proc = None

        # --- AUTOMATIC SYSTEM CONFIGURATION ---
        self.setup_audio_pipeline()

        # --- ROS 2 TOPIC SETUP ---
        self.subscription = self.create_subscription(
            UInt8MultiArray,
            '/audio/audio',
            self.audio_callback,
            10)
        
        self.get_logger().info("Real-Time Audio Processing Node cleanly automated and started.")

    def setup_audio_pipeline(self):
        try:
            # 1. Configure Local Laptop Ports
            self.get_logger().info("Configuring local PulseAudio network ports...")
            subprocess.run([
                "pactl", "load-module", "module-native-protocol-tcp", "auth-anonymous=1"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. Tell Pepper to redirect its microphone stream over to the laptop
            self.get_logger().info(f"Connecting to Pepper ({self.PEPPER_IP}) to tunnel audio sink...")
            tunnel_cmd = f"pactl load-module module-tunnel-sink server={self.LAPTOP_IP}"
            subprocess.run([
                "ssh", f"{self.PEPPER_USER}@{self.PEPPER_IP}", tunnel_cmd
            ], check=True)

            # 3. Spin up Pepper's ROS 2 audio capture node in a non-blocking background process
            self.get_logger().info("Launching background ROS 2 audio capture node on Pepper...")
            capture_cmd = f"ros2 run audio_capture audio_capture_node --ros-args -p dst:={self.LAPTOP_IP}"
            
            # We use Popen so Python doesn't freeze waiting for the robot node to finish
            self.pepper_ssh_proc = subprocess.Popen([
                "ssh", f"{self.PEPPER_USER}@{self.PEPPER_IP}", capture_cmd
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        except subprocess.CalledProcessError as e:
            self.get_logger().error(f"Failed to execute native audio configuration command: {str(e)}")
        except Exception as e:
            self.get_logger().error(f"Audio pipeline setup error: {str(e)}")

    def audio_callback(self, msg):
        raw_data = np.array(msg.data, dtype=np.uint8)
        if len(raw_data) == 0:
            return

        # Convert raw stream to 16-bit signed PCM arrays
        audio_samples = (raw_data.astype(np.int16) - 128) * 256
        amplitude = np.max(np.abs(audio_samples))
        
        # Real-time capture verification statement
        if amplitude > 2000: 
            self.get_logger().info(f"[LIVE AUDIO] Live amplitude spike processed: {amplitude}")

    def shutdown_pipeline(self):
        """Clean up the open network streams so ports don't lock up on restart"""
        self.get_logger().info("Cleaning up network audio streams...")
        
        # 1. Terminate the background SSH node process on Pepper
        if self.pepper_ssh_proc:
            self.pepper_ssh_proc.terminate()
            self.pepper_ssh_proc.wait()
        
        # 2. Unload the modules cleanly from both environments
        try:
            # Unload on Pepper
            subprocess.run([
                "ssh", f"{self.PEPPER_USER}@{self.PEPPER_IP}", "pactl unload-module module-tunnel-sink"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Unload on Laptop
            subprocess.run([
                "pactl", "unload-module", "module-native-protocol-tcp"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass # Suppress exit failures during standard system interrupts


def main(args=None):
    rclpy.init(args=args)
    node = RealTimeAudioProcessor()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Trigger cleanup routing before finalizing node contexts
        node.shutdown_pipeline()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()