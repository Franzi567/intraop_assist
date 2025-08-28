from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QCheckBox,
    QSizePolicy
)
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Qt, QPoint, QRect
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont

from PySide6.QtCore import Qt, QSize, QRect, QPointF, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QIcon, QImage
import math

from .colors import rgb, COLORS


from .colors import COLORS

# ---- Circular Progress for Abdeckung ----
class CircularProgress(QWidget):
    def __init__(self, value=0, max_value=100, parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.setMinimumSize(140, 140)

    def setValue(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        side = min(self.width(), self.height())
        rect = QRect(10, 10, side-20, side-20)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Hintergrund (grau)
        p.setPen(QPen(QColor(*COLORS["light_gray"]), 12))
        p.drawArc(rect, 0, 360*16)

        # Vordergrund (blau)
        span_angle = -int(360 * 16 * self.value / self.max_value)
        p.setPen(QPen(QColor(*COLORS["light_blue"]), 12))
        p.drawArc(rect, 90*16, span_angle)

        # Text
        p.setPen(QColor(*COLORS["gray"]))
        font = p.font(); font.setPointSize(14); font.setBold(True)
        p.setFont(font)
        p.drawText(rect, Qt.AlignCenter, f"{self.value}%\nAbdeckung")
        p.end()

# ---- iOS style Switch ----
class Switch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setChecked(True)
        self.setText("")

    def sizeHint(self):
        return QSize(40, 20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = e.rect()
        bg_color = QColor(*COLORS["light_blue"]) if self.isChecked() else QColor(*COLORS["light_gray"])

        # Hintergrund
        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), rect.height()/2, rect.height()/2)

        # Knopf
        knob_d = rect.height() - 4
        x = rect.right() - knob_d - 2 if self.isChecked() else rect.left() + 2
        knob_rect = QRect(x, rect.top()+2, knob_d, knob_d)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.setPen(QPen(QColor("#E5E7EB")))
        p.drawEllipse(knob_rect)
        p.end()

# ---- reusable UI pieces ----
class Header(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Header")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(44)
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 10, 12, 6); lay.setSpacing(8)

        icon_label = QLabel()
        if isinstance(icon, str) and icon.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            pixmap = QPixmap(icon).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText(icon)  # emoji fallback
        icon_label.setFixedWidth(28)

        text = QLabel(title); text.setObjectName("HeaderTitle")
        lay.addWidget(icon_label); lay.addWidget(text, 1)

        if right_widget is not None:
            lay.addWidget(right_widget, 0, Qt.AlignRight)

class Card(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        self.header = Header(icon, title, right_widget)
        self.body = QFrame(); self.body.setObjectName("CardBody")
        self.body.setAttribute(Qt.WA_StyledBackground, True)

        inner = QVBoxLayout(self.body); inner.setContentsMargins(16, 12, 16, 16); inner.setSpacing(10)
        self.inner_layout = inner

        outer.addWidget(self.header); outer.addWidget(self.body, 1)

# ---- Top Bar ----
class TopBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        # left container (icon, camera icon + status, title, demo badge)
        left_wrap = QWidget()
        left_layout = QHBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # app icon
        app_icon = QLabel()
        pix_app = QPixmap("src/gui/icons/app_icon.png")
        if not pix_app.isNull():
            app_icon.setPixmap(pix_app.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            app_icon.setText("🏥")
        app_icon.setFixedWidth(22)
        left_layout.addWidget(app_icon, 0)

        # camera icon
        cam_icon = QLabel()
        pix_cam = QPixmap("src/gui/icons/camera.png")
        if not pix_cam.isNull():
            cam_icon.setPixmap(pix_cam.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            cam_icon.setText("🎥")
        cam_icon.setFixedWidth(20)
        cam_icon.setAlignment(Qt.AlignVCenter)
        left_layout.addWidget(cam_icon, 0)

        # camera status text (make it flexible but not expand to swallow title)
        self.camera_label = QLabel("Keine Kamera")
        self.camera_label.setObjectName("CameraStatus")
        # let this shrink if needed, but keep visible and vertically centered
        self.camera_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.camera_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        left_layout.addWidget(self.camera_label, 0)

        # title: allow to expand but prefer not to steal the camera label's space
        title = QLabel("Intraop-Assistenz · Blase")
        title.setObjectName("TopTitle")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        left_layout.addWidget(title, 1)

        # demo badge — use same visual height as patient pill (CSS below)
        demo_badge = QLabel("Demo")
        demo_badge.setObjectName("Badge_Demo")
        demo_badge.setProperty("small", True)
        demo_badge.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        left_layout.addWidget(demo_badge, 0, Qt.AlignVCenter)

        lay.addWidget(left_wrap, 0)

        # stretch to push right side to the far right
        lay.addStretch(1)

        # right side: patient pill, record pill, screenshot (unchanged)
        right = QHBoxLayout()
        right.setSpacing(12)

        self.patient = QLabel("Patient: ID-042")
        self.patient.setObjectName("PatientPill")

        record_icon = QLabel()
        pix = QPixmap("src/gui/icons/camera.png")
        if not pix.isNull():
            record_icon.setPixmap(pix.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            record_icon.setText("📷")

        self.record_text = QLabel(" Aufzeichnung")
        self.record_wrap = QWidget()
        self.record_wrap.setObjectName("RecordPill")
        self.record_wrap.setProperty("connected", False)
        rlayout = QHBoxLayout(self.record_wrap)
        rlayout.setContentsMargins(8, 0, 8, 0)
        rlayout.setSpacing(6)
        rlayout.addWidget(record_icon)
        rlayout.addWidget(self.record_text)

        screenshot = QPushButton(" Screenshot")
        screenshot.setObjectName("ShotBtn")
        screenshot.setIcon(QIcon("src/gui/icons/image.png"))

        right.addWidget(self.patient)
        right.addWidget(self.record_wrap)
        right.addWidget(screenshot)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        lay.addWidget(right_wrap, 0, Qt.AlignRight)

    def set_camera_text(self, text: str):
        self.camera_label.setText(text)
        # keep style in sync if you toggle properties externally
        self.camera_label.style().unpolish(self.camera_label)
        self.camera_label.style().polish(self.camera_label)

# widgets_video_canvas.py (copy into your widgets module or replace existing VideoCanvas)
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import QPixmap, QImage
import typing

class VideoCanvas(QLabel):
    """
    Minimal video display widget that supports:
      - set_frame(QImage) : show base frame
      - set_overlay(QImage) : set RGBA overlay (scaled to frame)
      - clear_overlay()
      - set_overlay_opacity(float)
      - begin_annotation / cancel_annotation stubs and roi_marked signal
    """
    roi_marked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_qimg: typing.Optional[QImage] = None
        self._overlay_qimg: typing.Optional[QImage] = None
        self._overlay_opacity: float = 0.7
        self.setAlignment(Qt.AlignCenter)
        self._next_roi_label = 1
        # make widget scale contents but preserve aspect ratio
        self.setScaledContents(False)

    def set_frame(self, qimg: QImage):
        """Display a frame (QImage). If overlay exists and opacity > 0, show composited version."""
        if qimg is None:
            return
        self._base_qimg = qimg
        # if overlay and toggle is handled externally, caller will pass composited QImage already.
        # If overlay exists in this widget, composite here:
        if self._overlay_qimg is not None:
            # composite using QPainter
            base = self._base_qimg.convertToFormat(QImage.Format.Format_RGBA8888)
            ov = self._overlay_qimg
            if ov.format() != QImage.Format.Format_RGBA8888:
                ov = ov.convertToFormat(QImage.Format.Format_RGBA8888)
            if ov.size() != base.size():
                ov = ov.scaled(base.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            # draw overlay on base
            from PySide6.QtGui import QPainter
            res = base.copy()
            painter = QPainter(res)
            painter.setOpacity(self._overlay_opacity)
            painter.drawImage(0, 0, ov)
            painter.end()
            out = res.convertToFormat(QImage.Format.Format_RGB888)
        else:
            # show base directly
            out = self._base_qimg.convertToFormat(QImage.Format.Format_RGB888)

        pix = QPixmap.fromImage(out)
        self.setPixmap(pix)

    def set_overlay(self, overlay_qimg: QImage):
        """Set an RGBA overlay image (QImage). We'll composite it onto future frames."""
        if overlay_qimg is None:
            self._overlay_qimg = None
        else:
            if overlay_qimg.format() != QImage.Format.Format_RGBA8888:
                try:
                    overlay_qimg = overlay_qimg.convertToFormat(QImage.Format.Format_RGBA8888)
                except Exception:
                    pass
            self._overlay_qimg = overlay_qimg

    def clear_overlay(self):
        self._overlay_qimg = None
        # refresh display
        if self._base_qimg is not None:
            self.set_frame(self._base_qimg)

    def set_overlay_opacity(self, opacity: float):
        self._overlay_opacity = max(0.0, min(1.0, float(opacity)))
        if self._base_qimg is not None:
            self.set_frame(self._base_qimg)

    # --- ROI stubs (expand as needed) ---
    def begin_annotation(self, label_num: int):
        # In a full implementation you'd enter mouse-capture mode; here just return True
        return True

    def cancel_annotation(self):
        return True

    # Example to emit roi_marked (call when annotation finished in a real implementation)
    def _emit_roi_marked(self):
        self.roi_marked.emit(self._next_roi_label)
        self._next_roi_label += 1





# ---- Circular Progress for Abdeckung ----
class CircularProgress(QWidget):
    def __init__(self, value=0, max_value=100, parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.setMinimumSize(140, 140)

    def setValue(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        side = min(self.width(), self.height())
        rect = QRect(10, 10, side-20, side-20)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Hintergrund (grau)
        p.setPen(QPen(QColor(*COLORS["light_gray"]), 12))
        p.drawArc(rect, 0, 360*16)

        # Vordergrund (blau)
        span_angle = -int(360 * 16 * self.value / self.max_value)
        p.setPen(QPen(QColor(*COLORS["dark_blue"]), 12))
        p.drawArc(rect, 90*16, span_angle)

        # Text
        p.setPen(QColor(*COLORS["gray"]))
        font = p.font(); font.setPointSize(12); font.setBold(True)
        p.setFont(font)
        p.drawText(rect, Qt.AlignCenter, f"{self.value}%\nAbdeckung")
        p.end()

# ---- iOS style Switch ----
class Switch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setChecked(True)
        self.setText("")

    def sizeHint(self):
        return QSize(40, 20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = e.rect()
        bg_color = QColor(*COLORS["gray"]) if self.isChecked() else QColor(*COLORS["light_gray"])

        # Background
        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), rect.height()/2, rect.height()/2)

        # Knopf
        knob_d = rect.height() - 4
        x = rect.right() - knob_d - 2 if self.isChecked() else rect.left() + 2
        knob_rect = QRect(x, rect.top()+2, knob_d, knob_d)
        p.setBrush(QBrush(QColor(*COLORS["white"])))
        p.setPen(QPen(QColor(*COLORS["light_gray"])))
        p.drawEllipse(knob_rect)
        p.end()

# ---- reusable UI pieces ----
class Header(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Header")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 10, 12, 6); lay.setSpacing(8)

        icon_label = QLabel()
        if isinstance(icon, str) and icon.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            pixmap = QPixmap(icon).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText(icon)  # emoji fallback
        icon_label.setFixedWidth(28)

        text = QLabel(title); text.setObjectName("HeaderTitle")
        lay.addWidget(icon_label); lay.addWidget(text, 1)

        if right_widget is not None:
            lay.addWidget(right_widget, 0, Qt.AlignRight)

class Card(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        self.header = Header(icon, title, right_widget)
        self.body = QFrame(); self.body.setObjectName("CardBody")
        self.body.setAttribute(Qt.WA_StyledBackground, True)

        inner = QVBoxLayout(self.body); inner.setContentsMargins(16, 12, 16, 16); inner.setSpacing(10)
        self.inner_layout = inner

        outer.addWidget(self.header); outer.addWidget(self.body, 1)

# ---- Top Bar ----
class TopBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        # Left: icon + title + demo badge (title given expanding policy)
        icon = QLabel("🎥")
        title = QLabel("Intraop-Assistenz · Blase")
        title.setObjectName("TopTitle")
        # allow the title to expand and keep left-aligned
        from PySide6.QtWidgets import QSizePolicy
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        demo_badge = QLabel("Demo")
        demo_badge.setObjectName("Badge_Demo")

        left_wrap = QWidget()
        left_layout = QHBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(icon)
        left_layout.addWidget(title, 1)         # title gets stretch weight
        left_layout.addWidget(demo_badge)
        lay.addWidget(left_wrap)

        # Add stretch so left content stays left and right content stays right
        lay.addStretch(1)

        # Right: patient pill, record pill, screenshot
        right = QHBoxLayout()
        right.setSpacing(12)

        self.patient = QLabel("Patient: ID-042")
        self.patient.setObjectName("PatientPill")

        record_icon = QLabel()
        pix = QPixmap("src/gui/icons/camera.png")
        if not pix.isNull():
            record_icon.setPixmap(pix.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            record_icon.setText("📷")

        self.record_text = QLabel(" Connected")
        self.record_wrap = QWidget()
        self.record_wrap.setObjectName("RecordPill")
        self.record_wrap.setProperty("connected", False)
        rlayout = QHBoxLayout(self.record_wrap)
        rlayout.setContentsMargins(8, 0, 8, 0)
        rlayout.setSpacing(6)
        rlayout.addWidget(record_icon)
        rlayout.addWidget(self.record_text)

        screenshot = QPushButton(" Screenshot")
        screenshot.setObjectName("ShotBtn")
        screenshot.setIcon(QIcon("src/gui/icons/image.png"))

        right.addWidget(self.patient)
        right.addWidget(self.record_wrap)
        right.addWidget(screenshot)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        lay.addWidget(right_wrap, 0, Qt.AlignRight)



