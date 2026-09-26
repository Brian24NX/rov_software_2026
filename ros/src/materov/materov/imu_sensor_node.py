"""ICM-20649 at +/-4g and +/-500 deg/s, published in ROS SI units."""
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import Imu

from materov.i2c_sensor import I2CSensorNode
from materov.sensor_math import decode_icm20649


class ImuSensorNode(I2CSensorNode):
    def __init__(self):
        super().__init__('imu_sensor_node', 0x68)
        self.pub = self.create_publisher(Imu, '/imu/data_raw', 10)
        self.create_timer(0.02, self.sample)

    def select_bank(self, bank):
        self.bus.write_byte_data(self.address, 0x7F, bank << 4)

    def initialize_sensor(self):
        self.select_bank(0)
        identity = self.bus.read_byte_data(self.address, 0x00)
        if identity != 0xE1:
            raise ValueError(f'Expected ICM-20649 WHO_AM_I=0xe1; got 0x{identity:02x}')
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
        acceleration, gyro = decode_icm20649(block)
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
