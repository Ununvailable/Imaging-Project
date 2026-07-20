"""
OPT acquisition orchestration layer.
Coordinates BaslerAceController + StepperController for a full angular sweep.
Owns dataset naming, folder creation, and metadata.json writing.
"""

from datetime import datetime
import os
import json
import numpy as np
from PIL import Image

from src.basler_ace_controller import BaslerAceController
from src.stepper_controller import StepperController


class OPTAcquisition:
    def __init__(self, data_root: str = "data", steps_per_degree: float = 400.0,
                 file_format: str = "tiff"):
        self.data_root = data_root
        self.steps_per_degree = steps_per_degree
        self.file_format = file_format.lower()

        self.camera = BaslerAceController()
        self.motor = StepperController()

        self.dataset_name = None
        self.dataset_path = None
        self.projections_path = None
        self.reconstruction_path = None

        self._aborted = False
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

    def capture_reference_frames(self):
        if self.dataset_path is None:
            raise RuntimeError("Call create_dataset() first")

        flat = self.camera.grab_frame(timeout_ms=2000)
        if flat is not None:
            self._save_frame(flat, os.path.join(self.dataset_path, f"flat_field.{self.file_format}"))

        dark = self.camera.grab_frame(timeout_ms=2000)
        if dark is not None:
            self._save_frame(dark, os.path.join(self.dataset_path, f"dark_field.{self.file_format}"))

    def run_sweep(self, start_angle: float, end_angle: float, step_deg: float):
        if self.dataset_path is None:
            raise RuntimeError("Call create_dataset() first")

        self._aborted = False
        self._angles = list(np.arange(start_angle, end_angle, step_deg))
        steps_per_increment = round(step_deg * self.steps_per_degree)

        for index, angle in enumerate(self._angles):
            if self._aborted:
                break

            if index > 0:
                with self.motor.lock:
                    self.motor.stop()
                    self.motor.move_relative(steps_per_increment)
                    idle = self.motor.wait_until_idle()
                if not idle:
                    raise RuntimeError(f"Motor did not settle before frame {index}")

            frame = self.camera.grab_frame(timeout_ms=2000)
            if frame is None:
                raise RuntimeError(f"Capture failed at index {index}, angle {angle}")

            filename = f"{index + 1:03d}.{self.file_format}"
            self._save_frame(frame, os.path.join(self.projections_path, filename))
            self._last_completed_index = index

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