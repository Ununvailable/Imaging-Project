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
        """Open first detected Basler device, optionally set resolution."""
        raise NotImplementedError

    def close(self):
        """Stop grabbing and close camera if open."""
        raise NotImplementedError

    def start_grabbing(self):
        raise NotImplementedError

    def stop_grabbing(self):
        raise NotImplementedError

    def grab_frame(self, timeout_ms: int = 1000):
        """Return a single BGR numpy array, or None on failed/timed-out grab."""
        raise NotImplementedError

    def set_exposure(self, exposure_us: float, auto_off: bool = True):
        raise NotImplementedError

    def set_gain(self, gain: float, auto_off: bool = True):
        raise NotImplementedError

    def is_open(self) -> bool:
        raise NotImplementedError

    def is_grabbing(self) -> bool:
        raise NotImplementedError
