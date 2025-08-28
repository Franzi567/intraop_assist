# inside VideoCanvas class
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage
from PySide6.QtCore import Qt

class VideoCanvas(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._frame = None         # QImage RGB for display
        self._overlay = None  # QImage RGBA or None
        self._overlay_opacity = 0.7

    def set_overlay(self, qimg: QImage):
        """Set the RGBA overlay QImage (will be drawn on top of the video)."""
        try:
            self._overlay = qimg
            self.update()
        except Exception:
            pass

    def clear_overlay(self):
        self._overlay = None
        self.update()

    def set_overlay_opacity(self, opacity: float):
        self._overlay_opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    def set_frame(self, qimg: QImage):
        """Called from main thread to update the base frame (display)."""
        self._frame = qimg
        self.update()

    def set_overlay(self, qimg: QImage):
        """Called by ModelWorker when an overlay is produced (RGBA)."""
        self._overlay = qimg
        self.update()

    def set_overlay_opacity(self, alpha_float: float):
        """alpha_float between 0.0 and 1.0"""
        self._overlay_alpha = max(0.0, min(1.0, float(alpha_float)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        # draw base frame (scaled to widget)
        if self._frame is not None and not self._frame.isNull():
            scaled = self._frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            # center
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)

            # draw overlay on top (if present)
            if self._overlay is not None:
                painter.save()
                painter.setOpacity(self._overlay_opacity)
                # center/scale overlay to fit current widget size or match frame size
                target = self._overlay.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # draw centered
                x = (self.width() - target.width()) // 2
                y = (self.height() - target.height()) // 2
                painter.drawImage(x, y, target)
                painter.restore()
        else:
            # nothing to show -> fill background
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
