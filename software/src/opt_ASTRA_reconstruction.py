"""
2D single-slice OPT reconstruction.
Lensless setup: two 0.5mm slits collimate the illumination, object rotates
in the beam, bare CMOS sensor (no lens) records the shadow directly.
Chief-ray path is a straight line with no refraction step, so standard
parallel-beam filtered backprojection applies directly -- no fan/cone-beam
correction needed here.

Reconstruction backend: ASTRA Toolbox, 'parallel' 2D geometry, with
FBP_CUDA if a CUDA GPU is available (checked once at init, same pattern as
the reference CBCT script), falling back to ASTRA's CPU 'FBP' otherwise.
If ASTRA itself isn't installed, falls back further to
skimage.transform.iradon so the module still runs without it.

Object-space pixel size = sensor pixel pitch (no lens => no magnification).

Note: the two-slit collimator has finite angular acceptance
(~0.5mm slit / ~138mm separation => ~0.2 deg half-angle), which sets a
resolution floor via geometric penumbra blur -- worth confirming with a
sharp-edged calibration target rather than assuming pixel-limited resolution.

Pipeline: pick one row from every projection -> sinogram -> flat/dark
correction -> absorbance (-log) -> FBP -> save reconstructed slice.
"""

import os
import json
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

try:
    import astra
    ASTRA_AVAILABLE = True
except ImportError:
    ASTRA_AVAILABLE = False

if not ASTRA_AVAILABLE:
    from skimage.transform import iradon


