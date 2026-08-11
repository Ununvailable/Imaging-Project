"""
View a reconstructed OPT volume (data/<dataset>/reconstruction/volume.npy).

Primary viewer: napari (interactive 3D slice scrubbing, optional dependency).
Fallback: matplotlib slider-based slice viewer, no extra install required.
"""

import os
import argparse
import numpy as np


def load_volume(npy_path: str) -> np.ndarray:
    if not os.path.exists(npy_path):
        raise FileNotFoundError(f"Volume not found: {npy_path}")
    return np.load(npy_path)


def view_volume_napari(npy_path: str):
    import napari

    volume = load_volume(npy_path)
    viewer = napari.Viewer()
    viewer.add_image(volume, name=os.path.basename(npy_path), colormap="gray")
    napari.run()


def view_volume_matplotlib(npy_path: str, initial_row: int = None):
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider

    volume = load_volume(npy_path)
    num_rows = volume.shape[0]
    row = initial_row if initial_row is not None else num_rows // 2

    fig, ax = plt.subplots(figsize=(6, 6))
    plt.subplots_adjust(bottom=0.15)
    img_display = ax.imshow(volume[row], cmap="gray")
    ax.set_title(f"Row {row} / {num_rows - 1}")
    ax.axis("off")

    slider_ax = plt.axes([0.2, 0.03, 0.6, 0.04])
    slider = Slider(slider_ax, "Row", 0, num_rows - 1, valinit=row, valstep=1)

    def update(val):
        r = int(slider.val)
        img_display.set_data(volume[r])
        img_display.set_clim(volume[r].min(), volume[r].max())
        ax.set_title(f"Row {r} / {num_rows - 1}")
        fig.canvas.draw_idle()

    slider.on_changed(update)
    plt.show()


def view_volume(npy_path: str, prefer: str = "napari"):
    """Try napari first (if prefer='napari'), fall back to matplotlib."""
    if prefer == "napari":
        try:
            view_volume_napari(npy_path)
            return
        except ImportError:
            print("napari not available, falling back to matplotlib viewer")
    view_volume_matplotlib(npy_path)


def main():
    parser = argparse.ArgumentParser(description="View a reconstructed OPT volume")
    parser.add_argument("path", type=str, help="Path to volume.npy")
    parser.add_argument("--matplotlib", action="store_true",
                         help="Force the matplotlib fallback viewer instead of napari")
    args = parser.parse_args()

    view_volume(args.path, prefer="matplotlib" if args.matplotlib else "napari")


if __name__ == "__main__":
    main()