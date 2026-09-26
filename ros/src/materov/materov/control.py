"""Hardware-independent motor state machine; times are monotonic seconds."""
import math
import random
import struct

import numpy as np

THRUSTER_GEOMETRY = [
    (0.225, -0.185, 45), (0.225, 0.185, 315),
    (0, -0.185, None), (0, 0.185, None),
    (-0.225, -0.185, 135), (-0.225, 0.185, 225),
]


def axis2command(value):
    """Preserve the existing pilot deadzone and response curve."""
    if abs(value) < 0.4:
        return 0.0
    return 1.5 * value - math.copysign(0.5, value)


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (0x07 if crc & 0x80 else 0)) & 0xFF
    return crc


def encode_frame(values):
    """AA55, payload length, seven signed neutral offsets, CRC-8/ATM."""
    if len(values) != 7 or not all(math.isfinite(v) for v in values):
        raise ValueError('Expected seven finite PWM values')
    offsets = [max(-360, min(360, int(v - 1500))) for v in values]
    frame = b'\xaa\x55\x0e' + struct.pack('<7h', *offsets)
    return frame + bytes([crc8(frame)])


class ThrusterControl:
    """A timeout or transport fault requires a new, neutral arming request."""

    def __init__(self, hz=100.0, ramp_mode='sync', joy_timeout=0.5,
                 inhibited=False):
        if not math.isfinite(hz) or not 1 <= hz <= 500:
            raise ValueError('hz must be between 1 and 500')
        if not math.isfinite(joy_timeout) or not 0.1 <= joy_timeout <= 2:
            raise ValueError('joy_timeout must be between 0.1 and 2 seconds')
        if ramp_mode not in ('sync', 'async'):
            raise ValueError('Unknown ramp mode')
        self.joy_timeout = joy_timeout
        self.inhibited = inhibited
        self.ramp_mode = ramp_mode
        self.ramp_steps = max(1, int(hz * (0.2 if ramp_mode == 'sync' else 0.05)))
        columns = []
        for x, y, angle in THRUSTER_GEOMETRY:
            if angle is None:
                columns.append([0, 0, 1, 0])
            else:
                dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
                columns.append([dx, dy, 0, x * dy - y * dx])
        self.matrix = np.array(columns).T
        self.inverse = np.linalg.pinv(self.matrix)
        self.last_joy = None
        self.joy_neutral = False
        self.armed = False
        self.reason = 'startup'
        self.neutralize()

    def neutralize(self):
        self.current = [1500.0] * 6
        self.target = [1500.0] * 6
        self.claw = 1500
        self.queue = []

    def disarm(self, reason):
        self.armed = False
        self.reason = reason
        self.neutralize()

    def fresh(self, now):
        return self.last_joy is not None and 0 <= now - self.last_joy <= self.joy_timeout

    def arm(self, now, serial_connected):
        if self.armed and self.fresh(now) and serial_connected and not self.inhibited:
            return True
        self.disarm('arming_rejected')
        if self.inhibited:
            self.reason = 'actuation_inhibited'
        elif not serial_connected:
            self.reason = 'serial_unavailable'
        elif not self.fresh(now):
            self.reason = 'joystick_stale'
        elif not self.joy_neutral:
            self.reason = 'release_controls_before_arming'
        else:
            self.armed = True
            self.reason = 'armed'
        return self.armed

    def update_joy(self, axes, buttons, now):
        # Check BEFORE accepting a new sample: a late sample cannot hide a gap.
        if self.armed and not self.fresh(now):
            self.disarm('joystick_timeout')
        valid = (len(axes) >= 5 and len(buttons) >= 6
                 and all(math.isfinite(v) and -1 <= v <= 1 for v in axes)
                 and all(v in (0, 1) for v in buttons))
        if not valid:
            self.last_joy = None
            self.joy_neutral = False
            self.disarm('invalid_joystick')
            return
        self.last_joy = now
        self.joy_neutral = (all(abs(axes[i]) < 0.1 for i in (0, 1, 4))
                            and not any(buttons[i] for i in (1, 2, 4, 5, 6)
                                        if i < len(buttons)))
        # View/Back is a vehicle stop; Guide is not always exposed over USB.
        if len(buttons) > 6 and buttons[6]:
            self.disarm('gamepad_stop')
        if not self.armed:
            self.neutralize()
            return
        tau = [-axis2command(axes[1]), axis2command(axes[0]),
               -axis2command(axes[4]), float(buttons[4] - buttons[5])]
        thrust = self.inverse @ np.array(tau)
        thrust /= max(1.0, float(np.max(np.abs(thrust))))
        self.target = [round(1500 + 400 * v) for v in thrust]
        self.claw = 1500 + 200 * (buttons[2] - buttons[1])

    def tick(self, now):
        if self.armed and not self.fresh(now):
            self.disarm('joystick_timeout')
        if self.inhibited or not self.armed:
            self.neutralize()
        else:
            indices = range(6)
            if self.ramp_mode == 'async':
                if not self.queue:
                    self.queue = random.sample(range(6), 6)
                indices = [self.queue.pop()]
            for i in indices:
                delta = self.target[i] - self.current[i]
                self.current[i] += delta if abs(delta) < 1 else delta / self.ramp_steps
        return encode_frame(self.current + [self.claw])

    def status(self, now, serial_connected):
        return {'armed': self.armed, 'inhibited': self.inhibited,
                'joystick_fresh': self.fresh(now), 'joystick_neutral': self.joy_neutral,
                'serial_connected': serial_connected, 'reason': self.reason,
                'outputs_neutral': all(v == 1500 for v in self.current + [self.claw])}
