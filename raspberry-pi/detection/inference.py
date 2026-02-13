"""
Inference Pipeline
Handles frame capture, preprocessing, and detection.

- Tries OpenCV (USB webcam) first.
- Falls back to Picamera2 (rpicam) if OpenCV fails.
- If both fail, runs without camera: capture_frame() returns None so the app still starts.
"""

import logging
import time
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except Exception:
    Picamera2 = None
    PICAMERA2_AVAILABLE = False


class InferencePipeline:
    """Manages camera capture and inference pipeline"""

    def __init__(self, camera_id: int = 0, resolution: Tuple[int, int] = (320, 240)):
        self.camera_id = camera_id
        self.resolution = resolution
        self.cap = None
        self.picam2 = None
        self._no_camera = False
        self._init_camera()

    def _try_opencv_index(self, index: int):
        """Try to open and read one frame from the given OpenCV index. Returns cap if ok, else None."""
        try:
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                return None
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            # Some webcams need a couple of reads before returning a frame
            for _ in range(5):
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    self.cap = cap
                    logger.info("Camera initialized via OpenCV (index=%s) %sx%s",
                                index, self.resolution[0], self.resolution[1])
                    return True
                time.sleep(0.2)
            cap.release()
        except Exception:
            pass
        return False

    def _init_camera(self):
        # 1) Try OpenCV: configured index first, then scan 0..20
        if self._try_opencv_index(self.camera_id):
            return
        for idx in range(0, 21):
            if idx == self.camera_id:
                continue
            if self._try_opencv_index(idx):
                return

        # 2) Try Picamera2
        if PICAMERA2_AVAILABLE:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_video_configuration(
                    main={"size": (self.resolution[0], self.resolution[1]), "format": "BGR888"}
                )
                self.picam2.configure(config)
                self.picam2.start()
                logger.info("Camera initialized via Picamera2 %sx%s",
                             self.resolution[0], self.resolution[1])
                return
            except Exception as e:
                logger.warning("Picamera2 failed: %s", e)
                self.picam2 = None

        # 3) No camera: allow app to run anyway (capture_frame will return None)
        self._no_camera = True
        logger.warning(
            "No camera available (tried OpenCV indices 0-20 and Picamera2). "
            "App will run but detection will skip. Try: other USB port, different webcam (e.g. Logitech C270), or run: python -c \"import cv2; [print(i, cv2.VideoCapture(i).read()[0]) for i in range(20)]\""
        )

    def capture_frame(self) -> Optional[np.ndarray]:
        if self._no_camera:
            return None
        if self.cap is not None:
            if not self.cap.isOpened():
                return None
            ret, frame = self.cap.read()
            return frame if ret else None
        if self.picam2 is not None:
            try:
                return self.picam2.capture_array()
            except Exception:
                return None
        return None

    def release(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except Exception:
                pass
            self.picam2 = None

    def __del__(self):
        self.release()
