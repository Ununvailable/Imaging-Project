import cv2
import os
from PIL import Image
from datetime import datetime

# Create data folder if it doesn't exist
os.makedirs('data', exist_ok=True)

# Initialize webcam (please refer to Window's Device Manager )
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Error: Could not access webcam")
    exit()

# Capture frame
ret, frame = cap.read()

if ret:
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/photo_{timestamp}.png"
    
    # Save image
    cv2.imwrite(filename, frame)
    print(f"Photo saved: {filename}")
else:
    print("Error: Failed to capture image")

# Release webcam
cap.release()