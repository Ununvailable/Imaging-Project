"""
2D single-slice OPT reconstruction.
Lensless setup: two 0.5mm slits collimate the illumination, object rotates
in the beam, bare CMOS sensor (no lens) records the shadow directly.
Chief-ray path is a straight line with no refraction step, so standard
parallel-beam filtered backprojection (skimage.transform.iradon) applies
directly -- no fan/cone-beam correction needed here.

Object-space pixel size = sensor pixel pitch (no lens => no magnification).

Note: the two-slit collimator has finite angular acceptance
(~0.5mm slit / ~138mm separation => ~0.2 deg half-angle), which sets a
resolution floor via geometric penumbra blur -- worth confirming with a
sharp-edged calibration target rather than assuming pixel-limited resolution.

Pipeline: pick one row from every projection -> sinogram -> flat/dark
correction -> absorbance (-log) -> iradon -> save reconstructed slice.
"""

import os
import json
import numpy as np
from PIL import Image
from skimage.transform import iradon


class OPTReconstructor:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.projections_path = os.path.join(dataset_path, "projections")
        self.reconstruction_path = os.path.join(dataset_path, "reconstruction")
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        with open(os.path.join(self.dataset_path, "metadata.json"), "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_gray(self, path: str) -> np.ndarray:
        with Image.open(path) as img:
            return np.array(img.convert("L"), dtype=np.float32)

    def _projection_files(self) -> list:
        file_format = self.metadata.get("file_format", "png")
        n = self.metadata.get("acquisition_num_projections", 0)
        files = [
            os.path.join(self.projections_path, f"{i + 1:03d}.{file_format}")
            for i in range(n)
        ]
        missing = [f for f in files if not os.path.exists(f)]
        if missing:
            raise FileNotFoundError(f"{len(missing)} projection file(s) missing, e.g. {missing[0]}")
        return files

    def _load_reference_row(self, filename: str, row_index: int) -> np.ndarray:
        path = os.path.join(self.dataset_path, filename)
        if not os.path.exists(path):
            return None
        return self._load_gray(path)[row_index, :]

    def load_projection_stack(self) -> np.ndarray:
        """Load every projection into memory once, shape (num_angles, height, width)."""
        files = self._projection_files()
        first = self._load_gray(files[0])
        height, width = first.shape

        stack = np.zeros((len(files), height, width), dtype=np.float32)
        stack[0] = first
        for i, path in enumerate(files[1:], start=1):
            stack[i] = self._load_gray(path)
        return stack

    def build_sinogram(self, row_index: int = None):
        files = self._projection_files()

        first = self._load_gray(files[0])
        height, width = first.shape
        if row_index is None:
            row_index = height // 2

        sinogram = np.zeros((len(files), width), dtype=np.float32)
        for i, path in enumerate(files):
            img = first if i == 0 else self._load_gray(path)
            sinogram[i, :] = img[row_index, :]

        flat_row = self._load_reference_row("flat_field.png", row_index)
        dark_row = self._load_reference_row("dark_field.png", row_index)

        return sinogram, row_index, flat_row, dark_row

    def correct_and_log(self, sinogram: np.ndarray, flat_row, dark_row) -> np.ndarray:
        corrected = sinogram.copy()

        if dark_row is not None:
            corrected = corrected - dark_row[np.newaxis, :]
            corrected = np.maximum(corrected, 1.0)

        if flat_row is not None:
            flat = flat_row.copy()
            if dark_row is not None:
                flat = np.maximum(flat - dark_row, 1.0)
            corrected = corrected / flat[np.newaxis, :]
            # normalized transmission; clip to avoid log(0) or log(negative)
            corrected = np.clip(corrected, 1e-6, None)
            absorbance = -np.log(corrected)
        else:
            # no flat field available: normalize by per-sinogram max as a fallback
            i0 = np.max(corrected)
            absorbance = -np.log(np.clip(corrected / i0, 1e-6, None))

        return absorbance

    def reconstruct(self, row_index: int = None, apply_correction: bool = True) -> dict:
        sinogram, row_index, flat_row, dark_row = self.build_sinogram(row_index)

        if apply_correction:
            processed = self.correct_and_log(sinogram, flat_row, dark_row)
        else:
            processed = sinogram

        angles_deg = np.array(self.metadata["angles_deg"])

        # iradon expects sinogram shape (detector_pixels, num_angles)
        slice_2d = iradon(processed.T, theta=angles_deg, circle=False)

        os.makedirs(self.reconstruction_path, exist_ok=True)
        out_path = os.path.join(self.reconstruction_path, f"slice_row{row_index:04d}.png")
        self._save_slice(slice_2d, out_path)

        sinogram_path = os.path.join(self.reconstruction_path, f"sinogram_row{row_index:04d}.png")
        self._save_slice(processed, sinogram_path)

        return {
            "row_index": row_index,
            "slice_path": out_path,
            "sinogram_path": sinogram_path,
            "slice_shape": slice_2d.shape,
        }

    def reconstruct_volume(self, row_start: int = 0, row_end: int = None, step: int = 1,
                            apply_correction: bool = True, save_slices: bool = False) -> dict:
        """
        Reconstruct a band of rows (or the full image height) in one pass.
        Loads all projections into memory ONCE (see load_projection_stack),
        rather than reloading the full projection set per row.

        row_end=None reconstructs to the full image height.
        Memory note: stack size is num_angles * height * width * 4 bytes --
        e.g. 360 angles * 1024 rows * 1280 cols * 4B ~= 1.9 GB. For low-memory
        machines, process in chunks via row_start/row_end rather than the
        full height at once.
        """
        stack = self.load_projection_stack()  # (num_angles, height, width)
        num_angles, height, width = stack.shape
        if row_end is None:
            row_end = height
        rows = list(range(row_start, row_end, step))
        if not rows:
            raise ValueError("Empty row range")

        flat_path = os.path.join(self.dataset_path, "flat_field.png")
        dark_path = os.path.join(self.dataset_path, "dark_field.png")
        flat_full = self._load_gray(flat_path) if os.path.exists(flat_path) else None
        dark_full = self._load_gray(dark_path) if os.path.exists(dark_path) else None

        angles_deg = np.array(self.metadata["angles_deg"])
        os.makedirs(self.reconstruction_path, exist_ok=True)

        volume = None
        for idx, row in enumerate(rows):
            sinogram = stack[:, row, :]  # (num_angles, width)
            flat_row = flat_full[row, :] if flat_full is not None else None
            dark_row = dark_full[row, :] if dark_full is not None else None

            processed = self.correct_and_log(sinogram, flat_row, dark_row) if apply_correction else sinogram
            slice_2d = iradon(processed.T, theta=angles_deg, circle=False)

            if volume is None:
                volume = np.zeros((len(rows),) + slice_2d.shape, dtype=np.float32)
            volume[idx] = slice_2d

            if save_slices:
                self._save_slice(slice_2d, os.path.join(self.reconstruction_path, f"slice_row{row:04d}.png"))

        volume_path = os.path.join(self.reconstruction_path, "volume.npy")
        np.save(volume_path, volume)

        return {
            "rows": rows,
            "volume_path": volume_path,
            "volume_shape": volume.shape,
        }

    def _save_slice(self, array: np.ndarray, path: str):
        normalized = array - array.min()
        max_val = normalized.max()
        if max_val > 0:
            normalized = normalized / max_val
        img = (normalized * 65535).astype(np.uint16)
        Image.fromarray(img).save(path)