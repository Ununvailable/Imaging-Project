"""
Geometry calibration for OPT reconstruction.

Translated from the reference CBCT script's calibration_* parameters, scoped
to what's actually meaningful for THIS setup (lensless, parallel-beam):

- Center-of-rotation (COR) offset: translates directly, and is the most
  important one -- a misaligned rotation axis causes doubled/ghosted
  reconstructions regardless of beam geometry. Implemented here via the
  standard 0/180-degree opposing-view correlation technique.
- Angular offset/direction: low-stakes (just rotates the output); rotation
  direction is already captured in metadata.json's angles_deg.
- Tilt/skew: conceptually translates but needs ASTRA's 'parallel_vec'
  geometry (not the simple 'parallel' geometry currently used) -- not
  implemented here, lower priority for a rigid bench setup.
- SOD correction: does NOT translate. That's a source-to-origin distance
  correction; parallel-beam has no source apex for it to correct.
"""

import os
import json
import numpy as np

from src.opt_reconstruction import OPTReconstructor


def _find_opposing_angle_index(angles_deg: np.ndarray, index: int) -> int:
    """Find the recorded angle closest to angles_deg[index] + 180 degrees."""
    target = (angles_deg[index] + 180.0) % 360.0
    diffs = np.abs((angles_deg - target + 180) % 360 - 180)  # circular distance
    return int(np.argmin(diffs))


def estimate_cor_offset(dataset_path: str, row_index: int = None,
                         search_range_px: int = 50) -> dict:
    """
    Estimate center-of-rotation offset (in pixels) via 0/180-degree pair
    correlation: the projection at angle theta and the horizontally-flipped
    projection at theta+180 should align if the rotation axis is centered.
    Any consistent shift between them reveals the COR offset.

    Returns a dict with the estimated offset and which angle pair was used.
    Positive offset means the rotation axis sits to the +x side of the
    detector's geometric center.
    """
    recon = OPTReconstructor(dataset_path)
    sinogram, row_index, _, _ = recon.build_sinogram(row_index)
    angles_deg = np.array(recon.metadata["angles_deg"])

    idx_a = 0
    idx_b = _find_opposing_angle_index(angles_deg, idx_a)
    angular_separation = abs((angles_deg[idx_b] - angles_deg[idx_a] + 180) % 360 - 180)
    if abs(angular_separation - 180) > 5:
        raise ValueError(
            f"No projection pair close to 180 deg apart found "
            f"(closest: {angular_separation:.1f} deg). Sweep may not span >=180 deg."
        )

    proj_a = sinogram[idx_a, :]
    proj_b_flipped = sinogram[idx_b, ::-1]

    width = proj_a.shape[0]
    proj_a = proj_a - proj_a.mean()
    proj_b_flipped = proj_b_flipped - proj_b_flipped.mean()

    correlation = np.correlate(proj_a, proj_b_flipped, mode="full")
    lags = np.arange(-(width - 1), width)

    center = len(correlation) // 2
    lo = max(0, center - search_range_px)
    hi = min(len(correlation), center + search_range_px + 1)
    local_best = lo + np.argmax(correlation[lo:hi])
    shift_px = lags[local_best]

    # The flip means: true COR offset from center = shift / 2
    cor_offset_px = shift_px / 2.0

    return {
        "row_index": row_index,
        "angle_pair_indices": (idx_a, idx_b),
        "angle_pair_deg": (float(angles_deg[idx_a]), float(angles_deg[idx_b])),
        "shift_px": int(shift_px),
        "cor_offset_px": cor_offset_px,
    }


def apply_cor_offset(sinogram: np.ndarray, cor_offset_px: float) -> np.ndarray:
    """
    Shift each projection row to re-center the rotation axis.
    sinogram shape: (num_angles, width).
    """
    if cor_offset_px == 0:
        return sinogram

    shift = -cor_offset_px
    shift_int = int(round(shift))
    corrected = np.roll(sinogram, shift_int, axis=1)

    # zero out wrapped-around edge pixels (roll wraps, which is wrong here)
    if shift_int > 0:
        corrected[:, :shift_int] = 0
    elif shift_int < 0:
        corrected[:, shift_int:] = 0

    return corrected


def calibrate_and_save(dataset_path: str, row_index: int = None) -> dict:
    """Estimate COR offset and write it into metadata.json for reconstruction to consume."""
    result = estimate_cor_offset(dataset_path, row_index)

    metadata_path = os.path.join(dataset_path, "metadata.json")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    metadata["calibration_offset_px"] = result["cor_offset_px"]

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return result