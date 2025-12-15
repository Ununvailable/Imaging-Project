import cv2
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports
import os
from datetime import datetime
import threading

class CameraMotorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Camera & Motor Control")
        self.root.geometry("1000x700")
        
        # Initialize variables
        self.cap = None
        self.serial_port = None
        self.camera_running = False
        self.camera_index = 1  # Check Window's Device Manager
        
        # Create data folder
        os.makedirs('data', exist_ok=True)
        
        # Setup GUI
        self.setup_gui()
        
    def setup_gui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Camera section
        camera_frame = ttk.LabelFrame(main_frame, text="Camera Feed", padding="10")
        camera_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.canvas = tk.Canvas(camera_frame, width=640, height=480, bg='gray')
        self.canvas.pack()
        
        # Camera controls
        cam_control_frame = ttk.Frame(camera_frame)
        cam_control_frame.pack(pady=5)
        
        ttk.Label(cam_control_frame, text="Camera Index:").pack(side=tk.LEFT, padx=5)
        self.camera_index_var = tk.StringVar(value="1")
        ttk.Entry(cam_control_frame, textvariable=self.camera_index_var, width=5).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(cam_control_frame, text="Start Camera", command=self.start_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(cam_control_frame, text="Stop Camera", command=self.stop_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(cam_control_frame, text="Capture Image", command=self.capture_image).pack(side=tk.LEFT, padx=5)
        
        # Serial connection section
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
        
        # Motor control section
        motor_frame = ttk.LabelFrame(main_frame, text="Motor Control", padding="10")
        motor_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        
        # Movement controls
        ttk.Label(motor_frame, text="Steps:").grid(row=0, column=0, padx=5, pady=5)
        self.steps_var = tk.StringVar(value="1000")
        ttk.Entry(motor_frame, textvariable=self.steps_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(motor_frame, text="Move Relative", command=self.move_relative).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(motor_frame, text="Move Absolute", command=self.move_absolute).grid(row=0, column=3, padx=5, pady=5)
        
        # Jogging controls
        jog_frame = ttk.Frame(motor_frame)
        jog_frame.grid(row=1, column=0, columnspan=4, pady=10)
        
        ttk.Button(jog_frame, text="Jog +", command=lambda: self.jog_move("+")).pack(side=tk.LEFT, padx=5)
        ttk.Button(jog_frame, text="Jog -", command=lambda: self.jog_move("-")).pack(side=tk.LEFT, padx=5)
        ttk.Button(jog_frame, text="Stop", command=self.stop_motor).pack(side=tk.LEFT, padx=5)
        ttk.Button(jog_frame, text="E-Stop", command=self.emergency_stop, 
                   style='Emergency.TButton').pack(side=tk.LEFT, padx=5)
        
        # Additional controls
        control_frame = ttk.Frame(motor_frame)
        control_frame.grid(row=2, column=0, columnspan=4, pady=5)
        
        ttk.Button(control_frame, text="Move to Origin", command=self.move_origin).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Check Status", command=self.check_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Get Angle", command=self.get_angle).pack(side=tk.LEFT, padx=5)
        
        # Speed controls
        speed_frame = ttk.LabelFrame(motor_frame, text="Speed Settings", padding="5")
        speed_frame.grid(row=3, column=0, columnspan=4, pady=10, sticky=(tk.W, tk.E))
        
        ttk.Label(speed_frame, text="Min:").grid(row=0, column=0, padx=2)
        self.min_speed_var = tk.StringVar(value="1000")
        ttk.Entry(speed_frame, textvariable=self.min_speed_var, width=8).grid(row=0, column=1, padx=2)
        
        ttk.Label(speed_frame, text="Max:").grid(row=0, column=2, padx=2)
        self.max_speed_var = tk.StringVar(value="5000")
        ttk.Entry(speed_frame, textvariable=self.max_speed_var, width=8).grid(row=0, column=3, padx=2)
        
        ttk.Label(speed_frame, text="Accel:").grid(row=0, column=4, padx=2)
        self.accel_var = tk.StringVar(value="200")
        ttk.Entry(speed_frame, textvariable=self.accel_var, width=8).grid(row=0, column=5, padx=2)
        
        ttk.Button(speed_frame, text="Set Speed", command=self.set_speed).grid(row=0, column=6, padx=5)
        
        # Response text area
        response_frame = ttk.LabelFrame(main_frame, text="Serial Monitor", padding="10")
        response_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.response_text = tk.Text(response_frame, height=8, width=80)
        self.response_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(response_frame, command=self.response_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.response_text.config(yscrollcommand=scrollbar.set)
        
        # Emergency button style
        style = ttk.Style()
        style.configure('Emergency.TButton', foreground='red')
        
        # Initialize
        self.refresh_ports()
        
    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)
    
    def connect_serial(self):
        try:
            port = self.port_combo.get()
            self.serial_port = serial.Serial(port, 9600, timeout=1)
            self.connection_status.config(text="Connected", foreground="green")
            self.log_response(f"Connected to {port}")
            
            # Start reading thread
            threading.Thread(target=self.read_serial, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.log_response(f"Error: {e}")
    
    def disconnect_serial(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.connection_status.config(text="Disconnected", foreground="red")
            self.log_response("Disconnected")
    
    def send_command(self, command):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.write((command + '\n').encode())
            self.log_response(f"Sent: {command}")
        else:
            messagebox.showwarning("Not Connected", "Please connect to serial port first")
    
    def read_serial(self):
        while self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    response = self.serial_port.readline().decode().strip()
                    self.log_response(f"Received: {response}")
            except:
                break
    
    def log_response(self, message):
        self.response_text.insert(tk.END, message + '\n')
        self.response_text.see(tk.END)
    
    def start_camera(self):
        try:
            self.camera_index = int(self.camera_index_var.get())
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                messagebox.showerror("Camera Error", "Could not access webcam")
                return
            
            self.camera_running = True
            self.update_camera()
            self.log_response(f"Camera {self.camera_index} started")
        except Exception as e:
            messagebox.showerror("Camera Error", str(e))
    
    def stop_camera(self):
        self.camera_running = False
        if self.cap:
            self.cap.release()
        self.camera_index = "1"
        self.canvas.delete("all")
        self.log_response("Camera stopped")
    
    def update_camera(self):
        if self.camera_running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (640, 480))
                
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                
                self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
                self.canvas.imgtk = imgtk
            
            self.root.after(30, self.update_camera)
    
    def capture_image(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"data/photo_{timestamp}.png"
                cv2.imwrite(filename, frame)
                self.log_response(f"Image saved: {filename}")
                messagebox.showinfo("Success", f"Image saved: {filename}")
        else:
            messagebox.showwarning("Camera Error", "Camera not running")
    
    # Motor control commands
    def stop_motor(self):
        self.send_command("STOP")

    def move_relative(self):
        self.stop_motor()
        steps = self.steps_var.get()
        self.send_command(f"MOVE_REL {steps}")
    
    def move_absolute(self):
        self.stop_motor()
        steps = self.steps_var.get()
        self.send_command(f"MOVE_ABS {steps}")
    
    def jog_move(self, direction):
        self.stop_motor()
        self.send_command(f"JOGGING {direction}")
    
    def emergency_stop(self):
        self.stop_motor()
        self.send_command("E")
    
    def move_origin(self):
        self.stop_motor()
        self.send_command("ORIGIN")
    
    def check_status(self):
        self.stop_motor()
        self.send_command("STATUS")
    
    def get_angle(self):
        self.stop_motor()
        self.send_command("ANGLE")
    
    def set_speed(self):
        self.stop_motor()
        min_speed = self.min_speed_var.get()
        max_speed = self.max_speed_var.get()
        accel = self.accel_var.get()
        self.send_command(f"SET SPEED S{min_speed}F{max_speed}R{accel}")
    
    def on_closing(self):
        self.stop_motor()
        self.stop_camera()
        self.disconnect_serial()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CameraMotorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()