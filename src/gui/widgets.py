from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QCheckBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QRect, QPointF, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QIcon
import math

from .colors import rgb, COLORS

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



# ... keep your imports ...
from PySide6.QtCore import Qt, QSize, QRect, QPointF, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QFont
import math

from .colors import COLORS

# ... keep your imports ...
from PySide6.QtCore import Qt, QSize, QRect, QPointF, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QFont
import math

from .colors import COLORS

class VideoCanvas(QLabel):
    # now emits also the note number (label_num)
    roi_marked = Signal(int)  # x, y (image px), label_num

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Kein Video")
        self._qimg = None              # last QImage
        self._img_size = None          # (w, h)
        self._target_rect = QRect()    # where the image is drawn inside label
        self._annotations = []         # [{pt_img: QPointF, label: int}]
        self._annotate_active = False
        self._pending_label = None     # int or None

    # ---------- public API ----------
    def set_frame(self, qimg):
        self._qimg = qimg
        self._img_size = (qimg.width(), qimg.height())
        self._update_pixmap()

    def begin_annotation(self, label_num: int) -> bool:
        """Enable one-shot annotation mode and set the label for the next mark."""
        if self._qimg is None:
            return False
        self._annotate_active = True
        self._pending_label = int(label_num)
        self.setCursor(Qt.CrossCursor)
        return True

    def cancel_annotation(self):
        self._annotate_active = False
        self._pending_label = None
        self.unsetCursor()
        self._update_pixmap()

    # ---------- events / drawing ----------
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_pixmap()

    def mousePressEvent(self, e):
        # single-click to drop an X
        if not self._annotate_active or e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        if not self._target_rect.contains(e.pos()):
            self.cancel_annotation()
            return

        # label coords -> image coords
        pt_img = self._label_to_img(QPointF(e.position()))
        if pt_img is None:
            self.cancel_annotation()
            return

        label_num = int(self._pending_label) if self._pending_label is not None else 0
        self._annotations.append({"pt_img": pt_img, "label": label_num})
        self._update_pixmap()

        # emit and exit one-shot mode
        self.roi_marked.emit(label_num)
        self.cancel_annotation()

    def _update_pixmap(self):
        if self._qimg is None or self.width() <= 0 or self.height() <= 0:
            return

        base = QPixmap.fromImage(self._qimg)
        scaled = base.scaled(self.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        x_off = (self.width() - scaled.width()) // 2
        y_off = (self.height() - scaled.height()) // 2
        self._target_rect = QRect(x_off, y_off, scaled.width(), scaled.height())

        composed = QPixmap(self.size())
        composed.fill(Qt.transparent)
        p = QPainter(composed)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(self._target_rect.topLeft(), scaled)

        # draw all stored X markers + labels
        for ann in self._annotations:
            pt_lbl = self._img_to_label(ann["pt_img"])
            self._draw_marker_x_with_label(
                p, pt_lbl, label_text=str(ann.get("label", "")),
                x_size=16, line_width=3,
                x_color=QColor(*COLORS["light_blue"]),
                text_color=QColor(*COLORS["gray"])
            )

        p.end()
        self.setPixmap(composed)

    # ----- helpers -----
    def _img_to_label(self, pt_img: QPointF) -> QPointF:
        if self._img_size is None or self._target_rect.isNull():
            return QPointF(0, 0)
        iw, ih = self._img_size
        tr = self._target_rect
        scale = min(tr.width() / iw, tr.height() / ih) if iw and ih else 1.0
        x = tr.left() + pt_img.x() * scale
        y = tr.top()  + pt_img.y() * scale
        return QPointF(x, y)

    def _label_to_img(self, pt_label: QPointF):
        if self._img_size is None or self._target_rect.isNull():
            return None
        iw, ih = self._img_size
        tr = self._target_rect
        if not tr.contains(pt_label.toPoint()):
            return None
        scale = min(tr.width() / iw, tr.height() / ih) if iw and ih else 1.0
        x = (pt_label.x() - tr.left()) / scale
        y = (pt_label.y() - tr.top())  / scale
        x = max(0.0, min(float(iw - 1), x))
        y = max(0.0, min(float(ih - 1), y))
        return QPointF(x, y)

    def _draw_marker_x_with_label(self, painter: QPainter, center_label_pt: QPointF,
                                  label_text: str, x_size: int = 8, line_width: int = 3,
                                  x_color: QColor = QColor(0, 190, 255), text_color: QColor = QColor(62, 68, 76)):
        """Draw an 'X' centered at center_label_pt with small label text next to it."""
        cx, cy = center_label_pt.x(), center_label_pt.y()
        half = x_size / 2.0

        pen = QPen(x_color, line_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # two diagonals
        painter.drawLine(QPointF(cx - half, cy - half), QPointF(cx + half, cy + half))
        painter.drawLine(QPointF(cx - half, cy + half), QPointF(cx + half, cy - half))

        # label box (subtle white bg for readability)
        if label_text:
            fm = painter.fontMetrics()
            # small, bold-ish font
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            text_w = fm.horizontalAdvance(label_text) + 8
            text_h = fm.height() + 4

            # place slightly to the right-top of the X
            tx = cx + half + 6
            ty = cy - half - 6

            # background bubble
            bg_rect = QRect(int(tx), int(ty - text_h + fm.ascent()), int(text_w), int(text_h))
            painter.setPen(QPen(QColor(*COLORS["light_gray"])))
            painter.setBrush(QBrush(QColor(*COLORS["white"])))
            painter.drawRoundedRect(bg_rect, 6, 6)

            # text
            painter.setPen(QPen(text_color))
            painter.drawText(bg_rect, Qt.AlignCenter, label_text)


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



