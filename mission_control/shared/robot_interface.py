"""API-facing bridge; connection means a recent vehicle control heartbeat."""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any


class RobotInterface:
    def __init__(self) -> None:
        self._controller = None
        self._lock = threading.Lock()

    def _get_controller(self):
        with self._lock:
            if self._controller is None:
                package = str(Path(__file__).resolve().parents[2] / 'ros/src/laptop')
                if package not in sys.path:
                    sys.path.insert(0, package)
                try:
                    from laptop.laptop_controller import LaptopController
                    self._controller = LaptopController()
                except Exception as exc:
                    # Do not cache failures permanently: setup/network can recover.
                    raise RuntimeError(f'ROS controller unavailable: {exc}') from exc
            return self._controller

    def run_task(self, task_id: str) -> dict[str, Any]:
        raise NotImplementedError('Automated task execution is not implemented; use the task instructions')

    def send_images(self, task_id: str, image_paths: list[str]) -> dict[str, Any]:
        raise NotImplementedError('Image transfer through send_images is not implemented; uploads are stored on the laptop')

    def run_reconstruction(self, task_id: str, image_paths: list[str]) -> dict[str, Any]:
        if image_paths:
            raise ValueError('This command captures new ROV images; uploaded paths are not accepted')
        controller = self._get_controller()
        if not controller.get_status()['connected']:
            raise RuntimeError('Vehicle is not connected')
        result = controller.send_command('run_reconstruction')
        return {'ok': True, 'task_id': task_id, **result}

    def set_thrusters(self, enabled: bool) -> dict[str, Any]:
        command = 'enable_thrusters' if enabled else 'disable_thrusters'
        result = self._get_controller().send_command(command)
        return {'ok': True, 'enabled': enabled, **result}

    def get_status(self) -> dict[str, Any]:
        try:
            return self._get_controller().get_status()
        except RuntimeError as exc:
            return {'ok': False, 'connected': False, 'control': None,
                    'mode': 'ros2', 'detail': str(exc)}

    def close(self):
        with self._lock:
            if self._controller is not None:
                self._controller.close()
                self._controller = None
