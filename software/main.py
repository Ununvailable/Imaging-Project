"""Entry point. Run from repo root: python main.py"""

import tkinter as tk
from src.gui import CameraMotorGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = CameraMotorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
