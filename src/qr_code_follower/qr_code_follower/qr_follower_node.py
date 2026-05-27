import json
import math
from collections import deque
from typing import Optional

import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateThroughPoses
import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo
from sensor_msgs.msg import Image
from std_msgs.msg import String
from std_srvs.srv import SetBool
from tf2_ros import Buffer
from tf2_ros import TransformException
from tf2_ros import TransformListener


class QrFollower(Node):
    def __init__(self):
        super().__init__('qr_follower')

        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('alternate_image_topic', '/image')
        self.declare_parameter('camera_info_topic', '/camera/camera_info')
        self.declare_parameter('camera_frame_override', 'camera_rgb_optical_frame')
        self.declare_parameter('follow_command_topic', 'follow_command')
        self.declare_parameter('status_topic', '/qr_follower/status')
        self.declare_parameter('enabled', False)
        self.declare_parameter('follow_mode', 'pose')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('target_text', '')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('qr_size_m', 0.16)
        self.declare_parameter('pose_queue_size', 8)
        self.declare_parameter('pose_save_period', 0.5)
        self.declare_parameter('min_pose_separation', 0.05)
        self.declare_parameter('goal_offset_m', 0.45)
        self.declare_parameter('stop_range_m', 0.65)
        self.declare_parameter('min_follow_distance_m', 0.45)
        self.declare_parameter('direct_linear_gain', 0.45)
        self.declare_parameter('direct_angular_gain', 1.4)
        self.declare_parameter('direct_center_deadband_rad', 0.04)
        self.declare_parameter('direct_max_linear_speed', 0.14)
        self.declare_parameter('direct_max_angular_speed', 0.7)
        self.declare_parameter('direct_fallback_horizontal_fov_deg', 62.0)
        self.declare_parameter('direct_stop_confirm_frames', 3)
        self.declare_parameter('direct_command_timeout_sec', 0.5)
        self.declare_parameter('send_min_poses', 2)
        self.declare_parameter('action_name', 'navigate_through_poses')
        self.declare_parameter('no_target_log_period', 10.0)
        self.declare_parameter('no_image_log_period', 5.0)
        self.declare_parameter('qr_lost_grace_period', 1.0)
        self.declare_parameter('detection_scale', 1.5)
        self.declare_parameter('detection_scales', [1.0, 1.5, 2.0])
        self.declare_parameter('aggressive_preprocessing', True)
        self.declare_parameter('detector_eps_x', 0.5)
        self.declare_parameter('detector_eps_y', 0.5)
        self.declare_parameter('publish_debug_image', False)
        self.declare_parameter('debug_image_topic', '/qr_follower/debug_image')

        self.bridge = CvBridge()
        self.detector = cv2.QRCodeDetector()
        self.configure_detector()
        self.camera_matrix = None
        self.dist_coeffs = None
        self.latest_target = None
        self.latest_goal_pose = None
        self.last_image_time = None
        self.last_target_seen_time = None
        self.last_saved_time = None
        self.last_sent_signature = None
        self.target_visible = None
        self.last_no_target_log_time = None
        self.last_no_image_log_time = None
        self.last_direct_command_log_time = None
        self.last_direct_command_time = None
        self.direct_command_stop_sent = True
        self.direct_stop_counter = 0
        self.goal_handle = None
        self.active = self.enabled
        self.pose_queue = deque(maxlen=self.pose_queue_size)

        self.tf_buffer = None
        self.tf_listener = None
        self.nav_client = None
        if self.follow_mode == 'pose':
            self.tf_buffer = Buffer()
            self.tf_listener = TransformListener(self.tf_buffer, self)
            self.nav_client = ActionClient(
                self, NavigateThroughPoses, self.action_name)

        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.cmd_vel_pub = self.create_publisher(Twist, self.cmd_vel_topic, 10)
        self.debug_image_pub = None
        if self.publish_debug_image:
            self.debug_image_pub = self.create_publisher(
                Image, self.debug_image_topic, 10)

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            qos_profile_sensor_data)
        self.image_subscriptions = []
        for topic in self.image_topics:
            self.image_subscriptions.append(
                self.create_subscription(
                    Image, topic, self.image_callback, qos_profile_sensor_data))
        self.follow_command_sub = self.create_subscription(
            String, self.follow_command_topic, self.follow_command_callback, 10)
        self.enable_srv = self.create_service(
            SetBool, '/qr_follower/set_enabled', self.set_enabled_callback)
        self.timer = self.create_timer(0.2, self.behavior_timer_callback)
        self.direct_command_watchdog_timer = self.create_timer(
            0.05, self.direct_command_watchdog_callback)

        self.get_logger().info(
            'QR NavigateThroughPoses follower ready. '
            f'image_topics={self.image_topics} '
            f'camera_info_topic={self.camera_info_topic} '
            f'camera_frame_override={self.camera_frame_override} '
            f'follow_command_topic={self.follow_command_topic} '
            f'follow_mode={self.follow_mode} '
            f'active={self.active}')

    @property
    def image_topic(self):
        return self.get_parameter('image_topic').value

    @property
    def alternate_image_topic(self):
        return str(self.get_parameter('alternate_image_topic').value).strip()

    @property
    def image_topics(self):
        topics = [str(self.image_topic).strip(), self.alternate_image_topic]
        return [topic for index, topic in enumerate(topics)
                if topic and topic not in topics[:index]]

    @property
    def camera_info_topic(self):
        return self.get_parameter('camera_info_topic').value

    @property
    def camera_frame_override(self):
        return str(self.get_parameter('camera_frame_override').value).strip()

    @property
    def follow_command_topic(self):
        return self.get_parameter('follow_command_topic').value

    @property
    def status_topic(self):
        return self.get_parameter('status_topic').value

    @property
    def enabled(self):
        return self.as_bool(self.get_parameter('enabled').value)

    @property
    def follow_mode(self):
        return str(self.get_parameter('follow_mode').value).strip().lower()

    @property
    def cmd_vel_topic(self):
        return self.get_parameter('cmd_vel_topic').value

    @property
    def target_text(self):
        return str(self.get_parameter('target_text').value).strip()

    @property
    def global_frame(self):
        return self.get_parameter('global_frame').value

    @property
    def base_frame(self):
        return self.get_parameter('base_frame').value

    @property
    def qr_size_m(self):
        return float(self.get_parameter('qr_size_m').value)

    @property
    def pose_queue_size(self):
        return int(self.get_parameter('pose_queue_size').value)

    @property
    def pose_save_period(self):
        return float(self.get_parameter('pose_save_period').value)

    @property
    def min_pose_separation(self):
        return float(self.get_parameter('min_pose_separation').value)

    @property
    def goal_offset_m(self):
        return float(self.get_parameter('goal_offset_m').value)

    @property
    def stop_range_m(self):
        return float(self.get_parameter('stop_range_m').value)

    @property
    def min_follow_distance_m(self):
        return float(self.get_parameter('min_follow_distance_m').value)

    @property
    def direct_linear_gain(self):
        return float(self.get_parameter('direct_linear_gain').value)

    @property
    def direct_angular_gain(self):
        return float(self.get_parameter('direct_angular_gain').value)

    @property
    def direct_center_deadband_rad(self):
        return float(self.get_parameter('direct_center_deadband_rad').value)

    @property
    def direct_max_linear_speed(self):
        return float(self.get_parameter('direct_max_linear_speed').value)

    @property
    def direct_max_angular_speed(self):
        return float(self.get_parameter('direct_max_angular_speed').value)

    @property
    def direct_fallback_horizontal_fov_deg(self):
        return float(self.get_parameter('direct_fallback_horizontal_fov_deg').value)

    @property
    def direct_stop_confirm_frames(self):
        return int(self.get_parameter('direct_stop_confirm_frames').value)

    @property
    def direct_command_timeout_sec(self):
        return float(self.get_parameter('direct_command_timeout_sec').value)

    @property
    def send_min_poses(self):
        return int(self.get_parameter('send_min_poses').value)

    @property
    def action_name(self):
        return self.get_parameter('action_name').value

    @property
    def no_target_log_period(self):
        return float(self.get_parameter('no_target_log_period').value)

    @property
    def no_image_log_period(self):
        return float(self.get_parameter('no_image_log_period').value)

    @property
    def qr_lost_grace_period(self):
        return float(self.get_parameter('qr_lost_grace_period').value)

    @property
    def detection_scale(self):
        return float(self.get_parameter('detection_scale').value)

    @property
    def detection_scales(self):
        values = self.get_parameter('detection_scales').value
        if not values:
            return [self.detection_scale]
        return [max(0.1, float(value)) for value in values]

    @property
    def aggressive_preprocessing(self):
        return self.as_bool(self.get_parameter('aggressive_preprocessing').value)

    @property
    def detector_eps_x(self):
        return float(self.get_parameter('detector_eps_x').value)

    @property
    def detector_eps_y(self):
        return float(self.get_parameter('detector_eps_y').value)

    @property
    def publish_debug_image(self):
        return self.as_bool(self.get_parameter('publish_debug_image').value)

    @property
    def debug_image_topic(self):
        return self.get_parameter('debug_image_topic').value

    def camera_info_callback(self, msg):
        self.camera_matrix = np.array(msg.k, dtype=np.float64).reshape((3, 3))
        self.dist_coeffs = np.array(msg.d, dtype=np.float64)

    def follow_command_callback(self, msg):
        command = msg.data.strip().lower()
        if command in ('start', 'follow', 'true', '1', 'on', 'enable'):
            self.start_behavior('follow_command')
        elif command in ('stop', 'false', '0', 'off', 'disable', 'cancel'):
            self.stop_behavior('follow_command')
        else:
            self.get_logger().warning(
                f'Ignored follow_command="{msg.data}". Use start or stop.')

    def image_callback(self, msg):
        self.last_image_time = self.get_clock().now()

        if self.camera_matrix is None and self.follow_mode == 'pose':
            self.publish_status({
                'active': self.active,
                'follow_mode': self.follow_mode,
                'detected': False,
                'reason': 'waiting_for_camera_info',
            })
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as exc:
            self.get_logger().warning(f'Could not convert camera image: {exc}')
            return

        target = self.detect_qr(frame)
        if target is None:
            if self.active and self.follow_mode == 'direct':
                self.publish_stop()

            if self.target_recently_seen():
                reason = 'qr_target_temporarily_lost'
                if self.active and self.follow_mode == 'direct':
                    reason = 'direct_follow_paused_target_temporarily_lost'
                self.publish_status({
                    'active': self.active,
                    'follow_mode': self.follow_mode,
                    'detected': True,
                    'target_detected': True,
                    'reason': reason,
                    'queue_size': len(self.pose_queue),
                })
                self.publish_debug(frame)
                return

            self.log_no_target_detected()
            self.latest_target = None
            self.publish_status({
                'active': self.active,
                'follow_mode': self.follow_mode,
                'detected': False,
                'target_detected': False,
                'reason': 'no_qr_target_detected',
                'queue_size': len(self.pose_queue),
            })
            self.publish_debug(frame)
            return

        self.log_target_detected(target)
        self.last_target_seen_time = self.get_clock().now()
        if self.follow_mode == 'direct':
            self.handle_direct_follow(target, frame.shape[1])
            self.draw_debug(frame, target)
            self.publish_debug(frame)
            return

        pose = self.qr_pose_from_target(target, msg.header)
        if pose is None:
            self.latest_target = None
            self.publish_status({
                'active': self.active,
                'detected': True,
                'target_detected': True,
                'reason': 'qr_pose_estimation_failed',
                'queue_size': len(self.pose_queue),
            })
            self.publish_debug(frame)
            return

        goal_pose = self.offset_pose_from_qr(pose)
        if goal_pose is None:
            self.latest_target = None
            self.publish_status({
                'active': self.active,
                'detected': True,
                'target_detected': True,
                'reason': 'qr_goal_pose_failed',
                'queue_size': len(self.pose_queue),
            })
            self.publish_debug(frame)
            return

        distance = self.distance_to_base(pose)
        self.latest_target = {
            'text': target['text'],
            'qr_pose': pose,
            'goal_pose': goal_pose,
            'distance': distance,
        }
        self.latest_goal_pose = goal_pose

        if self.active:
            self.maybe_save_pose(goal_pose)

        self.publish_status({
            'active': self.active,
            'follow_mode': self.follow_mode,
            'detected': True,
            'target_detected': True,
            'text': target['text'],
            'distance_m': self.round_or_none(distance),
            'queue_size': len(self.pose_queue),
        })
        self.draw_debug(frame, target)
        self.publish_debug(frame)

    def behavior_timer_callback(self):
        if not self.active:
            return
        self.log_if_no_camera_images()
        if self.follow_mode != 'pose':
            return
        if self.nav_client is None:
            return

        target = self.latest_target
        if target is not None and target['distance'] is not None:
            if target['distance'] <= max(self.stop_range_m, self.min_follow_distance_m):
                self.stop_behavior('within_stop_range')
                return

        if len(self.pose_queue) < self.send_min_poses:
            return

        signature = self.pose_queue_signature()
        if signature == self.last_sent_signature:
            return

        if not self.nav_client.server_is_ready():
            if not self.nav_client.wait_for_server(timeout_sec=0.1):
                self.publish_status({
                    'active': self.active,
                    'detected': target is not None,
                    'queue_size': len(self.pose_queue),
                    'reason': 'waiting_for_nav2_action',
                })
                return

        self.send_navigation_goal(list(self.pose_queue), signature)

    def direct_command_watchdog_callback(self):
        if self.follow_mode != 'direct':
            return
        if self.last_direct_command_time is None or self.direct_command_stop_sent:
            return

        age = (
            self.get_clock().now() - self.last_direct_command_time
        ).nanoseconds / 1e9
        if age < self.direct_command_timeout_sec:
            return

        self.publish_stop()
        self.direct_command_stop_sent = True

    def log_if_no_camera_images(self):
        now = self.get_clock().now()
        if self.last_image_time is not None:
            image_age = (now - self.last_image_time).nanoseconds / 1e9
            if image_age <= self.no_image_log_period:
                return

        if self.last_no_image_log_time is not None:
            log_age = (now - self.last_no_image_log_time).nanoseconds / 1e9
            if log_age < self.no_image_log_period:
                return

        self.last_no_image_log_time = now
        self.get_logger().warning(
            f'No camera images received on {self.image_topics}. '
            'QR detection cannot run.')
        self.publish_status({
            'active': self.active,
            'follow_mode': self.follow_mode,
            'detected': False,
            'target_detected': False,
            'reason': 'waiting_for_camera_image',
            'image_topics': self.image_topics,
        })

    def handle_direct_follow(self, target, image_width):
        target_width_fraction = self.target_width_fraction_for_min_distance(
            image_width)
        width_error = target_width_fraction - target['width_fraction']
        angle_error = target['angle_error']
        estimated_distance = self.estimate_distance_from_width(
            target['width_px'], image_width)

        twist = Twist()
        if self.active:
            if abs(angle_error) > self.direct_center_deadband_rad:
                twist.angular.z = -self.direct_angular_gain * angle_error

            if width_error > 0.0:
                twist.linear.x = self.direct_linear_gain * width_error
                if abs(angle_error) > 0.35:
                    twist.linear.x *= 0.35

            twist.linear.x = self.clamp(
                twist.linear.x, 0.0, self.direct_max_linear_speed)
            twist.angular.z = self.clamp(
                twist.angular.z,
                -self.direct_max_angular_speed,
                self.direct_max_angular_speed)

            close_enough = target['width_fraction'] >= target_width_fraction
            if close_enough:
                self.direct_stop_counter += 1
            else:
                self.direct_stop_counter = 0

            if self.direct_stop_counter >= self.direct_stop_confirm_frames:
                twist = Twist()
                self.stop_behavior('within_min_follow_distance_by_qr_size')

            self.cmd_vel_pub.publish(twist)
            self.last_direct_command_time = self.get_clock().now()
            self.direct_command_stop_sent = False
            self.log_direct_command(twist, target, target_width_fraction,
                                    estimated_distance)
        else:
            self.log_direct_inactive()

        self.latest_target = {
            'text': target['text'],
            'distance': None,
            'estimated_distance': estimated_distance,
            'width_fraction': target['width_fraction'],
            'angle_error': angle_error,
        }
        self.publish_status({
            'active': self.active,
            'follow_mode': self.follow_mode,
            'detected': True,
            'target_detected': True,
            'text': target['text'],
            'angle_error_rad': round(angle_error, 3),
            'estimated_distance_m': self.round_or_none(estimated_distance),
            'width_fraction': round(target['width_fraction'], 3),
            'target_width_fraction': round(target_width_fraction, 3),
            'stop_counter': self.direct_stop_counter,
            'cmd_vel_topic': self.cmd_vel_topic,
            'linear_x': round(twist.linear.x, 3),
            'angular_z': round(twist.angular.z, 3),
            'reason': 'direct_follow',
        })

    def log_direct_command(self, twist, target, target_width_fraction,
                           estimated_distance):
        now = self.get_clock().now()
        if self.last_direct_command_log_time is not None:
            age = (now - self.last_direct_command_log_time).nanoseconds / 1e9
            if age < 1.0:
                return

        self.last_direct_command_log_time = now
        self.get_logger().info(
            'Direct QR cmd_vel: '
            f'topic={self.cmd_vel_topic} '
            f'linear_x={twist.linear.x:.3f} '
            f'angular_z={twist.angular.z:.3f} '
            f'width_fraction={target["width_fraction"]:.3f} '
            f'target_width_fraction={target_width_fraction:.3f} '
            f'estimated_distance_m={self.round_or_none(estimated_distance)} '
            f'stop_counter={self.direct_stop_counter}')

    def log_direct_inactive(self):
        now = self.get_clock().now()
        if self.last_direct_command_log_time is not None:
            age = (now - self.last_direct_command_log_time).nanoseconds / 1e9
            if age < 2.0:
                return

        self.last_direct_command_log_time = now
        self.get_logger().info(
            'QR detected, but direct follower is inactive. '
            'Publish "start" on follow_command to command /cmd_vel.')

    def detect_qr(self, frame) -> Optional[dict]:
        candidates = []
        _, image_width = frame.shape[:2]

        for detection_frame, scale in self.detection_frames(frame):
            decoded_info, points = self.detect_multi(detection_frame)

            if points is None or len(points) == 0:
                ok, single_points = self.detector.detect(detection_frame)
                if not ok or single_points is None or len(single_points) == 0:
                    continue
                decoded_info = ['']
                points = [single_points.reshape(-1, 2)]

            for index, qr_points in enumerate(points):
                text = ''
                if index < len(decoded_info) and decoded_info[index] is not None:
                    text = str(decoded_info[index])

                if self.target_text and text != self.target_text:
                    continue

                qr_points = qr_points.reshape(-1, 2).astype(np.float32) / scale
                x, y, width, height = cv2.boundingRect(qr_points)
                if width <= 0 or height <= 0:
                    continue
                center_x = x + width / 2.0

                candidates.append({
                    'text': text,
                    'points': qr_points,
                    'center_x': center_x,
                    'width_px': float(width),
                    'width_fraction': width / float(image_width),
                    'angle_error': self.pixel_angle_error(center_x, image_width),
                    'area': width * height,
                })

        if not candidates:
            return None

        return max(candidates, key=lambda candidate: candidate['area'])

    def detection_frames(self, frame):
        base_frames = [frame]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        base_frames.append(gray)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        clahe_gray = clahe.apply(gray)
        base_frames.append(clahe_gray)

        if self.aggressive_preprocessing:
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            sharpened = cv2.addWeighted(gray, 1.7, blurred, -0.7, 0)
            base_frames.append(sharpened)

            _, otsu = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            base_frames.append(otsu)
            base_frames.append(cv2.bitwise_not(otsu))

            adaptive = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                5,
            )
            base_frames.append(adaptive)
            base_frames.append(cv2.bitwise_not(adaptive))

            kernel = np.ones((3, 3), np.uint8)
            closed = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
            base_frames.append(closed)

        frames = []
        seen = set()
        for scale in self.detection_scales:
            for base_frame in base_frames:
                if scale == 1.0:
                    detection_frame = base_frame
                else:
                    detection_frame = cv2.resize(
                        base_frame,
                        None,
                        fx=scale,
                        fy=scale,
                        interpolation=cv2.INTER_CUBIC,
                    )

                key = (detection_frame.shape, detection_frame.dtype.str,
                       detection_frame.data.tobytes()[:64])
                if key in seen:
                    continue
                seen.add(key)
                frames.append((detection_frame, scale))

        return frames

    def detect_multi(self, frame):
        try:
            ok, points = self.detector.detectMulti(frame)
        except cv2.error:
            return [], None

        if not ok:
            return [], None

        decoded_info = [''] * len(points)
        return decoded_info, points

    def configure_detector(self):
        if hasattr(self.detector, 'setEpsX'):
            self.detector.setEpsX(self.detector_eps_x)
        if hasattr(self.detector, 'setEpsY'):
            self.detector.setEpsY(self.detector_eps_y)

    def target_recently_seen(self):
        if self.last_target_seen_time is None:
            return False

        age = (
            self.get_clock().now() - self.last_target_seen_time
        ).nanoseconds / 1e9
        return age <= self.qr_lost_grace_period

    def qr_pose_from_target(self, target, header) -> Optional[PoseStamped]:
        if self.tf_buffer is None:
            return None

        half = self.qr_size_m / 2.0
        object_points = np.array([
            [-half, -half, 0.0],
            [half, -half, 0.0],
            [half, half, 0.0],
            [-half, half, 0.0],
        ], dtype=np.float32)

        image_points = self.order_qr_points(target['points'])
        if image_points is None:
            return None

        ok, _, translation = cv2.solvePnP(
            object_points,
            image_points,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )
        if not ok:
            return None
        if not np.all(np.isfinite(translation)):
            self.get_logger().warning('Rejected QR pose: solvePnP returned non-finite translation.')
            return None

        camera_frame = self.camera_frame_override or header.frame_id
        if not camera_frame:
            self.get_logger().warning(
                'Image header has no frame_id and camera_frame_override is empty.')
            return None

        try:
            transform = self.tf_buffer.lookup_transform(
                self.global_frame,
                camera_frame,
                rclpy.time.Time())
        except TransformException as exc:
            self.get_logger().warning(
                f'Could not transform QR pose from {camera_frame} '
                f'to {self.global_frame}: {exc}')
            return None

        point_camera = (
            float(translation[0][0]),
            float(translation[1][0]),
            float(translation[2][0]),
        )
        if not self.values_are_finite(point_camera):
            self.get_logger().warning(f'Rejected QR pose: invalid camera point {point_camera}.')
            return None

        point_global = self.transform_point(point_camera, transform.transform)
        if not self.values_are_finite(point_global):
            self.get_logger().warning(f'Rejected QR pose: invalid map point {point_global}.')
            return None

        pose = PoseStamped()
        pose.header.frame_id = self.global_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = point_global[0]
        pose.pose.position.y = point_global[1]
        pose.pose.position.z = point_global[2]
        pose.pose.orientation.w = 1.0
        if not self.pose_is_finite(pose):
            self.get_logger().warning('Rejected QR pose: generated pose contains non-finite values.')
            return None
        return pose

    def offset_pose_from_qr(self, qr_pose) -> Optional[PoseStamped]:
        if not self.pose_is_finite(qr_pose):
            self.get_logger().warning('Rejected QR goal: QR pose contains non-finite values.')
            return None

        base_pose = self.base_pose()
        if base_pose is None:
            return None
        if not self.pose_is_finite(base_pose):
            self.get_logger().warning('Rejected QR goal: base pose contains non-finite values.')
            return None

        qr_x = qr_pose.pose.position.x
        qr_y = qr_pose.pose.position.y
        base_x = base_pose.pose.position.x
        base_y = base_pose.pose.position.y

        dx = qr_x - base_x
        dy = qr_y - base_y
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance) or distance < 1e-6:
            self.get_logger().warning(
                f'Rejected QR goal: invalid distance to QR ({distance}).')
            return None

        offset = min(self.goal_offset_m, max(0.0, distance - 0.05))
        goal_x = qr_x - (dx / distance) * offset
        goal_y = qr_y - (dy / distance) * offset
        yaw = math.atan2(qr_y - goal_y, qr_x - goal_x)
        if not self.values_are_finite((goal_x, goal_y, yaw)):
            self.get_logger().warning(
                f'Rejected QR goal: invalid goal geometry x={goal_x}, y={goal_y}, yaw={yaw}.')
            return None

        goal = PoseStamped()
        goal.header.frame_id = self.global_frame
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = goal_x
        goal.pose.position.y = goal_y
        goal.pose.position.z = 0.0
        goal.pose.orientation = self.yaw_to_quaternion(yaw)
        if not self.pose_is_finite(goal):
            self.get_logger().warning('Rejected QR goal: generated goal contains non-finite values.')
            return None
        return goal

    def maybe_save_pose(self, pose):
        if not self.pose_is_finite(pose):
            self.get_logger().warning('Skipped QR goal queue insert: pose contains non-finite values.')
            return

        now = self.get_clock().now()
        if self.last_saved_time is not None:
            age = (now - self.last_saved_time).nanoseconds / 1e9
            if age < self.pose_save_period:
                return

        if self.pose_queue:
            last_pose = self.pose_queue[-1]
            distance = self.distance_between_poses(last_pose, pose)
            if not math.isfinite(distance):
                self.get_logger().warning('Skipped QR goal queue insert: distance check is non-finite.')
                return
            if distance < self.min_pose_separation:
                return

        pose.header.stamp = now.to_msg()
        self.pose_queue.append(pose)
        self.last_saved_time = now

    def send_navigation_goal(self, poses, signature):
        if self.follow_mode != 'pose':
            return
        if self.nav_client is None:
            return

        poses = [pose for pose in poses if self.pose_is_finite(pose)]
        if len(poses) < self.send_min_poses:
            self.last_sent_signature = None
            self.publish_status({
                'active': self.active,
                'detected': self.latest_target is not None,
                'queue_size': len(self.pose_queue),
                'reason': 'not_enough_valid_nav_poses',
            })
            return

        if self.goal_handle is not None:
            self.goal_handle.cancel_goal_async()

        goal = NavigateThroughPoses.Goal()
        goal.poses = poses
        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(
            lambda done_future: self.navigation_goal_response(
                done_future, signature))
        self.last_sent_signature = signature
        self.publish_status({
            'active': self.active,
            'detected': self.latest_target is not None,
            'queue_size': len(self.pose_queue),
            'reason': 'sent_nav_goal',
        })

    def navigation_goal_response(self, future, signature):
        goal_handle = future.result()
        if self.follow_mode != 'pose' or not self.active:
            if goal_handle.accepted:
                goal_handle.cancel_goal_async()
            self.goal_handle = None
            return

        if not goal_handle.accepted:
            self.goal_handle = None
            self.last_sent_signature = None
            self.publish_status({
                'active': self.active,
                'reason': 'nav_goal_rejected',
                'signature': signature,
            })
            return

        self.goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.navigation_result)

    def navigation_result(self, future):
        if self.follow_mode != 'pose':
            self.goal_handle = None
            return

        self.goal_handle = None
        status = future.result().status
        self.publish_status({
            'active': self.active,
            'reason': 'nav_goal_finished',
            'status': status,
        })

    def log_no_target_detected(self):
        now = self.get_clock().now()
        should_log = False

        if self.target_visible is not False:
            should_log = True
        elif self.last_no_target_log_time is None:
            should_log = True
        else:
            age = (now - self.last_no_target_log_time).nanoseconds / 1e9
            should_log = age >= self.no_target_log_period

        self.target_visible = False
        if should_log:
            self.last_no_target_log_time = now
            self.get_logger().info('No QR target detected in camera feed.')

    def log_target_detected(self, target):
        if self.target_visible is not True:
            label = target['text'] if target['text'] else '<undecoded>'
            self.get_logger().info(f'QR target detected: {label}')
        self.target_visible = True
        self.last_no_target_log_time = None

    def start_behavior(self, reason):
        if not self.active:
            self.get_logger().info(f'Starting QR follow behavior: {reason}')
        self.active = True
        self.set_parameters([
            Parameter('enabled', Parameter.Type.BOOL, True)
        ])
        self.pose_queue.clear()
        self.last_saved_time = None
        self.last_sent_signature = None
        self.direct_stop_counter = 0
        self.last_direct_command_time = None
        self.direct_command_stop_sent = True
        if self.follow_mode == 'direct' and self.goal_handle is not None:
            self.goal_handle.cancel_goal_async()
            self.goal_handle = None
        if self.follow_mode == 'pose' and self.latest_goal_pose is not None:
            self.maybe_save_pose(self.latest_goal_pose)
        self.publish_status({
            'active': True,
            'reason': reason,
            'queue_size': len(self.pose_queue),
        })

    def stop_behavior(self, reason):
        if self.active:
            self.get_logger().info(f'Stopping QR follow behavior: {reason}')
        self.active = False
        self.set_parameters([
            Parameter('enabled', Parameter.Type.BOOL, False)
        ])
        self.pose_queue.clear()
        self.last_saved_time = None
        self.last_sent_signature = None
        self.direct_stop_counter = 0
        self.last_direct_command_time = None
        self.direct_command_stop_sent = True
        if self.goal_handle is not None:
            self.goal_handle.cancel_goal_async()
            self.goal_handle = None
        self.publish_status({
            'active': False,
            'reason': reason,
            'queue_size': 0,
        })
        if self.follow_mode == 'direct':
            self.publish_stop()

    def set_enabled_callback(self, request, response):
        if request.data:
            self.start_behavior('service_request')
        else:
            self.stop_behavior('service_request')

        response.success = True
        response.message = f'QR follower active={bool(request.data)}'
        return response

    def base_pose(self) -> Optional[PoseStamped]:
        if self.tf_buffer is None:
            return None

        try:
            transform = self.tf_buffer.lookup_transform(
                self.global_frame,
                self.base_frame,
                rclpy.time.Time())
        except TransformException:
            return None

        pose = PoseStamped()
        pose.header.frame_id = self.global_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = transform.transform.translation.x
        pose.pose.position.y = transform.transform.translation.y
        pose.pose.position.z = transform.transform.translation.z
        pose.pose.orientation = transform.transform.rotation
        if not self.pose_is_finite(pose):
            return None
        return pose

    def distance_to_base(self, pose) -> Optional[float]:
        base_pose = self.base_pose()
        if base_pose is None:
            return None
        return self.distance_between_poses(base_pose, pose)

    def pose_queue_signature(self):
        return tuple(
            (
                round(pose.pose.position.x, 2),
                round(pose.pose.position.y, 2),
            )
            for pose in self.pose_queue
        )

    def publish_status(self, payload):
        msg = String()
        msg.data = json.dumps(payload)
        self.status_pub.publish(msg)

    def publish_stop(self):
        self.cmd_vel_pub.publish(Twist())
        if self.follow_mode == 'direct':
            self.direct_command_stop_sent = True

    def draw_debug(self, frame, target):
        points = target['points'].astype('int32')
        cv2.polylines(frame, [points], isClosed=True, color=(0, 255, 0),
                      thickness=2)
        if target['text']:
            cv2.putText(frame, target['text'], tuple(points[0]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    def publish_debug(self, frame):
        if self.debug_image_pub is None:
            return

        try:
            self.debug_image_pub.publish(
                self.bridge.cv2_to_imgmsg(frame, encoding='bgr8'))
        except Exception as exc:
            self.get_logger().warning(f'Could not publish debug image: {exc}')

    @staticmethod
    def order_qr_points(points):
        if points is None or len(points) != 4:
            return None

        points = points.astype(np.float32)
        sums = points.sum(axis=1)
        diffs = np.diff(points, axis=1).reshape(-1)

        top_left = points[np.argmin(sums)]
        bottom_right = points[np.argmax(sums)]
        top_right = points[np.argmin(diffs)]
        bottom_left = points[np.argmax(diffs)]
        return np.array(
            [top_left, top_right, bottom_right, bottom_left],
            dtype=np.float32)

    @staticmethod
    def transform_point(point, transform):
        rotated = QrFollower.rotate_vector(point, transform.rotation)
        return (
            rotated[0] + transform.translation.x,
            rotated[1] + transform.translation.y,
            rotated[2] + transform.translation.z,
        )

    @staticmethod
    def rotate_vector(vector, quat):
        x, y, z = vector
        qx = quat.x
        qy = quat.y
        qz = quat.z
        qw = quat.w

        tx = 2.0 * (qy * z - qz * y)
        ty = 2.0 * (qz * x - qx * z)
        tz = 2.0 * (qx * y - qy * x)

        return (
            x + qw * tx + (qy * tz - qz * ty),
            y + qw * ty + (qz * tx - qx * tz),
            z + qw * tz + (qx * ty - qy * tx),
        )

    @staticmethod
    def yaw_to_quaternion(yaw):
        quat = PoseStamped().pose.orientation
        quat.z = math.sin(yaw / 2.0)
        quat.w = math.cos(yaw / 2.0)
        return quat

    @staticmethod
    def distance_between_poses(first, second):
        dx = first.pose.position.x - second.pose.position.x
        dy = first.pose.position.y - second.pose.position.y
        return math.hypot(dx, dy)

    def pixel_angle_error(self, center_x, image_width):
        if self.camera_matrix is None:
            fallback_fov = math.radians(self.direct_fallback_horizontal_fov_deg)
            if image_width <= 0 or not math.isfinite(fallback_fov):
                return 0.0
            normalized_error = (center_x - image_width / 2.0) / (image_width / 2.0)
            return normalized_error * (fallback_fov / 2.0)

        fx = float(self.camera_matrix[0, 0])
        cx = float(self.camera_matrix[0, 2])
        if not self.values_are_finite((fx, cx)) or abs(fx) < 1e-6:
            return 0.0
        return math.atan2(center_x - cx, fx)

    def target_width_fraction_for_min_distance(self, image_width):
        if self.camera_matrix is None:
            fx = self.fallback_focal_length_px(image_width)
        else:
            fx = self.valid_focal_length_or_fallback(image_width)

        min_distance = max(self.min_follow_distance_m, 1e-3)
        if not self.values_are_finite((fx, min_distance, image_width)) or image_width <= 0:
            return 1.0

        target_width_px = fx * self.qr_size_m / min_distance
        return self.clamp(target_width_px / float(image_width), 0.02, 0.95)

    def estimate_distance_from_width(self, width_px, image_width):
        if width_px <= 0:
            return None

        if self.camera_matrix is None:
            fx = self.fallback_focal_length_px(image_width)
        else:
            fx = self.valid_focal_length_or_fallback(image_width)

        if not self.values_are_finite((fx, width_px)) or fx <= 0.0:
            return None
        return fx * self.qr_size_m / float(width_px)

    def valid_focal_length_or_fallback(self, image_width):
        fx = float(self.camera_matrix[0, 0])
        if self.values_are_finite((fx,)) and fx > 1.0:
            return fx

        return self.fallback_focal_length_px(image_width)

    def fallback_focal_length_px(self, image_width):
        fallback_fov = math.radians(self.direct_fallback_horizontal_fov_deg)
        if image_width <= 0 or not math.isfinite(fallback_fov):
            return 0.0
        return (image_width / 2.0) / math.tan(max(fallback_fov, 1e-3) / 2.0)

    @staticmethod
    def clamp(value, lower, upper):
        return max(lower, min(upper, value))

    @staticmethod
    def values_are_finite(values):
        return all(math.isfinite(float(value)) for value in values)

    @staticmethod
    def pose_is_finite(pose):
        return QrFollower.values_are_finite((
            pose.pose.position.x,
            pose.pose.position.y,
            pose.pose.position.z,
            pose.pose.orientation.x,
            pose.pose.orientation.y,
            pose.pose.orientation.z,
            pose.pose.orientation.w,
        ))

    @staticmethod
    def round_or_none(value):
        if value is None:
            return None
        return round(value, 3)

    @staticmethod
    def as_bool(value):
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(value)


def main(args=None):
    rclpy.init(args=args)
    node = QrFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.goal_handle is not None:
            node.goal_handle.cancel_goal_async()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
