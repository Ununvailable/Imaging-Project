"""
Stepper motor controller over serial.
Wraps connect/disconnect, command send, response read, motor commands.
No GUI or sweep-sequence logic here.
"""

import serial
import serial.tools.list_ports
import threading
import queue
import time


class StepperController:
    BAUD_RATE = 9600  # fixed by firmware
    COMMAND_GAP_S = 0.5  # minimum spacing between writes; Arduino parser can't keep up otherwise

    def __init__(self):
        self.serial_port = None
        self.rx_queue = queue.Queue()
        self._read_thread = None
        self._idle_event = threading.Event()
        self._error_event = threading.Event()
        self._last_error = None
        self._last_write_time = 0.0
        self.lock = threading.RLock()

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str):
        self.serial_port = serial.Serial(port, self.BAUD_RATE, timeout=1)
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def disconnect(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

    def is_connected(self) -> bool:
        return self.serial_port is not None and self.serial_port.is_open

    def send_command(self, command: str):
        if not self.is_connected():
            raise RuntimeError("Not connected to serial port")
        with self.lock:
            elapsed = time.time() - self._last_write_time
            if elapsed < self.COMMAND_GAP_S:
                time.sleep(self.COMMAND_GAP_S - elapsed)
            try:
                self.serial_port.write((command + '\n').encode())
                self._last_write_time = time.time()
            except serial.SerialException as e:
                self.rx_queue.put(("disconnected", str(e)))
                raise

    def _read_loop(self):
        while self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode(errors="replace").strip()
                    if line:
                        self.rx_queue.put(("rx", line))
                        # GSC-01 status reply format: "<position>,<LS1>,<LS2>,<R|B>"
                        # R = ready/idle, B = busy/moving
                        parts = line.split(",")
                        if len(parts) == 4:
                            status_flag = parts[-1].strip().upper()
                            if status_flag == "R":
                                self._idle_event.set()
                        if "WRONG COMMAND" in line.upper():
                            self._last_error = line
                            self._error_event.set()
            except serial.SerialException as e:
                self.rx_queue.put(("disconnected", str(e)))
                break
            except Exception as e:
                self.rx_queue.put(("error", str(e)))

    # Motor command wrappers
    def stop(self):
        self.send_command("STOP")

    def move_relative(self, steps: int):
        self.send_command(f"MOVE_REL {steps}")

    def move_absolute(self, steps: int):
        self.send_command(f"MOVE_ABS {steps}")

    def jog(self, direction: str):
        self.send_command(f"JOGGING {direction}")

    def emergency_stop(self):
        self.send_command("E")

    def move_origin(self):
        self.send_command("ORIGIN")

    def get_status(self):
        self.send_command("STATUS")

    def get_angle(self):
        self.send_command("ANGLE")

    def set_speed(self, min_speed: int, max_speed: int, accel: int):
        self.send_command(f"SET SPEED S{min_speed}F{max_speed}R{accel}")

    def wait_until_idle(self, timeout_s: float = 20.0, poll_interval_s: float = 2.0) -> bool:
        """
        Poll STATUS until the GSC-01 CSV reply's last field is 'R' (ready), or timeout.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            self._idle_event.clear()
            self._error_event.clear()
            self.get_status()
            if self._idle_event.wait(timeout=poll_interval_s):
                return True
            if self._error_event.is_set():
                raise RuntimeError(f"Motor reported error: {self._last_error}")
        return False