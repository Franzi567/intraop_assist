from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QPlainTextEdit,
    QStatusBar, QFrame, QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QDateTime, QThread
from PySide6.QtGui import QPixmap, QImage, QPalette, QColor

from datetime import datetime
import os

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
        self._pending_video_src = r"C:\Git\intraop_assist\data\Video_Snippet_1.mp4"

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

        # --- Footer (Copyright) ---   <-- move this block *above* starting the video thread
        self.footer = QStatusBar(self)
        self.footer.setObjectName("Footer")
        self.footer.setSizeGripEnabled(False)
        footer_container = QWidget(self.footer)
        hl = QHBoxLayout(footer_container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        footer_label = QLabel(f"© Franziska Krauß 2025", footer_container)
        footer_label.setObjectName("FooterLabel")
        footer_label.setAlignment(Qt.AlignCenter)
        hl.addStretch(1);
        hl.addWidget(footer_label, 0);
        hl.addStretch(1)
        self.footer.clearMessage()
        self.footer.addPermanentWidget(footer_container, 1)
        self.setStatusBar(self.footer)

        # create "Open video" button (user can manually pick a file)
        self.open_video_btn = QPushButton("Open video")
        self.open_video_btn.setObjectName("OpenVideoButton")
        self.open_video_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.open_video_btn.clicked.connect(self.on_open_video_clicked)
        # place it in the video_card header or under video controls; example: add to the inner layout
        video_card.inner_layout.addWidget(self.open_video_btn, 0, Qt.AlignRight)

        # --- Model worker (HAC inference) ---
        try:
            from .model_worker import ModelWorker
            self.model_worker = ModelWorker(target_fps=5, max_queue=2)
        except Exception:
            # fallback if import path differs; import locally then instantiate
            from .model_worker import ModelWorker
            self.model_worker = ModelWorker(target_fps=5, max_queue=2)

        # internal storage for last frame / overlay
        self._last_frame_qimg = None  # QImage (RGB)
        self._last_overlay_qimg = None  # QImage (RGBA)

        # connect worker signals
        self.model_worker.overlay_ready.connect(self.on_overlay_ready)
        self.model_worker.error.connect(lambda msg: self.footer.showMessage(msg, 5000))
        self.model_worker.started_ok.connect(lambda: self.footer.showMessage("Model loaded", 3000))

        # start worker thread
        self.model_worker.start()

        self.vessel_toggle.toggled.connect(lambda on: self._on_vessel_toggle(on))

        # Slider + ROI + Kommentar
        self.overlay_slider = QSlider(Qt.Horizontal);
        self.overlay_slider.setValue(70)
        slider_row = QHBoxLayout()
        trans_label = QLabel(" Transparenz")
        trans_label.setObjectName("MutedLabel")
        slider_row.addWidget(trans_label)
        slider_row.addWidget(self.overlay_slider)
        # slider controlling overlay opacity (0..1)
        self.overlay_slider.valueChanged.connect(lambda v: self.video_label.set_overlay_opacity(v / 100.0))

        self.vessel_toggle.toggled.connect(lambda on: None if on else self.video_label.clear_overlay())
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

        self.open_video_btn.clicked.connect(self.on_open_video_clicked)

    def on_model_ready(self):
        """Called when ModelWorker finished loading."""
        self._model_ready = True
        self.footer.showMessage("Modell geladen – starte Video…", 3000)
        # Start the video now (using whatever source we have queued)
        self.start_video_thread(self._pending_video_src)

    def on_open_video_clicked(self):
        """Manual Open Video button handler (user-initiated)."""
        start_dir = getattr(self, "_last_video_dir", os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video file",
            start_dir,
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm);;All files (*)"
        )
        if not path:
            return
        self._last_video_dir = os.path.dirname(path)
        self._pending_video_src = path  # remember the choice

        if self._model_ready:
            self.footer.showMessage(f"Opening: {os.path.basename(path)}", 3000)
            self.start_video_thread(path)
        else:
            # start later when on_model_ready() fires
            self.footer.showMessage(
                f"Modell lädt noch – starte Video automatisch: {os.path.basename(path)}",
                4000
            )

    def on_frame_for_model(self, np_frame):
        try:
            if hasattr(self, "model_worker") and getattr(self.model_worker, "enqueue_frame", None):
                self.model_worker.enqueue_frame(np_frame)
        except Exception:
            pass

    def on_overlay_ready(self, overlay_qimg: QImage):
        self._last_overlay_qimg = overlay_qimg
        if self.vessel_toggle.isChecked():
            self.video_label.set_overlay(overlay_qimg)
            self.video_label.set_overlay_opacity(self.overlay_slider.value() / 100.0)

    def _on_vessel_toggle(self, on: bool):
        if not on:
            self.video_label.clear_overlay()
            if self._last_frame_qimg is not None:
                self.video_label.set_frame(self._last_frame_qimg)
        else:
            if self._last_overlay_qimg is not None:
                self.video_label.set_overlay(self._last_overlay_qimg)
                self.video_label.set_overlay_opacity(self.overlay_slider.value() / 100.0)

    def _compose_overlay(self, base_qimg: QImage, overlay_qimg: QImage, opacity: float) -> QImage:
        """Scale overlay to base size and draw it with given opacity onto a copy of base_qimg."""
        if base_qimg is None:
            return overlay_qimg

        bw, bh = base_qimg.width(), base_qimg.height()
        ov = overlay_qimg
        if ov.format() != QImage.Format.Format_RGBA8888:
            try:
                ov = ov.convertToFormat(QImage.Format.Format_RGBA8888)
            except Exception:
                pass
        # scale overlay to base size
        if ov.width() != bw or ov.height() != bh:
            ov = ov.scaled(bw, bh, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        base_rgba = base_qimg.convertToFormat(QImage.Format.Format_RGBA8888)
        result = base_rgba.copy()

        from PySide6.QtGui import QPainter
        painter = QPainter(result)
        painter.setOpacity(opacity)
        painter.drawImage(0, 0, ov)
        painter.end()

        # convert to RGB for display (VideoCanvas.set_frame likely expects RGB)
        return result.convertToFormat(QImage.Format.Format_RGB888)

    def closeEvent(self, event):
        try:
            # stop model worker
            if hasattr(self, "model_worker") and self.model_worker is not None:
                try:
                    self.model_worker.stop()
                    self.model_worker.wait(3000)
                except Exception:
                    pass

            # stop video thread
            if hasattr(self, "vthread") and self.vthread is not None:
                try:
                    self.vthread.stop()
                    self.vthread.wait(3000)
                except Exception:
                    pass
        finally:
            super().closeEvent(event)

    def start_video_thread(self, src="auto"):
        """
        Stop any existing thread and start a new VideoThread for `src`.
        If src == "auto", and the thread emits the specific 'no camera' error,
        we will automatically open a file dialog so the user can pick a video file.
        """
        # stop existing thread cleanly
        if hasattr(self, "vthread") and self.vthread is not None:
            try:
                self.vthread.stop()
                self.vthread.wait(500)
            except Exception:
                pass

        # create thread and connect signals
        self.vthread = VideoThread(src=src, width=1280, height=720, target_fps=22.74, loop_video=True)
        self.vthread.frame_ready.connect(self.update_video_frame)
        self.vthread.frame_raw.connect(self.on_frame_for_model)
        self.vthread.connection_changed.connect(self.set_connection_status)
        self.vthread.video_finished.connect(lambda: self.footer.showMessage("Video finished", 3000))

        # handle errors:
        # - if starting with "auto" we want to open file picker when we get that specific error
        def _error_handler(msg):
            # show message in footer always
            self.footer.showMessage(msg, 5000)
            # if this was the 'auto' no-camera error, open file picker once
            if isinstance(src, str) and src == "auto" and "No camera found for 'auto' source" in msg:
                # run file picker on the UI thread immediately
                self.on_auto_no_camera()

        # connect to the thread
        self.vthread.error.connect(_error_handler)

        # also allow manual open button to work
        self.open_video_btn.setEnabled(True)

        # start with high priority if available
        try:
            prio = QThread.HighPriority
        except AttributeError:
            prio = QThread.Priority.HighPriority
        self.vthread.start(prio)

    def on_auto_no_camera(self):
        """
        Called automatically when src=='auto' reports no camera.
        Show a file dialog and, if a file is chosen, restart video thread with that file.
        """
        # prefer last opened dir or cwd
        start_dir = getattr(self, "_last_video_dir", os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "No camera found — open video file instead",
            start_dir,
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm);;All files (*)"
        )
        if not path:
            # user cancelled — nothing to do
            return
        # remember dir for next time
        self._last_video_dir = os.path.dirname(path)
        # restart thread with chosen file (non-auto)
        self.start_video_thread(path)

    def on_open_video_clicked(self):
        """Manual Open Video button handler (user-initiated)."""
        start_dir = getattr(self, "_last_video_dir", os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video file",
            start_dir,
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm);;All files (*)"
        )
        if not path:
            return
        self._last_video_dir = os.path.dirname(path)
        self.footer.showMessage(f"Opening: {os.path.basename(path)}", 3000)
        self.start_video_thread(path)

    # video frame (receives QImage)
    def update_video_frame(self, qimg: QImage):
        self._last_frame_qimg = qimg
        # Always just show the base frame; VideoCanvas will overlay if one is set.
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
        pill.style().unpolish(pill);
        pill.style().polish(pill);
        pill.update()

        # also colorize left “Keine Kamera” label via CSS property
        try:
            self.topbar.camera_label.setProperty("connected", connected)
            self.topbar.camera_label.style().unpolish(self.topbar.camera_label)
            self.topbar.camera_label.style().polish(self.topbar.camera_label)
            self.topbar.camera_label.update()
            self.topbar.camera_label.setText("Kamera verbunden" if connected else "Keine Kamera")
        except Exception:
            pass

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

