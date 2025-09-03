# video_thread.py — unified API
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import cv2
import numpy as np
import time
import os


class VideoThread(QThread):
    """
    Emits:
      - frame_ready(QImage RGB888)  : for painting in UI
      - frame_raw(object np.uint8)  : (H,W,3) RGB for model
      - connection_changed(bool)
      - video_finished()
      - error(str), debug(str)
    """
    frame_ready = Signal(QImage)
    frame_raw = Signal(object)
    connection_changed = Signal(bool)
    video_finished = Signal()
    error = Signal(str)
    debug = Signal(str)

    def __init__(
        self,
        src: str | int = "auto",
        width: int | None = None,
        height: int | None = None,
        target_fps: float | None = None,
        loop_video: bool = True,
    ):
        super().__init__()
        self.src = src
        self.width = int(width) if width else None
        self.height = int(height) if height else None
        self.target_fps = float(target_fps) if target_fps and target_fps > 0 else None
        self.loop_video = bool(loop_video)
        self._running = False
        self._cap: cv2.VideoCapture | None = None

    # ----- internals -----
    def _open_capture(self):
        src = self.src
        cap: cv2.VideoCapture | None = None

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

        # For cameras: try to set resolution
        if self.width and self.height and (not isinstance(src, str) or src == "auto"):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        self.connection_changed.emit(True)
        return cap

    def run(self):
        self._running = True
        self._cap = self._open_capture()
        if self._cap is None:
            return

        fps = self._cap.get(cv2.CAP_PROP_FPS)
        fps = fps if fps and fps > 0 else 25.0
        use_fps = self.target_fps or float(fps)
        delay = 1.0 / max(1e-6, use_fps)

        while self._running:
            ok, frame_bgr = self._cap.read()
            if not ok:
                # If file and looping, restart; else end
                if isinstance(self.src, str) and self.src != "auto" and self.loop_video:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.video_finished.emit()
                break

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            if self.width and self.height:
                rgb = cv2.resize(rgb, (self.width, self.height), interpolation=cv2.INTER_AREA)

            # Emit raw to model
            try:
                self.frame_raw.emit(rgb)
            except Exception:
                pass

            # Emit QImage to UI
            h, w, _ = rgb.shape
            qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
            self.frame_ready.emit(qimg)

            # Pace
            time.sleep(delay)

        # Cleanup
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        self.connection_changed.emit(False)

    def stop(self):
        self._running = False
        try:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
        except Exception:
            pass
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
