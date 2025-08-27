from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import sys, time
import cv2

class VideoThread(QThread):
    # Emit QImage (thread-safe to pass; QPixmap is not)
    frame_ready = Signal(QImage)
    connection_changed = Signal(bool)

    def __init__(self, src=0, width=640, height=480, target_fps=30):
        super().__init__()
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        self.src = src
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self._running = True

    def _open(self):
        apis = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if sys.platform.startswith("win") else [cv2.CAP_ANY]
        for api in apis:
            cap = cv2.VideoCapture(self.src, api)
            if cap.isOpened():
                if self.width:  cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
                if self.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # reduce latency
                except Exception:
                    pass
                return cap
            else:
                try:
                    cap.release()
                except Exception:
                    pass
        return None

    def run(self):
        period = 1.0 / max(1, self.target_fps)
        last_emit = 0.0
        cap = None
        connected = False

        while self._running:
            if cap is None or not cap.isOpened():
                cap = self._open()
                if cap is None:
                    if connected:
                        self.connection_changed.emit(False)
                        connected = False
                    self.msleep(500)
                    continue
                else:
                    if not connected:
                        self.connection_changed.emit(True)
                        connected = True

            ok, frame = cap.read()
            if not ok:
                # camera hiccup: close and retry
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
                if connected:
                    self.connection_changed.emit(False)
                    connected = False
                self.msleep(200)
                continue

            now = time.time()
            if (now - last_emit) >= period:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # contiguous uint8
                h, w = rgb.shape[:2]
                qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(qimg)
                last_emit = now
            # else: drop frame to keep latency low

        # graceful stop
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def stop(self):
        self._running = False
