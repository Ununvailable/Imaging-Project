"""
Tkinter GUI. Thin layer: wires user actions to OPTAcquisition
(which itself wires BaslerAceController + StepperController).
No direct hardware calls here.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading

from src.opt_acquisition import OPTAcquisition


class CameraMotorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OPT Acquisition")
        self.root.geometry("1000x750")

        self.acquisition = OPTAcquisition()
        self.live_view_running = False

        self.setup_gui()

    def setup_gui(self):
        outer_canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0)
        outer_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        v_scroll = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=outer_canvas.yview)
        v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        outer_canvas.configure(yscrollcommand=v_scroll.set)

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        main_frame = ttk.Frame(outer_canvas, padding="10")
        main_frame_id = outer_canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def on_frame_configure(event):
            outer_canvas.configure(scrollregion=outer_canvas.bbox("all"))

        def on_canvas_configure(event):
            outer_canvas.itemconfig(main_frame_id, width=event.width)

        main_frame.bind("<Configure>", on_frame_configure)
        outer_canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            outer_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        outer_canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Camera feed
        camera_frame = ttk.LabelFrame(main_frame, text="Camera Feed", padding="10")
        camera_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.canvas = tk.Canvas(camera_frame, width=640, height=480, bg='gray')
        self.canvas.pack()

        cam_control_frame = ttk.Frame(camera_frame)
        cam_control_frame.pack(pady=5)

        ttk.Label(cam_control_frame, text="Width:").pack(side=tk.LEFT, padx=5)
        self.cam_width_var = tk.StringVar(value="640")
        ttk.Entry(cam_control_frame, textvariable=self.cam_width_var, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Label(cam_control_frame, text="Height:").pack(side=tk.LEFT, padx=5)
        self.cam_height_var = tk.StringVar(value="480")
        ttk.Entry(cam_control_frame, textvariable=self.cam_height_var, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Button(cam_control_frame, text="Start Camera", command=self.start_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(cam_control_frame, text="Stop Camera", command=self.stop_camera).pack(side=tk.LEFT, padx=5)

        exposure_frame = ttk.Frame(camera_frame)
        exposure_frame.pack(pady=5)

        ttk.Label(exposure_frame, text="Exposure (us):").pack(side=tk.LEFT, padx=5)
        self.exposure_var = tk.StringVar(value="10000")
        ttk.Entry(exposure_frame, textvariable=self.exposure_var, width=8).pack(side=tk.LEFT, padx=5)

        ttk.Label(exposure_frame, text="Gain:").pack(side=tk.LEFT, padx=5)
        self.gain_var = tk.StringVar(value="0")
        ttk.Entry(exposure_frame, textvariable=self.gain_var, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Button(exposure_frame, text="Lock Exposure/Gain", command=self.lock_exposure).pack(side=tk.LEFT, padx=5)

        # Serial connection
        serial_frame = ttk.LabelFrame(main_frame, text="Serial Connection", padding="10")
        serial_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)

        ttk.Label(serial_frame, text="Port:").grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(serial_frame, width=15)
        self.port_combo.grid(row=0, column=1, padx=5)

        ttk.Button(serial_frame, text="Refresh Ports", command=self.refresh_ports).grid(row=0, column=2, padx=5)
        ttk.Button(serial_frame, text="Connect", command=self.connect_serial).grid(row=0, column=3, padx=5)
        ttk.Button(serial_frame, text="Disconnect", command=self.disconnect_serial).grid(row=0, column=4, padx=5)

        self.connection_status = ttk.Label(serial_frame, text="Disconnected", foreground="red")
        self.connection_status.grid(row=0, column=5, padx=5)

        # Manual motor control
        motor_frame = ttk.LabelFrame(main_frame, text="Manual Motor Control", padding="10")
        motor_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)

        ttk.Label(motor_frame, text="Steps:").grid(row=0, column=0, padx=5, pady=5)
        self.steps_var = tk.StringVar(value="1000")
        ttk.Entry(motor_frame, textvariable=self.steps_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(motor_frame, text="Move Relative", command=self.move_relative).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(motor_frame, text="Move Absolute", command=self.move_absolute).grid(row=0, column=3, padx=5, pady=5)

        jog_frame = ttk.Frame(motor_frame)
        jog_frame.grid(row=1, column=0, columnspan=4, pady=10)

        ttk.Button(jog_frame, text="Jog +", command=lambda: self.jog("+")).pack(side=tk.LEFT, padx=5)
        ttk.Button(jog_frame, text="Jog -", command=lambda: self.jog("-")).pack(side=tk.LEFT, padx=5)
        ttk.Button(jog_frame, text="Stop", command=self.stop_motor).pack(side=tk.LEFT, padx=5)
        ttk.Button(jog_frame, text="E-Stop", command=self.emergency_stop,
                   style='Emergency.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Button(motor_frame, text="Move to Origin", command=self.move_origin).grid(row=2, column=0, padx=5, pady=5)

        # Sweep control
        sweep_frame = ttk.LabelFrame(main_frame, text="Sweep Acquisition", padding="10")
        sweep_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=5)

        ttk.Label(sweep_frame, text="Start (deg):").grid(row=0, column=0, padx=5)
        self.start_angle_var = tk.StringVar(value="0")
        ttk.Entry(sweep_frame, textvariable=self.start_angle_var, width=8).grid(row=0, column=1, padx=5)

        ttk.Label(sweep_frame, text="End (deg):").grid(row=0, column=2, padx=5)
        self.end_angle_var = tk.StringVar(value="360")
        ttk.Entry(sweep_frame, textvariable=self.end_angle_var, width=8).grid(row=0, column=3, padx=5)

        ttk.Label(sweep_frame, text="Step (deg):").grid(row=0, column=4, padx=5)
        self.step_angle_var = tk.StringVar(value="1")
        ttk.Entry(sweep_frame, textvariable=self.step_angle_var, width=8).grid(row=0, column=5, padx=5)

        ttk.Button(sweep_frame, text="Capture References", command=self.capture_references).grid(row=0, column=6, padx=5)
        self.start_sweep_button = ttk.Button(sweep_frame, text="Start Sweep", command=self.start_sweep)
        self.start_sweep_button.grid(row=0, column=7, padx=5)
        ttk.Button(sweep_frame, text="Abort Sweep", command=self.abort_sweep).grid(row=0, column=8, padx=5)

        self.sweep_progress = ttk.Label(sweep_frame, text="Idle")
        self.sweep_progress.grid(row=1, column=0, columnspan=9, pady=5)

        # Log
        response_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        response_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.response_text = tk.Text(response_frame, height=8, width=80)
        self.response_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(response_frame, command=self.response_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.response_text.config(yscrollcommand=scrollbar.set)

        style = ttk.Style()
        style.configure('Emergency.TButton', foreground='red')

        self.refresh_ports()
        self.poll_serial_queue()

    def log(self, message):
        self.response_text.insert(tk.END, message + '\n')
        self.response_text.see(tk.END)

    def poll_serial_queue(self):
        q = self.acquisition.motor.rx_queue
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "rx":
                    self.log(f"Received: {payload}")
                elif kind == "disconnected":
                    self.log(f"Serial disconnected: {payload}")
                    self.connection_status.config(text="Disconnected", foreground="red")
                elif kind == "error":
                    self.log(f"Serial read error: {payload}")
        except Exception:
            pass
        self.root.after(100, self.poll_serial_queue)

    # Camera
    def start_camera(self):
        try:
            width = int(self.cam_width_var.get())
            height = int(self.cam_height_var.get())
            self.acquisition.camera.open(width=width, height=height)
            self.acquisition.camera.start_grabbing()
            self.live_view_running = True
            self.update_live_view()
            self.log("Camera started")
        except Exception as e:
            messagebox.showerror("Camera Error", str(e))

    def stop_camera(self):
        self.live_view_running = False
        self.acquisition.camera.close()
        self.canvas.delete("all")
        self.log("Camera stopped")

    def update_live_view(self):
        if not self.live_view_running:
            return
        try:
            frame = self.acquisition.camera.grab_frame(timeout_ms=100)
            if frame is not None:
                rgb = frame[..., ::-1]
                img = Image.fromarray(rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
                self.canvas.imgtk = imgtk
        except Exception as e:
            self.log(f"Live view error: {e}")
        self.root.after(30, self.update_live_view)

    def lock_exposure(self):
        try:
            self.acquisition.lock_exposure(float(self.exposure_var.get()), float(self.gain_var.get()))
            self.log("Exposure/gain locked")
        except Exception as e:
            messagebox.showerror("Exposure Error", str(e))

    # Serial
    def refresh_ports(self):
        ports = self.acquisition.motor.list_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def connect_serial(self):
        try:
            self.acquisition.motor.connect(self.port_combo.get())
            self.connection_status.config(text="Connected", foreground="green")
            self.log(f"Connected to {self.port_combo.get()}")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def disconnect_serial(self):
        self.acquisition.motor.disconnect()
        self.connection_status.config(text="Disconnected", foreground="red")
        self.log("Disconnected")

    # Manual motor control
    def _validated_steps(self):
        try:
            return int(self.steps_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Steps must be an integer")
            return None

    def move_relative(self):
        steps = self._validated_steps()
        if steps is None:
            return
        self.acquisition.motor.stop()
        self.acquisition.motor.move_relative(steps)

    def move_absolute(self):
        steps = self._validated_steps()
        if steps is None:
            return
        self.acquisition.motor.stop()
        self.acquisition.motor.move_absolute(steps)

    def jog(self, direction):
        self.acquisition.motor.stop()
        self.acquisition.motor.jog(direction)

    def stop_motor(self):
        self.acquisition.motor.stop()

    def emergency_stop(self):
        self.acquisition.motor.stop()
        self.acquisition.motor.emergency_stop()

    def move_origin(self):
        self.acquisition.motor.stop()
        self.acquisition.motor.move_origin()

    # Sweep
    def capture_references(self):
        try:
            if self.acquisition.dataset_path is None:
                self.acquisition.create_dataset()
                self.log(f"Dataset created: {self.acquisition.dataset_name}")
            self.acquisition.capture_reference_frames()
            self.log("Reference frames captured")
        except Exception as e:
            messagebox.showerror("Reference Capture Error", str(e))

    def start_sweep(self):
        try:
            start = float(self.start_angle_var.get())
            end = float(self.end_angle_var.get())
            step = float(self.step_angle_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Start/End/Step must be numeric")
            return

        if self.acquisition.dataset_path is None:
            self.acquisition.create_dataset()
            self.log(f"Dataset created: {self.acquisition.dataset_name}")

        self.start_sweep_button.config(state=tk.DISABLED)

        def worker():
            self.root.after(0, lambda: self.sweep_progress.config(text="Running"))
            try:
                self.acquisition.run_sweep(start, end, step)
                self.acquisition.write_metadata({
                    "acquisition_start_angle_deg": start,
                    "acquisition_scan_range_deg": end - start,
                    "acquisition_angle_step_deg": step,
                })
                self.root.after(0, lambda: self.sweep_progress.config(text="Done"))
                self.root.after(0, lambda: self.log("Sweep complete"))
            except Exception as e:
                self.root.after(0, lambda: self.sweep_progress.config(text="Error"))
                self.root.after(0, lambda err=e: self.log(f"Sweep error: {err}"))
            finally:
                self.root.after(0, lambda: self.start_sweep_button.config(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    def abort_sweep(self):
        self.acquisition.abort()
        self.sweep_progress.config(text="Aborted")
        self.log("Sweep aborted")

    def on_closing(self):
        self.acquisition.motor.stop()
        self.stop_camera()
        self.acquisition.motor.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraMotorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()