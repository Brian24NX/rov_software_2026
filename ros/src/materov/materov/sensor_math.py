"""Datasheet conversions, independent of I2C/ROS for regression testing.

ICM-20649: TDK DS-000192 v1.1, tables 1/2 (FS_SEL=0).
MS5837: TE 30BA/02BA second-order compensation and PROM CRC-4.
Reference: https://github.com/bluerobotics/ms5837-python
"""
import math
import struct


def decode_icm20649(block):
    if len(block) != 12:
        raise ValueError('ICM-20649 requires one 12-byte burst')
    raw = struct.unpack('>6h', bytes(block))
    return ([v * 9.80665 / 8192.0 for v in raw[:3]],
            [math.radians(v / 65.5) for v in raw[3:]])


def prom_crc4(words):
    if len(words) != 7:
        raise ValueError('Expected seven PROM words')
    data = list(words) + [0]
    data[0] &= 0x0FFF
    remainder = 0
    for index in range(16):
        word = data[index // 2]
        remainder ^= (word & 255) if index % 2 else (word >> 8)
        for _ in range(8):
            remainder = ((remainder << 1) ^ (0x3000 if remainder & 0x8000 else 0)) & 0xFFFF
    return (remainder >> 12) & 15


def validate_prom(words):
    if len(words) != 7 or any(not 0 <= v <= 65535 for v in words):
        raise ValueError('Invalid PROM length or word')
    if not all(v not in (0, 65535) for v in words[1:]):
        raise ValueError('Empty/unprogrammed sensor calibration')
    if prom_crc4(words) != words[0] >> 12:
        raise ValueError('Pressure calibration CRC mismatch')


def compensate_ms5837(c, pressure_adc, temperature_adc, model='30BA'):
    """Return pressure in mbar and temperature in Celsius."""
    if model not in ('30BA', '02BA'):
        raise ValueError('pressure_model must be 30BA or 02BA')
    if len(c) != 7 or not (0 < pressure_adc < 0xFFFFFF and 0 < temperature_adc < 0xFFFFFF):
        raise ValueError('Invalid calibration/ADC conversion')
    dt = temperature_adc - c[5] * 256
    temp = 2000 + dt * c[6] / 2**23
    delta = temp - 2000
    ti = off_i = sens_i = 0.0
    if model == '02BA':
        sensitivity = c[1] * 2**16 + c[3] * dt / 2**7
        offset = c[2] * 2**17 + c[4] * dt / 2**6
        if temp < 2000:
            ti = 11 * dt**2 / 2**35
            off_i = 31 * delta**2 / 8
            sens_i = 63 * delta**2 / 32
        divisor = 32768 * 100
    else:
        sensitivity = c[1] * 2**15 + c[3] * dt / 2**8
        offset = c[2] * 2**16 + c[4] * dt / 2**7
        if temp < 2000:
            ti = 3 * dt**2 / 2**33
            off_i = 3 * delta**2 / 2
            sens_i = 5 * delta**2 / 8
            if temp < -1500:
                off_i += 7 * (temp + 1500)**2
                sens_i += 4 * (temp + 1500)**2
        else:
            ti = 2 * dt**2 / 2**37
            off_i = delta**2 / 16
        divisor = 8192 * 10
    pressure = (pressure_adc * (sensitivity - sens_i) / 2**21 - (offset - off_i)) / divisor
    return pressure, (temp - ti) / 100
