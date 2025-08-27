from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QPlainTextEdit,
    QStatusBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QDateTime, QThread
from PySide6.QtGui import QPixmap, QImage, QPalette, QColor

from datetime import datetime

from .video_thread import VideoThread
from .widgets import Card, TopBar, Switch, CircularProgress, VideoCanvas
from .style import STYLE
from .colors import COLORS

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE)
        central = QWidget(); self.setCentralWidget(central)
        outer = QVBoxLayout(central); outer.setContentsMargins(0,0,0,0); outer.setSpacing(8)
        self.setWindowTitle("Intraoperative Assistenz - Harnblase")
        self._note_counter = 1

        # Top Bar
        self.topbar = TopBar()
        outer.addWidget(self.topbar, 0)

        # Main Row
        root = QHBoxLayout(); root.setContentsMargins(16,16,16,16); root.setSpacing(16)
        outer.addLayout(root, 1)

        # Left column
        left_col = QVBoxLayout(); left_col.setSpacing(16); left_col.setContentsMargins(0, 0, 0, 0)

        # Live Endoskopie
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row); toggle_layout.setContentsMargins(0,0,0,0); toggle_layout.setSpacing(6)
        eye_icon = QLabel()
        pix = QPixmap("src/gui/icons/eye.png")
        if not pix.isNull():
            eye_icon.setPixmap(pix.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            eye_icon.setText("👁")
        text_label = QLabel("Gefäße")
        text_label.setObjectName("MutedLabel")
        self.vessel_toggle = Switch()
        toggle_layout.addWidget(eye_icon); toggle_layout.addWidget(text_label); toggle_layout.addWidget(self.vessel_toggle)

        video_card = Card("src/gui/icons/video.png", "Live-Endoskopie", right_widget=toggle_row)

        # --- Video area with interactive ROI ---
        self.video_label = VideoCanvas()
        self.video_label.setObjectName("VideoArea")
        self.video_label.setMinimumSize(640, 360)
        video_card.inner_layout.addWidget(self.video_label, 1)

        # Start video thread
        self.vthread = VideoThread(src=1, width=1280, height=720, target_fps=30)
        self.vthread.frame_ready.connect(self.update_video_frame)
        self.vthread.connection_changed.connect(self.set_connection_status)
        try:
            prio = QThread.HighPriority
        except AttributeError:
            prio = QThread.Priority.HighPriority

        self.vthread.start(prio)

        # Slider + ROI + Kommentar
        self.overlay_slider = QSlider(Qt.Horizontal);
        self.overlay_slider.setValue(70)
        slider_row = QHBoxLayout()
        trans_label = QLabel(" Transparenz")
        trans_label.setObjectName("MutedLabel")
        slider_row.addWidget(trans_label)
        slider_row.addWidget(self.overlay_slider)

        roi_row = QHBoxLayout()

        self.roi_btn = QPushButton("ROI markieren")
        self.roi_btn.setObjectName("ROIButton")
        self.roi_btn.setCheckable(True)
        self.roi_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.comment = QLineEdit()
        self.comment.setPlaceholderText("Kommentar …")
        self.comment.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.comment.setMinimumWidth(0)
        pal = self.comment.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(*COLORS["light_gray"]))
        pal.setColor(QPalette.Text, QColor(*COLORS["gray"]))
        self.comment.setPalette(pal)

        video_card.inner_layout.addWidget(self.roi_btn, 0, Qt.AlignLeft)
        video_card.inner_layout.addWidget(self.comment, 1)

        # make placeholder + typed text gray
        pal = self.comment.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(*COLORS["light_gray"]))  # softer gray for placeholder
        pal.setColor(QPalette.Text, QColor(*COLORS["gray"]))  # typed text gray
        self.comment.setPalette(pal)

        roi_row.addWidget(self.roi_btn, 0); roi_row.addWidget(self.comment, 1)

        # connect ROI logic
        self.roi_btn.toggled.connect(self.on_roi_toggled)
        self.video_label.roi_marked.connect(self.on_roi_marked)

        video_card.inner_layout.addLayout(slider_row)
        video_card.inner_layout.addLayout(roi_row)

        # Abdeckung
        cov_card = Card("src/gui/icons/ratio.png", "Abdeckung")
        self.circ_cov = CircularProgress(68)
        cov_card.inner_layout.addWidget(self.circ_cov, alignment=Qt.AlignCenter)

        # Gewebe Score
        score_card = Card("src/gui/icons/graph.png", "Gewebe-Score")
        score_grid = QGridLayout()
        score_grid.addWidget(QLabel("Gesund:"), 0, 0);  score_grid.addWidget(QLabel("78 %"), 0, 1)
        score_grid.addWidget(QLabel("Verdächtig:"), 1, 0); score_grid.addWidget(QLabel("19 %"), 1, 1)
        score_grid.addWidget(QLabel("Tumorverdacht:"), 2, 0); score_grid.addWidget(QLabel("3 %"), 2, 1)
        score_card.inner_layout.addLayout(score_grid)

        # --- Notizen panel ---
        notes_card = Card("src/gui/icons/note.png", "Notizen")
        self.notes_view = QPlainTextEdit()
        self.notes_view.setObjectName("NotesView")
        self.notes_view.setReadOnly(True)
        self.notes_view.setFrameShape(QFrame.NoFrame)
        self.notes_view.setPlaceholderText("Noch keine Notizen.")
        notes_card.inner_layout.addWidget(self.notes_view)

        # Add left side
        left_col.addWidget(video_card, 3)
        row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0,0,0,0); row_layout.setSpacing(16)
        row_layout.addWidget(cov_card, 1); row_layout.addWidget(score_card, 1)
        left_col.addWidget(row, 1)
        left_col.addWidget(notes_card, 1)

        left_wrap = QWidget(); left_wrap.setLayout(left_col)

        # Right column
        model_card = Card("src/gui/icons/Bladder.png", "Digitales Blasenmodell")
        self.model_area = QLabel("3D-Modell (Platzhalter)")
        self.model_area.setObjectName("ModelArea")
        self.model_area.setAlignment(Qt.AlignCenter)
        model_card.inner_layout.addWidget(self.model_area, 1)

        root.addWidget(left_wrap, 2)
        root.addWidget(model_card, 3)

        # --- Footer (Copyright) ---
        self.footer = QStatusBar(self)
        self.footer.setObjectName("Footer")
        self.footer.setSizeGripEnabled(False)

        # one container item so QStatusBar doesn't draw separators
        footer_container = QWidget(self.footer)
        hl = QHBoxLayout(footer_container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        footer_label = QLabel(f"© Franziska Krauß 2025", footer_container)
        footer_label.setObjectName("FooterLabel")
        footer_label.setAlignment(Qt.AlignCenter)

        hl.addStretch(1)
        hl.addWidget(footer_label, 0)
        hl.addStretch(1)

        # only ONE permanent widget → no separators
        self.footer.clearMessage()
        self.footer.addPermanentWidget(footer_container, 1)
        self.setStatusBar(self.footer)

    # video frame (receives QImage)
    def update_video_frame(self, qimg: QImage):
        """
        Receive and display new video frame.
        Also detect an all-black frame (video stopped) and set RecordPill[stopped=true].
        """
        # show frame in the VideoCanvas (existing behavior)
        self.video_label.set_frame(qimg)

        # --- detect black/blank frame (simple, fast heuristic) ---
        is_black = True
        BLACK_THR = 12  # 0..255, increase to be less strict

        if qimg is None or qimg.isNull():
            is_black = True
        else:
            w, h = qimg.width(), qimg.height()
            if w == 0 or h == 0:
                is_black = True
            else:
                # sample center and 4 offsets (small cross) to be a bit robust
                sample_coords = [
                    (w // 2, h // 2),
                    (w // 4, h // 2),
                    (3 * w // 4, h // 2),
                    (w // 2, h // 4),
                    (w // 2, 3 * h // 4)
                ]
                # if any sample is bright enough, treat frame as not-black
                for (sx, sy) in sample_coords:
                    try:
                        col = qimg.pixelColor(int(sx), int(sy))
                    except Exception:
                        # fallback: assume not-black if sampling fails
                        is_black = False
                        break

                    if (col.red() > BLACK_THR) or (col.green() > BLACK_THR) or (col.blue() > BLACK_THR):
                        is_black = False
                        break
                else:
                    # loop finished without breaking → still black
                    is_black = True

        # --- set CSS property on record pill and refresh style ---
        try:
            pill = self.topbar.record_wrap
            pill.setProperty("stopped", bool(is_black))
            # keep existing connected property unchanged (so CSS for connected still works)
            pill.style().unpolish(pill)
            pill.style().polish(pill)
            pill.update()
        except Exception:
            # don't break the video display if topbar isn't available yet
            pass

    # camera connected status → flip pill color
    def set_connection_status(self, connected: bool):
        pill = self.topbar.record_wrap
        pill.setProperty("connected", connected)
        pill.style().unpolish(pill)
        pill.style().polish(pill)
        pill.update()

    # ROI button behavior
    def on_roi_toggled(self, checked: bool):
        if checked:
            ok = self.video_label.begin_annotation(self._note_counter)
            if not ok:
                self.roi_btn.setChecked(False)
        else:
            self.video_label.cancel_annotation()

    # When a ROI is marked in the video
    def on_roi_marked(self, label_num: int):
        t = QDateTime.currentDateTime().toString("yyyy.MM.dd HH:mm")
        text = self.comment.text().strip() or "Auffälligkeit"
        line = f"#{label_num} {t} – {text}"
        self.notes_view.appendPlainText(line)
        self._note_counter = label_num + 1
        self.roi_btn.setChecked(False)
        self.comment.clear()

    def closeEvent(self, event):
        if hasattr(self, "vthread"):
            self.vthread.stop()
            self.vthread.wait(500)
        super().closeEvent(event)
