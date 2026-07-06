"""
OPT acquisition orchestration layer.
Coordinates BaslerAceController + StepperController for a full angular sweep.
Owns dataset naming, folder creation, and metadata.json writing.
"""

from datetime import datetime
import os
import json

from src.basler_ace_controller import BaslerAceController
from src.stepper_controller import StepperController


class OPTAcquisition:
    def __init__(self, data_root: str = "data"):
        self.data_root = data_root
        self.camera = BaslerAceController()
        self.motor = StepperController()
        self.dataset_name = None
        self.dataset_path = None

    def create_dataset(self) -> str:
        """Generate timestamp name, create data/<name>/projections and /reconstructions."""
        raise NotImplementedError

    def lock_exposure(self, exposure_us: float, gain: float):
        raise NotImplementedError

    def capture_reference_frames(self):
        """Capture flat-field / dark-field frames before sweep. Saved under dataset root."""
        raise NotImplementedError

    def run_sweep(self, start_angle: float, end_angle: float, step_deg: float):
        """
        For each angle: move -> wait_until_idle -> capture -> save as
        data/<dataset>/projections/<angle>.<ext>
        Tracks progress for abort/resume.
        """
        raise NotImplementedError

    def abort(self):
        raise NotImplementedError

    def write_metadata(self, params: dict):
        """Write data/<dataset>/metadata.json"""
        raise NotImplementedError
