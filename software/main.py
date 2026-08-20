"""Entry point. Run from repo root: python main.py"""

import tkinter as tk
from src.gui import CameraMotorGUI
# from src.opt_reconstruction import OPTReconstructor
from src.opt_ASTRA_reconstruction import OPTReconstructor
from src.opt_result_view import view_volume
from src.geometry_calibration import calibrate_and_save


if __name__ == "__main__":
    # root = tk.Tk()
    # app = CameraMotorGUI(root)
    # root.protocol("WM_DELETE_WINDOW", app.on_closing)
    # root.mainloop()

    # result = calibrate_and_save("data/20260817_14_05_08")
    # print(result)  # {'cor_offset_px': ..., 'angle_pair_deg': (0.0, ~180.0), ...}

    # recon = OPTReconstructor("data/20260817_14_05_08")
    recon = OPTReconstructor("data/20260817_14_05_08", iterations=150)  # tune from here

    # # Full image height
    # result = recon.reconstruct_volume()

    # A specific band of rows
    result = recon.reconstruct_volume(row_start=400, row_end=600, invert=False) 

    # # Every 4th row (coarse preview, faster)
    # result = recon.reconstruct_volume(step=2)

    # print(result["volume_shape"])  # (num_rows, out_h, out_w)

    view_volume("data/20260817_14_05_08/reconstruction/volume.npy")
