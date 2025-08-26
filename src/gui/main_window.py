from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QPushButton, QSlider, QProgressBar, QFrame, QSizePolicy, QLineEdit, QCheckBox,
)
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QBrush, QPen

from .video_thread import VideoThread
import numpy as np


# ---- simple ToggleSwitch based on QCheckBox ----
class ToggleSwitch(QCheckBox):
    def __init__(self, label=""):
        super().__init__(label)
        self.setChecked(True)
        self.setStyleSheet("""
        QCheckBox::indicator { width: 40px; height: 20px; }
        QCheckBox::indicator:unchecked {
            border-radius: 10px;
            background-color: #CBD5E1;
        }
        QCheckBox::indicator:checked {
            border-radius: 10px;
            background-color: #3B82F6;
        }
        """)
        self.setText("Gefäße")  # label right of the switch


# ---- reusable UI pieces ----
class Header(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Header")
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 10, 12, 6); lay.setSpacing(8)

        icon_label = QLabel()
        if icon.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            pixmap = QPixmap(icon).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText(icon)  # fallback: emoji
        icon_label.setFixedWidth(28)

        text = QLabel(title); text.setObjectName("HeaderTitle")
        lay.addWidget(icon_label); lay.addWidget(text, 1)

        if right_widget is not None:
            lay.addWidget(right_widget, 0, Qt.AlignRight)




class Switch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setChecked(True)
        self.setText("")   # keine interne beschriftung

    def sizeHint(self):
        return QSize(40, 20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        rect = e.rect()
        bg_color = QColor("#3B82F6") if self.isChecked() else QColor("#CBD5E1")

        # Hintergrund
        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), rect.height()/2, rect.height()/2)

        # Knopf
        knob_d = rect.height()-4
        x = rect.right()-knob_d-2 if self.isChecked() else rect.left()+2
        knob_rect = QRect(x, rect.top()+2, knob_d, knob_d)
        p.setBrush(QBrush(QColor("#FFF")))
        p.setPen(QPen(QColor("#E5E7EB")))
        p.drawEllipse(knob_rect)
        p.end()

class TopBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(16)

        # --- left side ---
        left = QHBoxLayout(); left.setSpacing(8)
        icon = QLabel("🎥")
        title = QLabel("Intraop-Assistenz · Blase")
        title.setObjectName("TopTitle")
        badge = QLabel("Demo")
        badge.setObjectName("Badge")
        left.addWidget(icon)
        left.addWidget(title)
        left.addWidget(badge)

        left_wrap = QWidget(); left_wrap.setLayout(left)
        lay.addWidget(left_wrap, 0, Qt.AlignLeft)

        # --- right side ---
        right = QHBoxLayout(); right.setSpacing(12)
        patient = QLabel("Patient: ID-042"); patient.setObjectName("Pill")
        record = QLabel("Aufnahme läuft"); record.setObjectName("Pill")
        screenshot = QPushButton("Screenshot"); screenshot.setObjectName("TopBtn")
        right.addWidget(patient); right.addWidget(record); right.addWidget(screenshot)

        right_wrap = QWidget(); right_wrap.setLayout(right)
        lay.addWidget(right_wrap, 0, Qt.AlignRight)


