"""Recover an unavailable I2C device without publishing fabricated measurements."""
import time

from rclpy.node import Node
import smbus


class I2CSensorNode(Node):
    def __init__(self, name, default_address):
        super().__init__(name)
        self.bus_id = self.declare_parameter('i2c_bus', 7).value
        self.address = self.declare_parameter('i2c_address', default_address).value
        self.bus = None
        self.retry_at = 0.0

    def sample(self):
        if time.monotonic() < self.retry_at:
            return
        try:
            if self.bus is None:
                self.bus = smbus.SMBus(self.bus_id)
                self.initialize_sensor()
                self.get_logger().info(f'Sensor connected: I2C-{self.bus_id}, 0x{self.address:02x}')
            self.publish_sample()
        except (OSError, ValueError) as exc:
            self.get_logger().error(f'Sensor unavailable; retry in 5s: {exc}')
            self.close_bus()
            self.retry_at = time.monotonic() + 5.0

    def close_bus(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except OSError:
                pass
            self.bus = None

    def destroy_node(self):
        self.close_bus()
        super().destroy_node()
