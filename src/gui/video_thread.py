import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

class VideoThread(QThread):
    frame_ready = Signal(np.ndarray)

    def __init__(self, src=1, width=None, height=None, parent=None):
        super().__init__(parent)
        self.src = int(src) if str(src).isdigit() else src
        self.width, self.height = width, height
        self._running = True

    def run(self):
        cap = cv2.VideoCapture(self.src, cv2.CAP_ANY)
        if self.width:  cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # reduce latency if supported

        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.msleep(20)
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frame_ready.emit(rgb)

        cap.release()

    def stop(self):
        self._running = False
