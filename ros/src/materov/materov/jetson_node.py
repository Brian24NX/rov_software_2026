"""Bounded, non-destructive capture jobs and laptop reconstruction requests."""
from pathlib import Path
import json
import time
import uuid

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from interfaces.srv import RunReconstruction
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String


class JetsonNode(Node):
    def __init__(self):
        super().__init__('jetson_node')
        self.capture_root = Path(self.declare_parameter(
            'capture_root', str(Path.home() / 'shared/captures')).value)
        self.capture_target_count = 6
        self.capture_interval_s = 5.0
        self.latest_camera = None
        self.latest_camera_at = None
        self.capture_in_progress = False
        self.future = None
        self.images = []
        self.deadline = None
        self.next_capture = None
        self.client = self.create_client(RunReconstruction, 'run_reconstruction')
        self.status_pub = self.create_publisher(String, 'status', 10)
        self.create_subscription(String, 'commands', self.command_callback, 10)
        self.create_subscription(CompressedImage, '/camera/image_compressed',
                                 self.camera_image_callback, qos_profile_sensor_data)
        self.create_timer(0.25, self.capture_image_tick)

    def status(self, value):
        self.status_pub.publish(String(data=value))
        self.get_logger().info(value)

    def camera_image_callback(self, msg):
        if len(msg.data) > 10 * 1024 * 1024:
            return
        try:
            frame = cv2.imdecode(np.frombuffer(msg.data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                return
        except (cv2.error, ValueError):
            return
        self.latest_camera, self.latest_camera_at = msg, time.monotonic()

    def command_callback(self, msg):
        command = msg.data.strip().lower()
        if command.startswith('{'):
            try:
                command = str(json.loads(msg.data)['command']).strip().lower()
            except (ValueError, KeyError, TypeError):
                return
        if command == 'run_reconstruction':
            self.start_reconstruction_capture()
        elif command in ('forward', 'backward'):
            self.status('unsupported_command:' + command)
        # Motor commands belong to signal_publisher, which acknowledges them.

    def start_reconstruction_capture(self):
        if self.capture_in_progress or self.future is not None:
            self.status('reconstruction_busy')
            return
        if not self.client.service_is_ready():
            self.status('reconstruction_failed:service_unavailable')
            return
        try:
            self.capture_dir = self.capture_root / uuid.uuid4().hex
            self.capture_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            self.status(f'reconstruction_failed:capture_directory:{exc}')
            return
        self.images = []
        self.capture_in_progress = True
        self.next_capture = time.monotonic()
        self.deadline = self.next_capture + self.capture_target_count * self.capture_interval_s + 15
        self.status('reconstruction_started')
        self.capture_image_tick()

    def capture_image_tick(self):
        now = time.monotonic()
        if self.deadline is not None and now >= self.deadline:
            self.capture_in_progress = False
            future, self.future = self.future, None
            if future is not None:
                future.cancel()
            self.deadline = None
            self.status('reconstruction_failed:timeout')
            return
        if not self.capture_in_progress or now < self.next_capture:
            return
        if self.latest_camera_at is None or now - self.latest_camera_at > 1.0:
            return
        try:
            # Preserve the original JPEG; do not recompress or delete prior jobs.
            image = self.latest_camera
            (self.capture_dir / f'capture_{len(self.images):02d}.jpg').write_bytes(bytes(image.data))
            self.images.append(image)
        except OSError as exc:
            self.capture_in_progress = False
            self.deadline = None
            self.status(f'reconstruction_failed:save_image:{exc}')
            return
        self.next_capture = now + self.capture_interval_s
        if len(self.images) == self.capture_target_count:
            self.capture_in_progress = False
            self.status('capture_complete')
            self.send_reconstruction_request()

    def send_reconstruction_request(self):
        if not self.client.service_is_ready():
            self.deadline = None
            self.status('reconstruction_failed:service_unavailable')
            return
        request = RunReconstruction.Request()
        request.image_folder = str(self.capture_dir)
        request.images = self.images
        try:
            self.future = self.client.call_async(request)
            self.deadline = time.monotonic() + 660
            self.future.add_done_callback(self._on_reconstruction_response)
        except Exception as exc:
            self.future = None
            self.deadline = None
            self.status(f'reconstruction_failed:request:{exc}')

    def _on_reconstruction_response(self, future):
        if future is not self.future:
            return  # A canceled/timed-out job must not overwrite a newer job.
        self.future = None
        self.deadline = None
        try:
            response = future.result()
            self.status('reconstruction_done:' + response.model_path if response.success
                        else 'reconstruction_failed:' + response.message)
        except Exception as exc:
            self.status(f'reconstruction_failed:{exc}')


def main(args=None):
    rclpy.init(args=args)
    node = JetsonNode()
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
