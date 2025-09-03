from __future__ import annotations
from typing import List, Tuple

from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QCheckBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QRect, Signal, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QIcon, QImage, QFont

from .colors import COLORS


# --------------------------- Simple global app state ---------------------------

class AppState:
    """
    Minimal shared state for the GUI. Keeps patient_id globally so
    other modules (e.g., MainWindow for screenshots) can access it.
    """
    patient_id: str = "ID_042"


# ------------------------- Circular Progress -------------------------
class CircularProgress(QWidget):
    def __init__(self, value=0, max_value=100, parent=None):
        super().__init__(parent)
        self.value = int(value)
        self.max_value = int(max_value)
        self.setMinimumSize(140, 140)

    def setValue(self, val: int):
        self.value = max(0, min(self.max_value, int(val)))
        self.update()

    def paintEvent(self, event):
        side = min(self.width(), self.height())
        rect = QRect(10, 10, side - 20, side - 20)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # background ring
        p.setPen(QPen(QColor(*COLORS.get("light_gray", (200, 200, 200))), 12))
        p.drawArc(rect, 0, 360 * 16)

        # progress ring
        span_angle = -int(360 * 16 * self.value / max(1, self.max_value))
        p.setPen(QPen(QColor(*COLORS.get("light_blue", (64, 184, 255))), 12))
        p.drawArc(rect, 90 * 16, span_angle)

        # label
        p.setPen(QColor(*COLORS.get("gray", (80, 80, 80))))
        font = p.font()
        font.setPointSize(14)
        font.setBold(True)
        p.setFont(font)
        p.drawText(rect, Qt.AlignCenter, f"{self.value}%\nAbdeckung")


# ----------------------------- iOS Switch ----------------------------
class Switch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setChecked(True)
        self.setText("")
        self.toggled.connect(self.update)

    def sizeHint(self):
        return QSize(40, 20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = e.rect()
        bg_color = QColor(*COLORS.get("gray", (64, 184, 255))) if self.isChecked() \
                   else QColor(*COLORS.get("light_gray", (220, 220, 220)))

        # background
        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), rect.height() / 2, rect.height() / 2)

        # knob
        knob_d = rect.height() - 4
        x = rect.right() - knob_d - 2 if self.isChecked() else rect.left() + 2
        knob_rect = QRect(x, rect.top() + 2, knob_d, knob_d)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.setPen(QPen(QColor("#E5E7EB")))
        p.drawEllipse(knob_rect)


