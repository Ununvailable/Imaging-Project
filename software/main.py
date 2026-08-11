"""Entry point. Run from repo root: python main.py"""

import tkinter as tk
from src.gui import CameraMotorGUI
from src.opt_reconstruction import OPTReconstructor
from src.opt_result_view import view_volume


if __name__ == "__main__":
    # root = tk.Tk()
    # app = CameraMotorGUI(root)
    # root.protocol("WM_DELETE_WINDOW", app.on_closing)
    # root.mainloop()

    # recon = OPTReconstructor("data/20260809_22_20_29")

    # # Full image height
    # result = recon.reconstruct_volume()

    # # A specific band of rows
    # result = recon.reconstruct_volume(row_start=400, row_end=600) 

    # # Every 4th row (coarse preview, faster)
    # result = recon.reconstruct_volume(step=2)

    # print(result["volume_shape"])  # (num_rows, out_h, out_w)

    view_volume("data/20260809_22_20_29/reconstruction/volume.npy")
