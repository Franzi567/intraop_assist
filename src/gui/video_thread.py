# video_thread.py — unified API
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import cv2
import numpy as np
import time
import os

class VideoThread(QThread):
    # Modernized signal set expected by MainWindow
    frame_ready = Signal(QImage)        # QImage (RGB888) for painting
    frame_raw = Signal(object)          # numpy RGB uint8 (H,W,3) for model
    connection_changed = Signal(bool)   # camera/file "connected"
    video_finished = Signal()           # file finished (if not looping)
    error = Signal(str)                 # user-visible errors
    debug = Signal(str)                 # low-importance logs

    def __init__(self,
                 src: str | int = "auto",
                 width: int | None = None,
                 height: int | None = None,
                 target_fps: float | None = None,
                 loop_video: bool = True):
        super().__init__()
        self.src = src
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.loop_video = bool(loop_video)
        self._running = False
        self._cap = None

    def _open_capture(self):
        src = self.src
        cap = None

        if isinstance(src, str) and src == "auto":
            cap = cv2.VideoCapture(0)
            if not cap or not cap.isOpened():
                self.error.emit("No camera found for 'auto' source")
                self.connection_changed.emit(False)
                return None
        elif isinstance(src, str):
            if not os.path.exists(src):
                self.error.emit(f"Video file not found: {src}")
                self.connection_changed.emit(False)
                return None
            cap = cv2.VideoCapture(src)
        else:
            cap = cv2.VideoCapture(int(src))

        if not cap or not cap.isOpened():
            self.error.emit("Failed to open video source.")
            self.connection_changed.emit(False)
            return None

        self.connection_changed.emit(True)
        return cap

    def run(self):
        self._running = True
        self._cap = self._open_capture()
        if self._cap is None:
            return

        # FPS pacing
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        fps = fps if fps and fps > 0 else 25.0
        use_fps = float(self.target_fps) if (self.target_fps and self.target_fps > 0) else float(fps)
        delay = 1.0 / use_fps

        while self._running:
            ok, frame_bgr = self._cap.read()
            if not ok:
                # For files: loop if requested
                if isinstance(self.src, str) and self.src != "auto" and self.loop_video:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    self.video_finished.emit()
                    break

            # Convert to RGB
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # Optional resize (keeps model + display consistent size if you want)
            if self.width and self.height:
                rgb = cv2.resize(rgb, (int(self.width), int(self.height)), interpolation=cv2.INTER_AREA)

            # Emit raw for model
            try:
                self.frame_raw.emit(rgb)
            except Exception:
                pass

            # Emit QImage for painting
            h, w, _ = rgb.shape
            qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
            self.frame_ready.emit(qimg)

            # Pace
            if delay > 0:
                time.sleep(delay)

        try:
            self._cap.release()
        except Exception:
            pass
        self.connection_changed.emit(False)

    def stop(self):
        # signal the loop to end
        self._running = False
        # actively release capture to unblock cv2.VideoCapture.read()
        try:
            if hasattr(self, "_cap") and self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
        except Exception:
            pass
        # if the thread is still running, wait for it to finish
        try:
            if self.isRunning():
                self.wait(1500)
        except Exception:
            pass

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