# --------------------------- Simple Header ---------------------------
class Header(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Header")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(44)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 6)
        lay.setSpacing(8)

        icon_label = QLabel()
        if isinstance(icon, str) and icon.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            pixmap = QPixmap(icon).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText(icon or "")
        icon_label.setFixedWidth(28)

        text = QLabel(title or "")
        text.setObjectName("HeaderTitle")

        lay.addWidget(icon_label)
        lay.addWidget(text, 1)

        if right_widget is not None:
            lay.addWidget(right_widget, 0, Qt.AlignRight)


# ------------------------------- Card --------------------------------
class Card(QFrame):
    """Card with optional header (icon/title/right_widget)."""
    def __init__(self, icon: str = "", title: str = "", right_widget=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = None
        if (icon or title or right_widget is not None):
            self.header = Header(icon, title, right_widget)
            outer.addWidget(self.header, 0)

        self.body = QFrame()
        self.body.setObjectName("CardBody")
        self.body.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.body, 1)

        inner = QVBoxLayout(self.body)
        inner.setContentsMargins(16, 12, 16, 16)
        inner.setSpacing(10)
        self.inner_layout = inner


# ------------------------------- TopBar ------------------------------
class TopBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(12)

        # LEFT cluster (flush-left)
        left = QHBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)  # no gap between icon and title as requested

        cam = QLabel("🎥")
        left.addWidget(cam, 0, Qt.AlignVCenter)

        title = QLabel("Intraop-Assistenz · Blase")
        title.setObjectName("TopTitle")
        title.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        left.addWidget(title, 0, Qt.AlignVCenter)

        # tiny manual gap before the "Demo" badge
        gap = QWidget(); gap.setFixedWidth(8)
        left.addWidget(gap)

        demo = QLabel("Demo")
        demo.setObjectName("Badge_Demo")
        demo.setProperty("small", True)
        demo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        left.addWidget(demo, 0, Qt.AlignVCenter)

        # RIGHT cluster (stays on the right)
        right = QHBoxLayout()
        right.setSpacing(12)

        # Initialize patient id globally
        AppState.patient_id = "ID_042"
        self.patient_pill = QLabel(f"Patient: {AppState.patient_id}")
        self.patient_pill.setObjectName("PatientPill")
        right.addWidget(self.patient_pill)

        self.record_wrap = QWidget()
        self.record_wrap.setObjectName("cameraPill")
        pill = QHBoxLayout(self.record_wrap)
        pill.setContentsMargins(10, 3, 10, 3)
        pill.setSpacing(6)

        self.record_icon = QLabel()
        self.record_icon.setText("📷")  # fallback
        rpix = QPixmap("src/gui/icons/camera.png")
        if not rpix.isNull():
            self.record_icon.setPixmap(rpix.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self.record_text = QLabel("Nicht verbunden")
        pill.addWidget(self.record_icon)
        pill.addWidget(self.record_text)
        right.addWidget(self.record_wrap)

        self.shot_btn = QPushButton(" Screenshot")
        self.shot_btn.setObjectName("ShotBtn")
        self.shot_btn.setIcon(QIcon("src/gui/icons/image.png"))
        right.addWidget(self.shot_btn)

        # Layout order: LEFT | (stretch) | RIGHT
        root.addLayout(left, 0)
        root.addStretch(1)
        root.addLayout(right, 0)

        # initial
        self.set_camera_connected(False)

    def set_camera_connected(self, connected: bool):
        txt = "Kamera verbunden" if connected else "Nicht verbunden"
        self.record_text.setText(txt)

        from .colors import rgb
        bg = rgb("light_blue") if connected else rgb("light_light_gray")
        border = rgb("light_blue") if connected else rgb("light_light_gray")
        fg = rgb("gray")

        self.record_wrap.setStyleSheet(f"""
            QWidget#cameraPill {{
                background:{bg}; border:1px solid {border};
                padding: 4px 10px; border-radius:8px; font-size: 12px;
            }}
            QWidget#cameraPill QLabel {{ color:{fg}; font-weight:600; }}
        """)

    def set_patient_id(self, pid: str):
        AppState.patient_id = pid or AppState.patient_id
        label_text = pid if pid.startswith("Patient") else f"Patient: {AppState.patient_id}"
        self.patient_pill.setText(label_text)


# ----------------------------- VideoCanvas ---------------------------
class VideoCanvas(QLabel):
    """Displays frames, an RGBA overlay, and ROI markers.

    Signals:
      - roiClicked(int x, int y): emitted when in ROI mode and user clicks the image
    """
    roiClicked = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setObjectName("VideoCanvas")
        self.setAlignment(Qt.AlignCenter)
        self._frame: QImage | None = None           # raw frame
        self._overlay: QImage | None = None         # RGBA overlay (same or different size)
        self._overlay_opacity: float = 0.7
        self._roi_mode: bool = False
        self._markers: List[Tuple[QPointF, str]] = []

    # ---------- public API ----------
    def set_frame(self, qimg: QImage):
        self._frame = qimg
        self.update()

    def set_overlay(self, qimg_rgba: QImage | None):
        self._overlay = qimg_rgba
        self.update()

    def clear_overlay(self):
        self._overlay = None
        self.update()

    def set_overlay_opacity(self, value: float):
        self._overlay_opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def set_roi_mode(self, on: bool):
        self._roi_mode = bool(on)
        self.setCursor(Qt.CrossCursor if self._roi_mode else Qt.ArrowCursor)

    def add_marker(self, x: int, y: int, label: int | str | None = None):
        if label is None:
            label = len(self._markers) + 1
        label_str = f"#{int(label)}" if isinstance(label, (int, float)) else str(label)
        self._markers.append((QPointF(x, y), label_str))
        self.update()

    def clear_markers(self):
        self._markers.clear()
        self.update()

    # ---------- helpers ----------
    def _calc_draw_rect(self, src_w: int, src_h: int) -> QRect:
        """Return letterboxed target rect where a (src_w, src_h) image should be drawn."""
        lab_w, lab_h = self.width(), self.height()
        if src_w <= 0 or src_h <= 0 or lab_w <= 0 or lab_h <= 0:
            return QRect(0, 0, 0, 0)
        scale = min(lab_w / src_w, lab_h / src_h)
        draw_w = int(src_w * scale)
        draw_h = int(src_h * scale)
        off_x = (lab_w - draw_w) // 2
        off_y = (lab_h - draw_h) // 2
        return QRect(off_x, off_y, draw_w, draw_h)

    # ---------- events ----------
    def mousePressEvent(self, ev):
        if self._roi_mode and self._frame is not None:
            src_w, src_h = self._frame.width(), self._frame.height()
            tr = self._calc_draw_rect(src_w, src_h)
            if tr.width() > 0 and tr.height() > 0:
                # map click back to frame coordinates
                x = int((ev.position().x() - tr.x()) * (src_w / tr.width()))
                y = int((ev.position().y() - tr.y()) * (src_h / tr.height()))
                if 0 <= x < src_w and 0 <= y < src_h:
                    self.roiClicked.emit(x, y)
                return
        super().mousePressEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # fill background (in case of letterboxing)
        p.fillRect(self.rect(), self.palette().window())

        # --- base frame, letterboxed, no cropping ---
        if self._frame is not None and not self._frame.isNull():
            src_w, src_h = self._frame.width(), self._frame.height()
            target = self._calc_draw_rect(src_w, src_h)
            if target.width() > 0 and target.height() > 0:
                p.drawImage(target, self._frame)

            # --- overlay (same target rect mapping) ---
            if self._overlay is not None and not self._overlay.isNull():
                p.setOpacity(self._overlay_opacity)
                p.drawImage(target, self._overlay)
                p.setOpacity(1.0)

            # --- ROI markers ---
            if self._markers:
                sx = target.width() / max(1, src_w)
                sy = target.height() / max(1, src_h)
                pen_x = QPen(QColor(*COLORS.get("light_blue", (64, 184, 255))), 2)
                p.setPen(pen_x)

                font = p.font()
                font.setPointSize(11)
                font.setBold(True)
                p.setFont(font)

                for point, label_str in self._markers:
                    x = target.x() + int(point.x() * sx)
                    y = target.y() + int(point.y() * sy)
                    s = 10
                    p.setPen(pen_x)
                    p.drawLine(x - s, y - s, x + s, y + s)
                    p.drawLine(x - s, y + s, x + s, y - s)

                    p.setPen(QPen(QColor(0, 0, 0, 200)))
                    p.drawText(x + s + 5, y - s - 2, label_str)
                    p.setPen(QPen(QColor(255, 255, 255)))
                    p.drawText(x + s + 4, y - s - 3, label_str)

        p.end()
