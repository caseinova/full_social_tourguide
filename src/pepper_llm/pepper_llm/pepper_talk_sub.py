#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import urllib.request
import qi

PEPPER_IP = "192.168.0.150"
PEPPER_PORT = 9559

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:1b"


class PepperLink(Node):
    def __init__(self):
        super().__init__('pepper_link')
        self.subscriber_ = self.create_subscription(String, '/speech_content',self.speak_callback_,10)
        print("Connecting to Pepper...")

        session = qi.Session()
        session.connect("tcp://{}:{}".format(PEPPER_IP, PEPPER_PORT))

        self.tts = session.service("ALTextToSpeech")
        motion = session.service("ALMotion")
        motion.wakeUp()
        self.tts.setLanguage("English")
        self.tts.setVolume(0.8)
        self.subscriber_

    def speak_callback_(self, msg):
        self.tts.say(msg.data)
        

def main(args=None):
    rclpy.init(args=args)
    minimal_subscriber = PepperLink()
    rclpy.spin(minimal_subscriber)
    minimal_subscriber.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

    


