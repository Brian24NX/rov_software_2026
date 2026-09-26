"""Receive capture JPEGs and return success only for a real COLMAP point cloud."""
from pathlib import Path
import uuid

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from interfaces.srv import RunReconstruction

from laptop.reconstruction import run_colmap


class ReconstructionService(Node):
    def __init__(self):
        super().__init__('reconstruction_service')
        self.output_root = Path(self.declare_parameter(
            'output_root', str(Path.home() / 'rov-reconstructions')).value)
        self.create_service(RunReconstruction, 'run_reconstruction', self.handle_request)
        self.get_logger().info('Reconstruction service ready (CPU COLMAP, sparse point cloud)')

    def handle_request(self, request, response):
        response.success, response.model_path = False, ''
        try:
            if not 3 <= len(request.images) <= 30:
                raise ValueError(
                    'Send 3–30 JPEG images; remote directory names are not local paths')
            if sum(len(image.data) for image in request.images) > 50 * 1024 * 1024:
                raise ValueError('Capture exceeds 50 MiB')
            job = self.output_root / uuid.uuid4().hex
            images = job / 'images'
            images.mkdir(parents=True)
            for index, image in enumerate(request.images):
                if not image.data or len(image.data) > 10 * 1024 * 1024:
                    raise ValueError('Invalid capture image size')
                frame = cv2.imdecode(np.frombuffer(image.data, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError(f'Invalid image {index}')
                if not cv2.imwrite(str(images / f'{index:03d}.jpg'), frame):
                    raise OSError('Could not save image')
            response.model_path = str(run_colmap(images, job))
            response.success = True
            response.message = 'Sparse point cloud generated; scale is not calibrated'
        except Exception as exc:
            response.message = str(exc)
            self.get_logger().error(f'Reconstruction failed: {exc}')
        return response


def main():
    rclpy.init()
    node = ReconstructionService()
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
