"""USB camera streaming with discovery and reconnection after capture failure."""
from pathlib import Path
import time

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image


def camera_candidates():
    candidates = []
    for name_file in Path('/sys/class/video4linux').glob('video*/name'):
        try:
            name = name_file.read_text().lower()
            if 'zed' not in name:
                candidates.append(('explorehd' not in name,
                                   int(name_file.parent.name.removeprefix('video'))))
        except (OSError, ValueError):
            continue
    return [index for _, index in sorted(candidates)]


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.device = self.declare_parameter('device', 'auto').value
        self.bridge = CvBridge()
        self.cap = None
        self.retry_at = 0.0
        self.failures = 0
        self.pub_compressed = self.create_publisher(
            CompressedImage, '/camera/image_compressed', qos_profile_sensor_data)
        self.pub_raw = self.create_publisher(Image, '/camera/image_raw', qos_profile_sensor_data)
        self.create_timer(1.0 / 30.0, self.publish_frame)

    def open_camera(self):
        self.retry_at = time.monotonic() + 5.0
        devices = camera_candidates() if self.device == 'auto' else [self.device]
        for device in devices:
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ret, frame = cap.read()
                if ret and frame is not None:
                    self.cap = cap
                    self.failures = 0
                    self.get_logger().info(f'Camera connected: {device}, shape={frame.shape}')
                    return
            cap.release()
        self.get_logger().warn('Camera unavailable; retrying discovery in 5s')

    def publish_frame(self):
        if self.cap is None:
            if time.monotonic() >= self.retry_at:
                self.open_camera()
            return
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise ValueError('No camera frame')
            self.failures = 0
            stamp = self.get_clock().now().to_msg()
            ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise ValueError('JPEG encoding failed')
            msg = CompressedImage()
            msg.header.stamp, msg.header.frame_id = stamp, 'camera'
            msg.format, msg.data = 'jpeg', buf.tobytes()
            self.pub_compressed.publish(msg)
            if self.pub_raw.get_subscription_count():
                raw = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
                raw.header = msg.header
                self.pub_raw.publish(raw)
        except (cv2.error, ValueError) as exc:
            self.failures += 1
            if self.failures >= 5:
                self.get_logger().warn(f'Camera lost; reconnecting: {exc}')
                self.cap.release()
                self.cap = None
                self.retry_at = time.monotonic() + 1.0

    def destroy_node(self):
        if self.cap is not None:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
