"""
Stepper motor controller over serial.
Wraps connect/disconnect, command send, response read, motor commands.
No GUI or sweep-sequence logic here.
"""

import serial
import serial.tools.list_ports
import threading
import queue


class StepperController:
    BAUD_RATE = 9600  # fixed by firmware

    def __init__(self):
        self.serial_port = None
        self.rx_queue = queue.Queue()
        self._read_thread = None

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError

    def send_command(self, command: str):
        raise NotImplementedError

    def _read_loop(self):
        """Background thread: pushes received lines/errors onto rx_queue."""
        raise NotImplementedError

    # Motor command wrappers
    def stop(self):
        raise NotImplementedError

    def move_relative(self, steps: int):
        raise NotImplementedError

    def move_absolute(self, steps: int):
        raise NotImplementedError

    def jog(self, direction: str):
        raise NotImplementedError

    def emergency_stop(self):
        raise NotImplementedError

    def move_origin(self):
        raise NotImplementedError

    def get_status(self):
        raise NotImplementedError

    def get_angle(self):
        raise NotImplementedError

    def set_speed(self, min_speed: int, max_speed: int, accel: int):
        raise NotImplementedError

    def wait_until_idle(self, timeout_s: float = 10.0) -> bool:
        """Poll status/angle until motor reports idle or timeout. Needed by sweep controller."""
        raise NotImplementedError
