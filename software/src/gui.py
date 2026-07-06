"""
Tkinter GUI. Thin layer: wires user actions to OPTAcquisition
(which itself wires BaslerAceController + StepperController).
No direct hardware calls here.
"""

import tkinter as tk
from src.opt_acquisition import OPTAcquisition


class CameraMotorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OPT Acquisition")
        self.acquisition = OPTAcquisition()
        self.setup_gui()

    def setup_gui(self):
        raise NotImplementedError

    def on_closing(self):
        raise NotImplementedError


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraMotorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
