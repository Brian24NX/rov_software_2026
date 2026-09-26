#!/usr/bin/env python3
"""Read live Nano control status without publishing any commands."""
import json
import time


def status_banner(state):
    if state is None:
        return 'WARNING: ACTUATION STATUS UNKNOWN — NO VALID LIVE NANO STATUS RECEIVED.'
    if state['inhibited']:
        return 'ACTUATION INHIBITED — THRUSTERS AND CLAW CANNOT BE ARMED.'
    if state['armed']:
        return 'WARNING: ACTUATION NOT INHIBITED — VEHICLE ARMED; CONTROLLER CAN MOVE THRUSTERS AND CLAW.'
    return 'ACTUATION NOT INHIBITED — VEHICLE DISARMED; EXPLICIT ARMING REQUIRED.'


def main():
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    state = None

    def receive(msg):
        nonlocal state
        try:
            value = json.loads(msg.data)
        except (ValueError, TypeError):
            return
        if isinstance(value, dict) and all(
                isinstance(value.get(key), bool) for key in ('inhibited', 'armed')):
            state = value

    rclpy.init()
    node = Node('laptop_actuation_check')
    try:
        node.create_subscription(String, '/control/status', receive, 1)
        deadline = time.monotonic() + 8.0
        while state is None and rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        print('\n' + '=' * 78, flush=True)
        print(status_banner(state), flush=True)
        print('THIS CHECK DOES NOT ARM OR DISARM THE VEHICLE.', flush=True)
        print('=' * 78 + '\n', flush=True)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
