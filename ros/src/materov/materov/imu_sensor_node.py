"""ICM-20649 or ICM-20948 accel/gyro, published in ROS SI units.

Both parts are in service on different vehicles. They share a register layout
but report different WHO_AM_I values and, at the same FS_SEL, different
full-scale ranges - so the part is detected at init and its scale factors are
selected from that, rather than assumed.
"""
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import Imu

from materov.i2c_sensor import I2CSensorNode
from materov.sensor_math import ICM20649_WHO_AM_I, ICM20948_WHO_AM_I, decode_icm

_PART_NAMES = {ICM20649_WHO_AM_I: 'ICM-20649', ICM20948_WHO_AM_I: 'ICM-20948'}


class ImuSensorNode(I2CSensorNode):
    def __init__(self):
        super().__init__('imu_sensor_node', 0x68)
        self.who_am_i = None
        self.pub = self.create_publisher(Imu, '/imu/data_raw', 10)
        self.create_timer(0.02, self.sample)

    def select_bank(self, bank):
        self.bus.write_byte_data(self.address, 0x7F, bank << 4)

    def initialize_sensor(self):
        self.select_bank(0)
        identity = self.bus.read_byte_data(self.address, 0x00)
        if identity not in _PART_NAMES:
            raise ValueError(
                'Expected ICM-20649 WHO_AM_I=0xe1 or ICM-20948 WHO_AM_I=0xea; '
                f'got 0x{identity:02x}')
        self.who_am_i = identity
        self.get_logger().info(f'{_PART_NAMES[identity]} detected at 0x{self.address:02x}')
        self.bus.write_byte_data(self.address, 0x05, 0)
        self.bus.write_byte_data(self.address, 0x06, 1)
        self.bus.write_byte_data(self.address, 0x07, 0)
        time.sleep(0.05)
        self.select_bank(2)
        for register, value in ((0x00, 19), (0x10, 0), (0x11, 19),
                                (0x01, 0x01), (0x14, 0x01)):
            self.bus.write_byte_data(self.address, register, value)
        self.select_bank(0)

    def publish_sample(self):
        block = self.bus.read_i2c_block_data(self.address, 0x2D, 12)
        acceleration, gyro = decode_icm(block, self.who_am_i)
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'imu_link'
        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = acceleration
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = gyro
        msg.orientation_covariance[0] = -1.0
        # Zero covariances denote unknown, pending physical calibration.
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ImuSensorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
