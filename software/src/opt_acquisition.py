"""
OPT acquisition orchestration layer.
Coordinates BaslerAceController + StepperController for a full angular sweep.
Owns dataset naming, folder creation, and metadata.json writing.
"""

from datetime import datetime
import os
import json
import time
import threading
import numpy as np
from PIL import Image

from src.basler_ace_controller import BaslerAceController
from src.stepper_controller import StepperController


class OPTAcquisition:
    def __init__(self, data_root: str = "data", steps_per_degree: float = 400.0,
                 file_format: str = "png"):
        self.data_root = data_root
        self.steps_per_degree = steps_per_degree
        self.file_format = file_format.lower()

        self.camera = BaslerAceController()
        self.motor = StepperController()

        # Serializes all camera.grab_frame() calls. pypylon's InstantCamera
        # only permits one outstanding RetrieveResult() at a time; without
        # this, live view (GUI thread) and a running sweep (worker thread)
        # collide and pylon raises RuntimeException("There is already a
        # thread waiting for a result").
        self.camera_lock = threading.Lock()

        self.dataset_name = None
        self.dataset_path = None
        self.projections_path = None
        self.reconstruction_path = None

        self._aborted = False
        self._sweep_running = False
        self._last_completed_index = -1
        self._angles = []

    def create_dataset(self) -> str:
        self.dataset_name = datetime.now().strftime("%Y%m%d_%H_%M_%S")
        self.dataset_path = os.path.join(self.data_root, self.dataset_name)
        self.projections_path = os.path.join(self.dataset_path, "projections")
        self.reconstruction_path = os.path.join(self.dataset_path, "reconstruction")

        os.makedirs(self.projections_path, exist_ok=True)
        os.makedirs(self.reconstruction_path, exist_ok=True)
        return self.dataset_name

    def lock_exposure(self, exposure_us: float, gain: float):
        self.camera.set_exposure(exposure_us, auto_off=True)
        self.camera.set_gain(gain, auto_off=True)

    def _save_frame(self, frame: np.ndarray, path: str):
        Image.fromarray(frame[..., ::-1]).save(path)  # BGR -> RGB

    def grab_frame_locked(self, timeout_ms: int = 1000):
        """Thread-safe grab_frame wrapper. Use this instead of calling
        self.camera.grab_frame() directly whenever live view may be running
        concurrently with a sweep (i.e. always, from GUI code)."""
        with self.camera_lock:
            return self.camera.grab_frame(timeout_ms=timeout_ms)

    def capture_reference_frames(self):
        if self.dataset_path is None:
            raise RuntimeError("Call create_dataset() first")

        flat = self.grab_frame_locked(timeout_ms=2000)
        if flat is not None:
            self._save_frame(flat, os.path.join(self.dataset_path, f"flat_field.{self.file_format}"))

        dark = self.grab_frame_locked(timeout_ms=2000)
        if dark is not None:
            self._save_frame(dark, os.path.join(self.dataset_path, f"dark_field.{self.file_format}"))

    def _move_one_increment(self, steps: int, frame_index: int, max_retries: int = 3,
                             settle_delay_s: float = 1.0):
        """
        Move by `steps` and wait for idle. The firmware intermittently replies
        'Wrong Command' to an isolated query without actually desyncing motion —
        observed to self-recover on the next attempt. Retry a few times before
        treating it as fatal.

        settle_delay_s: extra pause held after the GSC-01 first reports 'R' and
        before releasing the lock for the next STOP/MOVE_REL cycle. Testing
        whether the device needs more internal settle time than the raw 'R'
        flag implies.
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                with self.motor.lock:
                    self.motor.stop()
                    self.motor.move_relative(steps)
                    idle = self.motor.wait_until_idle()
                    if idle:
                        time.sleep(settle_delay_s)
                if idle:
                    return
                last_error = f"did not settle (attempt {attempt}/{max_retries})"
            except RuntimeError as e:
                last_error = f"{e} (attempt {attempt}/{max_retries})"
            time.sleep(0.5)

        raise RuntimeError(f"Motor failed at frame {frame_index}: {last_error}")

    def _grab_frame_with_retry(self, index: int, max_retries: int = 3,
                                retry_delay_s: float = 0.5, timeout_ms: int = 2000):
        """
        Grab a projection frame, retrying on transient camera errors (e.g. a
        pylon RuntimeException from a stray concurrent retrieval) instead of
        letting one bad grab abort the whole sweep.
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                frame = self.grab_frame_locked(timeout_ms=timeout_ms)
                if frame is not None:
                    return frame
                last_error = "grab_frame returned None"
            except Exception as e:
                last_error = str(e)
            time.sleep(retry_delay_s)

        raise RuntimeError(f"Capture failed at index {index}: {last_error}")

    def run_sweep(self, start_angle: float, end_angle: float, step_deg: float):
        if self.dataset_path is None:
            raise RuntimeError("Call create_dataset() first")
        if self._sweep_running:
            raise RuntimeError("A sweep is already running")

        self._sweep_running = True
        try:
            self._aborted = False
            self._angles = list(np.arange(start_angle, end_angle, step_deg))
            steps_per_increment = round(step_deg * self.steps_per_degree)

            for index, angle in enumerate(self._angles):
                if self._aborted:
                    break

                if index > 0:
                    self._move_one_increment(steps_per_increment, index)

                frame = self._grab_frame_with_retry(index)

                filename = f"{index + 1:03d}.{self.file_format}"
                self._save_frame(frame, os.path.join(self.projections_path, filename))
                self._last_completed_index = index
        finally:
            self._sweep_running = False

    def is_sweep_running(self) -> bool:
        return self._sweep_running

    def abort(self):
        self._aborted = True
        self.motor.stop()

    def write_metadata(self, params: dict):
        if self.dataset_path is None:
            raise RuntimeError("Call create_dataset() first")

        metadata = dict(params)
        metadata["dataset_name"] = self.dataset_name
        metadata["acquisition_num_projections"] = len(self._angles)
        metadata["angles_deg"] = self._angles
        metadata["last_completed_index"] = self._last_completed_index
        metadata["file_format"] = self.file_format

        with open(os.path.join(self.dataset_path, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)