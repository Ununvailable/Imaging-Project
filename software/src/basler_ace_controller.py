"""
Basler Ace camera controller.
Wraps pypylon InstantCamera: open/close, grab, resolution, exposure/gain locking.
No GUI or acquisition-sequence logic here.
"""

from pypylon import pylon


class BaslerAceController:
    def __init__(self):
        self.camera = None
        self.converter = None

    def open(self, width: int = None, height: int = None):
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()

        if width is not None:
            self.camera.Width.Value = min(width, self.camera.Width.Max)
        if height is not None:
            self.camera.Height.Value = min(height, self.camera.Height.Max)

        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    def close(self):
        if self.camera is None:
            return
        if self.camera.IsGrabbing():
            self.camera.StopGrabbing()
        if self.camera.IsOpen():
            self.camera.Close()
        self.camera = None

    def start_grabbing(self):
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    def stop_grabbing(self):
        if self.camera is not None and self.camera.IsGrabbing():
            self.camera.StopGrabbing()

    def grab_frame(self, timeout_ms: int = 1000):
        if not self.is_grabbing():
            return None
        grab_result = self.camera.RetrieveResult(timeout_ms, pylon.TimeoutHandling_Return)
        try:
            if not grab_result.GrabSucceeded():
                return None
            image = self.converter.Convert(grab_result)
            return image.GetArray()  # BGR numpy array
        finally:
            grab_result.Release()

    def set_exposure(self, exposure_us: float, auto_off: bool = True):
        if auto_off:
            self.camera.ExposureAuto.SetValue("Off")
        self.camera.ExposureTime.SetValue(exposure_us)

    def set_gain(self, gain: float, auto_off: bool = True):
        if auto_off:
            self.camera.GainAuto.SetValue("Off")
        self.camera.Gain.SetValue(gain)

    def is_open(self) -> bool:
        return self.camera is not None and self.camera.IsOpen()

    def is_grabbing(self) -> bool:
        return self.camera is not None and self.camera.IsGrabbing()