class Card(QFrame):
    def __init__(self, icon: str, title: str, right_widget=None):
        super().__init__()
        self.setObjectName("Card")
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        self.header = Header(icon, title, right_widget)
        self.body = QFrame(); self.body.setObjectName("CardBody")
        inner = QVBoxLayout(self.body); inner.setContentsMargins(16, 12, 16, 16); inner.setSpacing(10)
        self.inner_layout = inner
        outer.addWidget(self.header); outer.addWidget(self.body, 1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        central = QWidget();
        self.setCentralWidget(central)
        outer = QVBoxLayout(central);
        outer.setContentsMargins(0, 0, 0, 0);
        outer.setSpacing(8)

        # Top bar
        self.topbar = TopBar()
        outer.addWidget(self.topbar, 0)

        # Main content row
        root = QHBoxLayout();
        root.setContentsMargins(16, 16, 16, 16);
        root.setSpacing(16)
        outer.addLayout(root, 1)
        self._apply_styles()
        self.setWindowTitle("Intraoperative Assistenz - Harnblase")

        # ===== Left column =====
        left_col = QVBoxLayout(); left_col.setSpacing(16)

        # rechts oben im Header: eye-icon + "Gefäße" + toggle
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(6)

        eye_label = QLabel()
        eye_pix = QPixmap("src/gui/icons/eye.png").scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        eye_label.setPixmap(eye_pix)

        text_label = QLabel("Gefäße")

        self.vessel_toggle = Switch()

        toggle_layout.addWidget(eye_label)
        toggle_layout.addWidget(text_label)
        toggle_layout.addWidget(self.vessel_toggle)

        video_card = Card("src/gui/icons/video.png", "Live-Endoskopie", right_widget=toggle_row)

        self.video_label = QLabel("Kein Video")
        self.video_label.setObjectName("VideoArea")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Start Video Thread
        self.vthread = VideoThread(src=1, width=1280, height=720)
        self.vthread.frame_ready.connect(self.update_video_frame)
        self.vthread.start()

        # Slider + ROI + Kommentar (unter dem Video)
        self.overlay_slider = QSlider(Qt.Horizontal)
        self.overlay_slider.setObjectName("Slider")
        self.overlay_slider.setValue(70)
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Transparenz Overlay"))
        slider_row.addWidget(self.overlay_slider)

        roi_row_left = QHBoxLayout()
        self.roi_btn_left = QPushButton("ROI markieren")
        self.roi_btn_left.setObjectName("PrimaryBtn")
        self.comment_left = QLineEdit()
        self.comment_left.setPlaceholderText("Kommentar zum Endoskopie-Bild …")
        roi_row_left.addWidget(self.roi_btn_left, 0)
        roi_row_left.addWidget(self.comment_left, 1)

        video_card.inner_layout.addWidget(self.video_label, 1)
        video_card.inner_layout.addLayout(slider_row)
        video_card.inner_layout.addLayout(roi_row_left)

        # --- Abdeckung (links) ---
        cov_card = Card("📊", "Abdeckung")
        self.cov_bar = QProgressBar();
        self.cov_bar.setValue(68)
        cov_card.inner_layout.addWidget(self.cov_bar)

        # --- Gewebe-Score (rechts) ---
        score_card = Card("🧬", "Gewebe-Score")
        score_grid = QGridLayout()
        score_grid.addWidget(QLabel("Gesund:"), 0, 0);
        score_grid.addWidget(QLabel("78 %"), 0, 1)
        score_grid.addWidget(QLabel("Verdächtig:"), 1, 0);
        score_grid.addWidget(QLabel("19 %"), 1, 1)
        score_grid.addWidget(QLabel("Tumorverdacht:"), 2, 0);
        score_grid.addWidget(QLabel("3 %"), 2, 1)
        score_card.inner_layout.addLayout(score_grid)

        # --- nebeneinander anordnen ---
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0);
        row_layout.setSpacing(16)
        row_layout.addWidget(cov_card, 1)
        row_layout.addWidget(score_card, 1)

        left_col.addWidget(video_card, 3)
        left_col.addWidget(row_widget, 1)

        # ===== Right column: Modell über volle Höhe =====
        model_card = Card("src/gui/icons/Bladder.png", "Digitales Blasenmodell")
        self.model_area = QLabel("3D-Modell (Platzhalter)")
        self.model_area.setObjectName("ModelArea")
        self.model_area.setAlignment(Qt.AlignCenter)
        self.model_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        model_card.inner_layout.addWidget(self.model_area, 1)

        # ===== assemble =====
        left_wrap = QWidget(); left_wrap.setLayout(left_col)
        root.addWidget(left_wrap, 2)
        root.addWidget(model_card, 3)

    # --- Video frame update ---
    def update_video_frame(self, rgb):
        if self.vessel_toggle.isChecked():
            # TODO: Overlay vessels here later
            pass
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

    def closeEvent(self, event):
        if hasattr(self, "vthread"):
            self.vthread.stop()
            self.vthread.wait(500)
        super().closeEvent(event)

    def _apply_styles(self):
        self.setStyleSheet("""
        QMainWindow { background: #F7F9FC; }
        #Card {
            background: #FFFFFF; border: 1px solid #E6EAF0; border-radius: 12px;
        }
        #Header { background: #FFFFFF; border-bottom: 1px solid #EEF2F7;
                  border-top-left-radius: 12px; border-top-right-radius: 12px; }
        #HeaderIcon { font-size: 18px; }
        #HeaderTitle { font-weight: 600; font-size: 16px; color: #0F172A; }
        QLabel { color: #111827; }
        #VideoArea, #ModelArea {
            background: #F1F5F9; border: 1px dashed #D8DEE9; border-radius: 10px; 
            color: #64748B; min-height: 260px;
        }
        QProgressBar { border: 1px solid #E5E7EB; border-radius: 8px; background: #EEF2F7; height: 18px; }
        QProgressBar::chunk { background-color: #3B82F6; border-radius: 8px; }
        #PrimaryBtn { background: #111827; color: white; padding: 8px 12px; border-radius: 10px; border: none; }
        #PrimaryBtn:hover { background: #0F172A; }
        QSlider::groove:horizontal { height: 6px; background: #E5E7EB; border-radius: 3px; }
        QSlider::handle:horizontal { background: #111827; width: 16px; height:16px; margin: -6px 0; border-radius: 8px; }
        QLineEdit { padding: 8px 10px; border: 1px solid #E5E7EB; border-radius: 8px; background: #FFFFFF; }
        #TopBar {
    background: #FFFFFF;
    border-bottom: 1px solid #E5E7EB;
}
#TopTitle {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
}
#Badge {
    background: #E0F2FE;
    color: #0369A1;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
}
#Pill {
    background: #111827;
    color: white;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
}
#TopBtn {
    background: #F9FAFB;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 4px 8px;
}
#TopBtn:hover { background: #F3F4F6; }

        """)