class OPTReconstructor:
    def __init__(self, dataset_path: str, output_format: str = "png", iterations: int = 150):
        self.dataset_path = dataset_path
        self.projections_path = os.path.join(dataset_path, "projections")
        self.reconstruction_path = os.path.join(dataset_path, "reconstruction")
        self.output_format = output_format
        self.iterations = iterations  # only used by iterative algorithms (SIRT/CGLS/SART), ignored by FBP
        self.metadata = self._load_metadata()

        self.backend, self.astra_algorithm = self._select_backend()

    def _select_backend(self):
        if not ASTRA_AVAILABLE:
            logger.warning("astra not installed; falling back to skimage.transform.iradon")
            return "skimage", None

        if astra.astra.use_cuda():
            logger.info("ASTRA: CUDA available, using FBP_CUDA")
            # return "astra", "FBP_CUDA"
            return "astra", "SIRT_CUDA"
        else:
            logger.warning("ASTRA: CUDA not available, using CPU FBP (slower)")
            return "astra", "FBP"

    def _load_metadata(self) -> dict:
        with open(os.path.join(self.dataset_path, "metadata.json"), "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_gray(self, path: str) -> np.ndarray:
        with Image.open(path) as img:
            return np.array(img.convert("L"), dtype=np.float32)

    def _projection_files(self) -> list:
        file_format = self.metadata.get("file_format", "tiff")
        n = self.metadata.get("acquisition_num_projections", 0)
        files = [
            os.path.join(self.projections_path, f"{i + 1:03d}.{file_format}")
            for i in range(n)
        ]
        missing = [f for f in files if not os.path.exists(f)]
        if missing:
            raise FileNotFoundError(f"{len(missing)} projection file(s) missing, e.g. {missing[0]}")
        return files

    def _reference_frame_path(self, name: str) -> str:
        # reference frames are saved with the same file_format as the projections
        file_format = self.metadata.get("file_format", "tiff")
        return os.path.join(self.dataset_path, f"{name}.{file_format}")

    def _load_reference_row(self, name: str, row_index: int) -> np.ndarray:
        path = self._reference_frame_path(name)
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

        flat_row = self._load_reference_row("flat_field", row_index)
        dark_row = self._load_reference_row("dark_field", row_index)

        return sinogram, row_index, flat_row, dark_row

    def correct_and_log(self, sinogram: np.ndarray, flat_row, dark_row, invert: bool = False) -> np.ndarray:
        corrected = sinogram.copy()

        if dark_row is not None:
            corrected = corrected - dark_row[np.newaxis, :]
            corrected = np.maximum(corrected, 1.0)

        if flat_row is not None:
            flat = flat_row.copy()
            if dark_row is not None:
                flat = np.maximum(flat - dark_row, 1.0)
            corrected = corrected / flat[np.newaxis, :]
            corrected = np.clip(corrected, 1e-6, None)
            absorbance = -np.log(corrected)
        else:
            i0 = np.max(corrected)
            absorbance = -np.log(np.clip(corrected / i0, 1e-6, None))

        if invert:
            absorbance = -absorbance

        return absorbance

    def _reconstruct_slice(self, processed_sinogram: np.ndarray, angles_deg: np.ndarray, width: int) -> np.ndarray:
        """processed_sinogram shape: (num_angles, width)"""
        if self.backend == "astra":
            return self._reconstruct_slice_astra(processed_sinogram, angles_deg, width)
        else:
            # iradon expects (detector_pixels, num_angles)
            return iradon(processed_sinogram.T, theta=angles_deg, circle=False)

    def _reconstruct_slice_astra(self, processed_sinogram: np.ndarray, angles_deg: np.ndarray, width: int) -> np.ndarray:
        angles_rad = np.radians(angles_deg)
        proj_geom = astra.create_proj_geom('parallel', 1.0, width, angles_rad)
        vol_geom = astra.create_vol_geom(width, width)

        sino_id = astra.data2d.create('-sino', proj_geom, processed_sinogram)
        rec_id = astra.data2d.create('-vol', vol_geom)

        cfg = astra.astra_dict(self.astra_algorithm)
        cfg['ReconstructionDataId'] = rec_id
        cfg['ProjectionDataId'] = sino_id
        if self.astra_algorithm == 'FBP':
            cfg['FilterType'] = 'Ram-Lak'
        else:
            # iterative algorithm (SIRT_CUDA, CGLS_CUDA, etc.): absorbance
            # can't physically be negative, so enforce it during iteration
            cfg['option'] = {'MinConstraint': 0}

        alg_id = astra.algorithm.create(cfg)
        try:
            if self.astra_algorithm == 'FBP':
                astra.algorithm.run(alg_id)  # single analytic pass, no iteration count needed
            else:
                # iterative algorithms default to 1 iteration if none is given --
                # nowhere near converged, produces a smeared/under-resolved result
                astra.algorithm.run(alg_id, self.iterations)
            result = astra.data2d.get(rec_id)
        finally:
            astra.algorithm.delete(alg_id)
            astra.data2d.delete(sino_id)
            astra.data2d.delete(rec_id)

        return result

    def reconstruct(self, row_index: int = None, apply_correction: bool = True, invert: bool = False) -> dict:
        sinogram, row_index, flat_row, dark_row = self.build_sinogram(row_index)
        width = sinogram.shape[1]

        processed = self.correct_and_log(sinogram, flat_row, dark_row, invert=invert) if apply_correction else sinogram

        cor_offset_px = self.metadata.get("calibration_offset_px", 0)
        if cor_offset_px:
            from src.geometry_calibration import apply_cor_offset
            processed = apply_cor_offset(processed, cor_offset_px)

        angles_deg = np.array(self.metadata["angles_deg"])

        slice_2d = self._reconstruct_slice(processed, angles_deg, width)

        os.makedirs(self.reconstruction_path, exist_ok=True)
        out_path = os.path.join(self.reconstruction_path, f"slice_row{row_index:04d}.{self.output_format}")
        self._save_slice(slice_2d, out_path)

        sinogram_path = os.path.join(self.reconstruction_path, f"sinogram_row{row_index:04d}.{self.output_format}")
        self._save_slice(processed, sinogram_path)

        return {
            "row_index": row_index,
            "slice_path": out_path,
            "sinogram_path": sinogram_path,
            "slice_shape": slice_2d.shape,
            "backend": self.backend,
            "algorithm": self.astra_algorithm,
        }

    def reconstruct_volume(self, row_start: int = 0, row_end: int = None, step: int = 1,
                            apply_correction: bool = True, save_slices: bool = False, invert: bool = False) -> dict:
        """
        Reconstruct a band of rows (or the full image height) in one pass.
        Loads all projections into memory ONCE (see load_projection_stack).

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

        flat_path = self._reference_frame_path("flat_field")
        dark_path = self._reference_frame_path("dark_field")
        flat_full = self._load_gray(flat_path) if os.path.exists(flat_path) else None
        dark_full = self._load_gray(dark_path) if os.path.exists(dark_path) else None

        angles_deg = np.array(self.metadata["angles_deg"])
        os.makedirs(self.reconstruction_path, exist_ok=True)

        cor_offset_px = self.metadata.get("calibration_offset_px", 0)
        if cor_offset_px:
            from src.geometry_calibration import apply_cor_offset

        volume = None
        for idx, row in enumerate(rows):
            sinogram = stack[:, row, :]  # (num_angles, width)
            flat_row = flat_full[row, :] if flat_full is not None else None
            dark_row = dark_full[row, :] if dark_full is not None else None

            processed = self.correct_and_log(sinogram, flat_row, dark_row, invert=invert) if apply_correction else sinogram
            if cor_offset_px:
                processed = apply_cor_offset(processed, cor_offset_px)
            slice_2d = self._reconstruct_slice(processed, angles_deg, width)

            if volume is None:
                volume = np.zeros((len(rows),) + slice_2d.shape, dtype=np.float32)
            volume[idx] = slice_2d

            if save_slices:
                self._save_slice(slice_2d, os.path.join(self.reconstruction_path,
                                                          f"slice_row{row:04d}.{self.output_format}"))

        volume_path = os.path.join(self.reconstruction_path, "volume.npy")
        np.save(volume_path, volume)

        return {
            "rows": rows,
            "volume_path": volume_path,
            "volume_shape": volume.shape,
            "backend": self.backend,
            "algorithm": self.astra_algorithm,
        }

    def _save_slice(self, array: np.ndarray, path: str):
        normalized = array - array.min()
        max_val = normalized.max()
        if max_val > 0:
            normalized = normalized / max_val
        img = (normalized * 65535).astype(np.uint16)
        Image.fromarray(img).save(path)