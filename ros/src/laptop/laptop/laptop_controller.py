"""Thread-safe command bridge with a private ROS context and live acknowledgments."""
import json
import threading
import time
import uuid


class LaptopController:
    def __init__(self):
        import rclpy
        from rclpy.context import Context
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import CompressedImage, Imu
        from std_msgs.msg import Float32, String

        self._rclpy = rclpy
        self._context = Context()
        self._lock = threading.Condition()
        self._commands_lock = threading.Lock()
        self._state = {}
        self._state_at = None
        self._observed = {}
        self._mission = None
        self._closed = False
        rclpy.init(context=self._context)
        self.node = None
        try:
            self.node = Node('laptop_controller', context=self._context)
            self.command_publisher = self.node.create_publisher(String, 'commands', 10)
            self.node.create_subscription(String, '/control/status', self._on_state, 10)
            self.node.create_subscription(String, '/status', self._on_mission, 10)
            for topic, kind, key in (
                ('/camera/image_compressed', CompressedImage, 'camera'),
                ('/zed/zed_node/rgb/image_rect_color/compressed', CompressedImage, 'zed'),
                ('/imu/data_raw', Imu, 'imu'),
                ('/pressure/data_raw', Float32, 'pressure'),
            ):
                self.node.create_subscription(
                    kind, topic, lambda msg, name=key: self._mark_seen(name),
                    qos_profile_sensor_data)
            self._executor = SingleThreadedExecutor(context=self._context)
            self._executor.add_node(self.node)
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        except Exception:
            if self.node is not None:
                self.node.destroy_node()
            self._context.try_shutdown()
            raise

    def _spin(self):
        from rclpy.executors import ExternalShutdownException
        try:
            self._executor.spin()
        except ExternalShutdownException:
            pass

    def _mark_seen(self, name):
        with self._lock:
            self._observed[name] = time.monotonic()

    def _on_state(self, msg):
        try:
            state = json.loads(msg.data)
            if not isinstance(state, dict) or not isinstance(state.get('armed'), bool):
                return
        except (ValueError, TypeError):
            return
        with self._lock:
            self._state, self._state_at = state, time.monotonic()
            self._lock.notify_all()

    def _on_mission(self, msg):
        with self._lock:
            self._mission = msg.data

    def get_status(self):
        now = time.monotonic()
        with self._lock:
            age = None if self._state_at is None else now - self._state_at
            connected = not self._closed and age is not None and age < 2.0
            return {'ok': True, 'mode': 'ros2', 'connected': connected,
                    'control': dict(self._state) if connected else None,
                    'control_age_s': age, 'mission_status': self._mission,
                    'sensors': {key: now - value for key, value in self._observed.items()},
                    'detail': ('Vehicle heartbeat received' if connected
                               else 'No fresh vehicle heartbeat')}

    def send_command(self, command, timeout=3.0):
        from std_msgs.msg import String

        with self._commands_lock:
            if self._closed:
                raise RuntimeError('ROS controller is closed')
            deadline = time.monotonic() + timeout
            while self.command_publisher.get_subscription_count() == 0:
                if time.monotonic() >= deadline:
                    raise RuntimeError('No vehicle command subscriber discovered')
                time.sleep(0.05)
            controlled = command in ('enable_thrusters', 'disable_thrusters', 'stop')
            if not controlled:
                self.command_publisher.publish(String(data=command))
                return {'acknowledged': False,
                        'message': 'Command published; completion is on /status'}
            request_id = uuid.uuid4().hex
            self.command_publisher.publish(String(data=json.dumps(
                {'command': command, 'request_id': request_id})))
            with self._lock:
                while self._state.get('request_id') != request_id:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError('Vehicle did not acknowledge control command')
                    self._lock.wait(remaining)
                state = dict(self._state)
            if command == 'enable_thrusters' and not state['armed']:
                raise RuntimeError(f"Arming rejected: {state.get('reason', 'unknown')}")
            if command != 'enable_thrusters' and state['armed']:
                raise RuntimeError('Vehicle did not confirm disarm')
            return {'acknowledged': True, 'control': state}

    def close(self):
        if self._closed:
            return
        try:
            self.send_command('disable_thrusters', timeout=1.0)
        except Exception:
            pass
        self._closed = True
        self._executor.shutdown(timeout_sec=2)
        self._context.try_shutdown()
        self._thread.join(timeout=2)
        self.node.destroy_node()
