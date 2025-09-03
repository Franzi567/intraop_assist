# video_thread.py — unified API with frame_id for perfect sync
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
      - frame_ready(QImage RGB888, int frame_id)  : for painting in UI
      - frame_raw(object np.uint8, int frame_id)  : (H,W,3) RGB for model
      - connection_changed(bool)
      - video_finished()
      - error(str), debug(str)
    """
    frame_ready = Signal(QImage, int)
    frame_raw = Signal(object, int)
    connection_changed = Signal(bool)
    video_finished = Signal()
    error = Signal(str)
    debug = Signal(str)

    def __init__(self, src: str | int = "auto", width: int | None = None,
                 height: int | None = None, target_fps: float | None = None,
                 loop_video: bool = True):
        super().__init__()
        self.src = src
        self.width = int(width) if width else None
        self.height = int(height) if height else None
        self.target_fps = float(target_fps) if target_fps and target_fps > 0 else None
        self.loop_video = bool(loop_video)
        self._running = False
        self._cap: cv2.VideoCapture | None = None
        self._frame_id = 0

    def _open_capture(self):
        src = self.src
        cap = None

        if isinstance(src, str) and src == "auto":
            # Prefer a direct camera backend if available to minimize buffering
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(0)
            if not cap or not cap.isOpened():
                self.error.emit("No camera found for 'auto' source")
                self.connection_changed.emit(False)
                return None
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        elif isinstance(src, str):
            if not os.path.exists(src):
                self.error.emit(f"Video file not found: {src}")
                self.connection_changed.emit(False)
                return None
            cap = cv2.VideoCapture(src)
        else:
            cap = cv2.VideoCapture(int(src))
            if cap and cap.isOpened():
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

        if not cap or not cap.isOpened():
            self.error.emit("Failed to open video source.")
            self.connection_changed.emit(False)
            return None

        # Keep native resolution — no forced resizing (prevents “zoomed” look)
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
                if isinstance(self.src, str) and self.src != "auto" and self.loop_video:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.video_finished.emit()
                break

            # Increment id for each *captured* frame
            self._frame_id += 1
            fid = self._frame_id

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # Emit raw for model (MainWindow will throttle/lock to pairs)
            try:
                self.frame_raw.emit(rgb, fid)
            except Exception:
                pass

            h, w, _ = rgb.shape
            # QImage shares data; copy() when delivering to UI to ensure safety
            qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
            self.frame_ready.emit(qimg, fid)

            time.sleep(delay)

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
                self._cap.release()
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
