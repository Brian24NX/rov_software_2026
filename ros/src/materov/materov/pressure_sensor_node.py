"""MS5837 absolute pressure (mbar); never infer depth without calibration."""
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import Float32

from materov.i2c_sensor import I2CSensorNode
from materov.sensor_math import compensate_ms5837, validate_prom


class PressureSensorNode(I2CSensorNode):
    def __init__(self):
        super().__init__('pressure_sensor_node', 0x76)
        self.model = self.declare_parameter('pressure_model', '30BA').value
        if self.model not in ('30BA', '02BA'):
            raise ValueError('pressure_model must be 30BA or 02BA')
        self.pub = self.create_publisher(Float32, '/pressure/data_raw', 10)
        self.temperature_pub = self.create_publisher(Float32, '/pressure/temperature', 10)
        self.create_timer(0.1, self.sample)

    def initialize_sensor(self):
        self.bus.write_byte(self.address, 0x1E)
        time.sleep(0.01)
        self.calibration = []
        for i in range(7):
            word = self.bus.read_word_data(self.address, 0xA0 + i * 2)
            self.calibration.append(((word & 255) << 8) | (word >> 8))
        validate_prom(self.calibration)

    def read_adc(self, command):
        self.bus.write_byte(self.address, command)
        time.sleep(0.02)  # OSR4096 maximum conversion time plus margin.
        data = self.bus.read_i2c_block_data(self.address, 0x00, 3)
        if len(data) != 3:
            raise ValueError('Incomplete pressure conversion')
        return int.from_bytes(bytes(data), 'big')

    def publish_sample(self):
        pressure, temperature = compensate_ms5837(
            self.calibration, self.read_adc(0x48), self.read_adc(0x58), self.model
        )
        self.pub.publish(Float32(data=pressure))
        self.temperature_pub.publish(Float32(data=temperature))


def main(args=None):
    rclpy.init(args=args)
    node = PressureSensorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
