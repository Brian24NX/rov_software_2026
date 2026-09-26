"""ROS and serial adapter for the fail-closed motor state machine."""
import argparse
import json
import os
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Joy
from std_msgs.msg import String
import serial

from materov.control import ThrusterControl


class SignalPublisherNode(Node):
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, hz=100.0,
                 ramp_mode='sync', joy_timeout=0.5):
        super().__init__('signal_publisher')
        inhibited = self.declare_parameter(
            'inhibit_actuation', os.getenv('ROV_INHIBIT_ACTUATION', '0') == '1'
        ).value
        self.control = ThrusterControl(hz, ramp_mode, joy_timeout, inhibited)
        self._port, self._baudrate = port, baudrate
        self.ser = None
        self.last_request_id = ''
        self.last_command = ''
        self.status_pub = self.create_publisher(String, '/control/status', 10)
        self.create_subscription(Joy, 'joy', self.joy_callback, qos_profile_sensor_data)
        self.create_subscription(String, 'commands', self.command_callback, 10)
        self._retry_serial()
        self.create_timer(1.0 / hz, self.serial_timer_callback)
        self.create_timer(5.0, self._retry_serial)
        self.create_timer(0.2, self.publish_status)
        self.get_logger().info(
            f'Thrusters DISABLED; actuation inhibited={inhibited}; '
            f'joystick timeout={joy_timeout}s'
        )

    def command_callback(self, msg):
        command, request_id = msg.data.strip().lower(), ''
        if msg.data.lstrip().startswith('{'):
            try:
                envelope = json.loads(msg.data)
                command = str(envelope['command']).strip().lower()
                request_id = str(envelope.get('request_id', ''))
            except (ValueError, KeyError, TypeError):
                return
        if command not in ('enable_thrusters', 'disable_thrusters', 'stop'):
            return
        self.last_command, self.last_request_id = command, request_id
        if command == 'enable_thrusters':
            self.control.arm(time.monotonic(), self.ser is not None)
        else:
            self.control.disarm(command)
            self.serial_timer_callback()
        self.publish_status()
        self.get_logger().info(f'Control: {self.control.reason}; armed={self.control.armed}')

    def publish_status(self):
        state = self.control.status(time.monotonic(), self.ser is not None)
        state.update(command=self.last_command, request_id=self.last_request_id)
        self.status_pub.publish(String(data=json.dumps(state)))

    def _retry_serial(self):
        if self.ser is not None:
            return
        self.control.disarm('serial_reconnect')
        try:
            self.ser = serial.Serial(self._port, self._baudrate, timeout=0.01,
                                     write_timeout=0.05, exclusive=True)
            self.get_logger().info(f'Serial {self._port} connected; rearming required')
        except (OSError, serial.SerialException) as exc:
            self.get_logger().error(f'Serial unavailable: {exc}')
        self.publish_status()

    def _lose_serial(self, exc):
        self.control.disarm('serial_lost')
        if self.ser is not None:
            try:
                self.ser.close()
            except OSError:
                pass
        self.ser = None
        self.get_logger().error(f'Serial lost; disarmed: {exc}')
        if rclpy.ok():
            self.publish_status()

    def serial_timer_callback(self):
        frame = self.control.tick(time.monotonic())
        if self.ser is not None:
            try:
                if self.ser.write(frame) != len(frame):
                    raise serial.SerialTimeoutException('Incomplete serial frame')
            except (OSError, serial.SerialException) as exc:
                self._lose_serial(exc)

    def joy_callback(self, msg):
        self.control.update_joy(msg.axes, msg.buttons, time.monotonic())

    def destroy_node(self):
        self.control.disarm('shutdown')
        self.serial_timer_callback()
        if self.ser is not None:
            self.ser.close()
            self.ser = None
        super().destroy_node()


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='/dev/ttyUSB0')
    parser.add_argument('--baudrate', type=int, default=115200)
    parser.add_argument('--hz', type=float, default=100.0)
    parser.add_argument('--ramp_mode', choices=['sync', 'async'], default='sync')
    parser.add_argument('--joy_timeout', type=float, default=0.5)
    parser.add_argument('--direct_control', action='store_true', help=argparse.SUPPRESS)
    parsed, remaining = parser.parse_known_args(args)
    if parsed.direct_control:
        parser.error('Automatic arming was removed; use an explicit neutral arming request')
    rclpy.init(args=remaining)
    node = SignalPublisherNode(parsed.port, parsed.baudrate, parsed.hz,
                               parsed.ramp_mode, parsed.joy_timeout)
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
