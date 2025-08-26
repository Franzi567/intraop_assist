from PySide6.QtCore import QThread, Signal
import cv2

class VideoThread(QThread):
    frame_ready = Signal(object)
    connection_changed = Signal(bool)   # <-- new signal

    def __init__(self, src=0, width=640, height=480):
        super().__init__()
        self.src = src
        self.width = width
        self.height = height
        self._running = True
        self._connected = False

    def run(self):
        cap = cv2.VideoCapture(self.src)
        if not cap.isOpened():
            self.connection_changed.emit(False)
            return

        self.connection_changed.emit(True)
        self._connected = True

        while self._running:
            ok, frame = cap.read()
            if not ok:
                if self._connected:
                    self.connection_changed.emit(False)
                    self._connected = False
                continue
            else:
                if not self._connected:
                    self.connection_changed.emit(True)
                    self._connected = True

                self.frame_ready.emit(frame[..., ::-1])  # BGR→RGB

        cap.release()

    def stop(self):
        self._running = False
        self.wait()
