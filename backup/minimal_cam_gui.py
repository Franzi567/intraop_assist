import sys, cv2, numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QHBoxLayout, QStatusBar

class CaptureThread(QThread):
    frame_ready = Signal(np.ndarray)
    def __init__(self, src, width=None, height=None, parent=None):
        super().__init__(parent)
        self.src = int(src) if str(src).isdigit() else src
        self.width, self.height = width, height
        self._running = True

    def run(self):
        cap = cv2.VideoCapture(self.src, cv2.CAP_ANY)
        if self.width:  cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        if self.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.msleep(10)
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frame_ready.emit(rgb)

        cap.release()

    def stop(self):
        self._running = False

class VideoLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setText("Waiting for camera…")

    def update_frame(self, rgb: np.ndarray):
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(img))

class MainWindow(QMainWindow):
    def __init__(self, src):
        super().__init__()
        self.setWindowTitle("Bladder GUI – Camera MVP")
        self.label = VideoLabel()
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.addWidget(self.label)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Source: {src}")

        self.th = CaptureThread(src, width=1280, height=720)
        self.th.frame_ready.connect(self.label.update_frame)
        self.th.start()

    def closeEvent(self, e):
        self.th.stop()
        self.th.wait(1000)
        super().closeEvent(e)

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "0"
    app = QApplication(sys.argv)
    win = MainWindow(src)
    win.resize(1280, 720)
    win.show()
    sys.exit(app.exec())
