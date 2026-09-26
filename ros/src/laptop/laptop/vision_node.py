"""Main/ZED video windows with stale-frame indication and an effective stop key."""
import os
import time

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String


class VisionNode(Node):
    def __init__(self):
        super().__init__('vision_node')
        self.show_video = self.declare_parameter(
            'show_video', bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
        ).value
        self.frames = {}
        self.create_subscription(CompressedImage, '/camera/image_compressed',
                                 self.claw_callback, qos_profile_sensor_data)
        self.create_subscription(CompressedImage,
                                 '/zed/zed_node/rgb/image_rect_color/compressed',
                                 self.zed_callback, qos_profile_sensor_data)
        self.command_publisher = self.create_publisher(String, 'commands', 10)
        self.create_timer(1.0 / 30.0, self._poll_keys)
        self.get_logger().info('Vision ready. Q or Escape disarms all seven channels.')

    def claw_callback(self, msg):
        self._receive('Main Camera (exploreHD)', msg)

    def zed_callback(self, msg):
        self._receive('ZED Camera', msg)

    def _receive(self, name, msg):
        frame = self._decode(msg)
        if frame is not None:
            self.frames[name] = (frame, time.monotonic())

    def _poll_keys(self):
        if not self.show_video:
            return
        for name, (frame, received) in self.frames.items():
            age = time.monotonic() - received
            display = frame.copy()
            if age > 1:
                cv2.putText(display, f'STALE: {age:.1f}s without video', (12, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow(name, display)
        self._handle_keys(cv2.waitKey(1) & 0xFF)

    def _decode(self, msg):
        try:
            frame = cv2.imdecode(np.frombuffer(msg.data, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                return frame
        except (cv2.error, ValueError):
            pass
        self.get_logger().warn('Dropped a corrupt camera frame', throttle_duration_sec=5.0)
        return None

    def _handle_keys(self, key):
        if key in (ord('q'), 27):
            self.send_command('disable_thrusters')

    def send_command(self, command):
        self.command_publisher.publish(String(data=command))
        self.get_logger().info(f'Sent command: {command}')

    def destroy_node(self):
        if rclpy.ok():
            self.send_command('disable_thrusters')
        if self.show_video:
            cv2.destroyAllWindows()
        super().destroy_node()


def main():
    rclpy.init()
    node = VisionNode()
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
