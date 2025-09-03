from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QPlainTextEdit,
    QStatusBar, QFrame, QSizePolicy, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QDateTime, QThread, QRect, QTimer
from PySide6.QtGui import QPixmap, QImage, QPalette, QColor, QPainter

from datetime import datetime
import os
import numpy as np

from .video_thread import VideoThread
from .widgets import Card, TopBar, Switch, CircularProgress, VideoCanvas, AppState
from .style import STYLE
from .colors import COLORS


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        os.environ.setdefault("QT_SCALE_FACTOR", "1.25")
        self.setStyleSheet(STYLE)
        self.setWindowTitle("Intraoperative Assistenz - Harnblase")

        # ---- latency control state ----
        self._latest_np_frame: np.ndarray | None = None  # last raw RGB frame from VideoThread
        self._inflight = False                           # True while model is working
        self._model_ready = False
        self._pending_video_src: str | int | None = None
        self._camera_connected = False
        self._note_counter = 1

        central = QWidget(); self.setCentralWidget(central)
        outer = QVBoxLayout(central); outer.setContentsMargins(0,0,0,0); outer.setSpacing(8)

        # ================= TOP BAR =================
        self.topbar = TopBar()
        outer.addWidget(self.topbar, 0)
        self.topbar.set_camera_connected(False)
        self.topbar.shot_btn.clicked.connect(self.on_screenshot_clicked)

        # ================= MAIN ROW =================
        root = QHBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)
        outer.addLayout(root, 1)

        # ================= LEFT COLUMN =================
        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        left_col.setContentsMargins(0, 0, 0, 0)

        # Header toggle row (Gefäße)
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(6)
        eye_icon = QLabel()
        pix = QPixmap("src/gui/icons/eye.png")
        eye_icon.setPixmap(
            pix.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not pix.isNull() else QPixmap()
        )
        if pix.isNull():
            eye_icon.setText("👁")
        text_label = QLabel("Gefäße")
        text_label.setObjectName("MutedLabel")
        self.vessel_toggle = Switch()
        toggle_layout.addWidget(eye_icon)
        toggle_layout.addWidget(text_label)
        toggle_layout.addWidget(self.vessel_toggle)

        video_card = Card("src/gui/icons/video.png", "Live-Endoskopie", right_widget=toggle_row)

        # Video area
        self.video_label = VideoCanvas()
        self.video_label.setObjectName("VideoArea")
        self.video_label.setMinimumSize(640, 360)
        video_card.inner_layout.addWidget(self.video_label, 1)

        # Footer / statusbar
        self.footer = QStatusBar(self)
        self.footer.setObjectName("Footer")
        self.footer.setSizeGripEnabled(False)
        footer_container = QWidget(self.footer)
        hl = QHBoxLayout(footer_container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        footer_label = QLabel("© Franziska Krauß 2025", footer_container)
        footer_label.setObjectName("FooterLabel")
        footer_label.setAlignment(Qt.AlignCenter)
        hl.addStretch(1)
        hl.addWidget(footer_label, 0)
        hl.addStretch(1)
        self.footer.clearMessage()
        self.footer.addPermanentWidget(footer_container, 1)
        self.setStatusBar(self.footer)

        # Open video button
        self.open_video_btn = QPushButton("Open video")
        self.open_video_btn.setObjectName("OpenVideoButton")
        self.open_video_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.open_video_btn.clicked.connect(self._on_open_video_clicked)
        video_card.inner_layout.addWidget(self.open_video_btn, 0, Qt.AlignRight)

        # Model worker (HAC)
        from .model_worker import ModelWorker
        self.model_worker = ModelWorker(target_fps=5, max_queue=2)
        self.model_worker.overlay_ready.connect(self.on_overlay_ready)
        self.model_worker.debug.connect(lambda msg: self.footer.showMessage(msg, 5000))
        self.model_worker.error.connect(lambda msg: self.footer.showMessage(msg, 7000))
        self.model_worker.started_ok.connect(self.on_model_ready)
        self.model_worker.start()

        # Internal frame/overlay cache
        self._last_frame_qimg: QImage | None = None
        self._last_overlay_qimg: QImage | None = None

        # Start note
        self.footer.showMessage("Lade Modell …")


        # Slider / ROI / Comment
        self.overlay_slider = QSlider(Qt.Horizontal)
        self.overlay_slider.setValue(70)
        slider_row = QHBoxLayout()
        trans_label = QLabel(" Transparenz")
        trans_label.setObjectName("MutedLabel")
        slider_row.addWidget(trans_label)
        slider_row.addWidget(self.overlay_slider)
        self.overlay_slider.valueChanged.connect(
            lambda v: self.video_label.set_overlay_opacity(v / 100.0)
        )

        self.vessel_toggle.toggled.connect(self._on_vessel_toggle)

        roi_row = QHBoxLayout()
        self.roi_btn = QPushButton("ROI markieren")
        self.roi_btn.setObjectName("ROIButton")
        self.roi_btn.setCheckable(True)
        self.roi_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.comment = QLineEdit()
        self.comment.setPlaceholderText("Kommentar …")
        self.comment.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pal = self.comment.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(*COLORS["light_gray"]))
        pal.setColor(QPalette.Text, QColor(*COLORS["gray"]))
        self.comment.setPalette(pal)

        video_card.inner_layout.addWidget(self.roi_btn, 0, Qt.AlignLeft)
        video_card.inner_layout.addWidget(self.comment, 1)

        roi_row.addWidget(self.roi_btn, 0)
        roi_row.addWidget(self.comment, 1)

        self.roi_btn.toggled.connect(self.on_roi_toggled)
        self.video_label.roiClicked.connect(self.on_roi_marked)

        # --- latency pump timer (start after UI widgets exist) ---
        self._infer_timer = QTimer(self)
        self._infer_timer.setInterval(180)  # ~5.5 Hz
        self._infer_timer.timeout.connect(self._pump_latest_to_model)
        self._infer_timer.start()

        video_card.inner_layout.addLayout(slider_row)
        video_card.inner_layout.addLayout(roi_row)

        # Abdeckung
        cov_card = Card("src/gui/icons/ratio.png", "Abdeckung")
        self.circ_cov = CircularProgress(68)
        cov_card.inner_layout.addWidget(self.circ_cov, alignment=Qt.AlignCenter)

        # Gewebe Score
        score_card = Card("src/gui/icons/graph.png", "Gewebe-Score")
        score_grid = QGridLayout()
        score_grid.addWidget(QLabel("Gesund:"), 0, 0)
        score_grid.addWidget(QLabel("78 %"), 0, 1)
        score_grid.addWidget(QLabel("Verdächtig:"), 1, 0)
        score_grid.addWidget(QLabel("19 %"), 1, 1)
        score_grid.addWidget(QLabel("Tumorverdacht:"), 2, 0)
        score_grid.addWidget(QLabel("3 %"), 2, 1)
        score_card.inner_layout.addLayout(score_grid)

        # Notizen
        notes_card = Card("src/gui/icons/note.png", "Notizen")
        self.notes_view = QPlainTextEdit()
        self.notes_view.setObjectName("NotesView")
        self.notes_view.setReadOnly(True)
        self.notes_view.setFrameShape(QFrame.NoFrame)
        self.notes_view.setPlaceholderText("Noch keine Notizen.")
        notes_card.inner_layout.addWidget(self.notes_view)

        # Assemble left
        left_col.addWidget(video_card)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(16)
        row_layout.addWidget(cov_card, 1)
        row_layout.addWidget(score_card, 1)
        left_col.addWidget(row)
        left_col.addWidget(notes_card)

        left_col.setStretch(0, 3)  # video
        left_col.setStretch(1, 1)  # row (Abdeckung + Gewebe-Score)
        left_col.setStretch(2, 1)  # Notizen

        left_wrap = QWidget()
        left_wrap.setLayout(left_col)

        # ================= RIGHT COLUMN =================
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(16)

        model_card = Card("src/gui/icons/bladder.png", "Digitales Blasenmodell")
        self.model_area = QLabel("3D-Modell (Platzhalter)")
        self.model_area.setObjectName("ModelArea")
        self.model_area.setAlignment(Qt.AlignCenter)
        model_card.inner_layout.addWidget(self.model_area, 1)
        right_col.addWidget(model_card)
        right_col.setStretch(0, 3)

        extra_card = Card("src/gui/icons/navigation.png", "Navigation")
        extra_placeholder = QLabel("Inhalt (Platzhalter)")
        extra_placeholder.setAlignment(Qt.AlignCenter)
        extra_card.inner_layout.addWidget(extra_placeholder, 1)
        right_col.addWidget(extra_card)
        right_col.setStretch(1, 1)

        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        # Add to root
        root.addWidget(left_wrap, 2)
        root.addWidget(right_wrap, 3)

        # Internal frame/overlay cache
        self._last_frame_qimg: QImage | None = None
        self._last_overlay_qimg: QImage | None = None

        # Start note: model loads, start video when ready
        self.footer.showMessage("Lade Modell …")

    # ---------------- latency pump ----------------
    def _pump_latest_to_model(self):
        # send only if: model is ready, overlay is enabled, we have a frame, and nothing is running
        if not self._model_ready or not self.vessel_toggle.isChecked():
            return
        if self._inflight or self._latest_np_frame is None:
            return
        try:
            self._inflight = True
            # non-blocking call into your worker; it will do one inference
            self.model_worker.feed_frame(self._latest_np_frame)
        except Exception:
            self._inflight = False  # fail-safe

    # ---------------- slots ----------------
    def on_model_ready(self):
        self._model_ready = True
        self.footer.showMessage("Modell geladen – starte Video…", 3000)
        src = self._pending_video_src if self._pending_video_src is not None else "auto"
        self.start_video_thread(src)

    def _on_open_video_clicked(self):
        start_dir = getattr(self, "_last_video_dir", os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self, "Open video file", start_dir,
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm);;All files (*)"
        )
        if not path:
            return
        self._last_video_dir = os.path.dirname(path)
        self._pending_video_src = path
        if self._model_ready:
            self.footer.showMessage(f"Opening: {os.path.basename(path)}", 3000)
            self.start_video_thread(path)
        else:
            self.footer.showMessage(
                f"Modell lädt noch – starte Video automatisch: {os.path.basename(path)}",
                4000
            )

    def on_frame_for_model(self, np_frame: np.ndarray):
        # DO NOT forward every frame to the model anymore — just store the newest.
        # The QTimer pump above will send only the latest one and only when idle.
        self._latest_np_frame = np_frame

    def on_overlay_ready(self, overlay_qimg: QImage):
        # inference finished – allow the next one
        self._inflight = False

        self._last_overlay_qimg = overlay_qimg
        if self.vessel_toggle.isChecked():
            self.video_label.set_overlay(overlay_qimg)
            self.video_label.set_overlay_opacity(self.overlay_slider.value() / 100.0)

    def _on_vessel_toggle(self, on: bool):
        # toggle both model emission & UI overlay
        if hasattr(self, "model_worker"):
            self.model_worker.set_enabled(on)
        if not on:
            self.video_label.clear_overlay()
            if self._last_frame_qimg is not None:
                self.video_label.set_frame(self._last_frame_qimg)
        else:
            if self._last_overlay_qimg is not None:
                self.video_label.set_overlay(self._last_overlay_qimg)
                self.video_label.set_overlay_opacity(self.overlay_slider.value() / 100.0)

    def closeEvent(self, event):
        try:
            if hasattr(self, "model_worker") and self.model_worker is not None:
                try:
                    self.model_worker.stop()
                    self.model_worker.wait(1500)
                except Exception:
                    pass

            if hasattr(self, "vthread") and self.vthread is not None:
                try:
                    self.vthread.stop()
                    self.vthread.wait(1500)
                except Exception:
                    pass
        finally:
            super().closeEvent(event)

    def start_video_thread(self, src: str | int = "auto"):
        # Stop existing thread
        if hasattr(self, "vthread") and self.vthread is not None:
            try:
                self.vthread.stop()
                self.vthread.wait(500)
            except Exception:
                pass

        # Create WITHOUT forced resizing (preserve original format)
        try:
            self.vthread = VideoThread(
                src=src,
                width=None,          # <- do not adapt/resize
                height=None,         # <- do not adapt/resize
                target_fps=None,     # use source FPS if available
                loop_video=True
            )
        except TypeError:
            cam_or_path = 0 if (isinstance(src, str) and src == "auto") else src
            self.vthread = VideoThread(cam_or_path)

        # Connect signals
        self.vthread.frame_ready.connect(self.update_video_frame)
        self.vthread.frame_raw.connect(self.on_frame_for_model)
        self.vthread.connection_changed.connect(self.set_connection_status)
        self.vthread.video_finished.connect(lambda: self.footer.showMessage("Video finished", 3000))
        self.vthread.error.connect(self._on_video_error)
        self.vthread.debug.connect(lambda msg: self.footer.showMessage(msg, 4000))

        # Start with high priority
        try:
            prio = QThread.HighPriority
        except AttributeError:
            prio = QThread.Priority.HighPriority
        self.vthread.start(prio)

    # Handle 'auto' no camera
    def _on_video_error(self, msg: str):
        self.footer.showMessage(msg, 6000)
        if "No camera found for 'auto' source" in msg:
            self.on_auto_no_camera()

    def on_auto_no_camera(self):
        start_dir = getattr(self, "_last_video_dir", os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "No camera found — open video file instead",
            start_dir,
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm);;All files (*)"
        )
        if not path:
            return
        self._last_video_dir = os.path.dirname(path)
        self.start_video_thread(path)

    # video frame (QImage)
    def update_video_frame(self, qimg: QImage):
        self._last_frame_qimg = qimg
        self.video_label.set_frame(qimg)

        # Black/blank detection (fast heuristic)
        is_black = True
        BLACK_THR = 12
        try:
            if qimg and not qimg.isNull() and qimg.width() > 0 and qimg.height() > 0:
                w, h = qimg.width(), qimg.height()
                sample_coords = [
                    (w // 2, h // 2),
                    (w // 4, h // 2),
                    (3 * w // 4, h // 2),
                    (w // 2, h // 4),
                    (w // 2, 3 * h // 4),
                ]
                for (sx, sy) in sample_coords:
                    c = qimg.pixelColor(int(sx), int(sy))
                    if (c.red() > BLACK_THR) or (c.green() > BLACK_THR) or (c.blue() > BLACK_THR):
                        is_black = False
                        break
        except Exception:
            is_black = False

        # update topbar pill "stopped" look
        try:
            pill = self.topbar.record_wrap
            pill.setProperty("stopped", bool(is_black))
            pill.style().unpolish(pill)
            pill.style().polish(pill)
            pill.update()
        except Exception:
            pass

        if not self._camera_connected:
            self._camera_connected = True
            self.set_connection_status(True)

    # camera connected status
    def set_connection_status(self, connected: bool):
        self.topbar.set_camera_connected(connected)

    # ROI
    def on_roi_toggled(self, checked: bool):
        self.video_label.set_roi_mode(checked)

    def on_roi_marked(self, x: int, y: int):
        idx = self._note_counter
        self.video_label.add_marker(x, y, idx)
        t = QDateTime.currentDateTime().toString("yyyy.MM.dd HH:mm")
        text = self.comment.text().strip() or "Auffälligkeit"
        line = f"#{idx} {t} – {text}"
        self.notes_view.appendPlainText(line)
        self._note_counter += 1
        self.roi_btn.setChecked(False)
        self.comment.clear()

    # Screenshot: compose frame + overlay with opacity (no aspect-cropping)
    def on_screenshot_clicked(self):
        if self._last_frame_qimg is None:
            QMessageBox.information(self, "Screenshot", "Kein Frame verfügbar.")
            return

        # base as RGB888
        base = self._last_frame_qimg.convertToFormat(QImage.Format_RGB888)
        result = base.copy()
        painter = QPainter(result)

        if self._last_overlay_qimg is not None and self.vessel_toggle.isChecked():
            ov = self._last_overlay_qimg
            painter.setOpacity(self.overlay_slider.value() / 100.0)

            if ov.size() == base.size():
                # 1:1 draw (no scaling)
                painter.drawImage(0, 0, ov)
            else:
                # Letterbox-fit (KeepAspectRatio) centered, no expanding/cropping
                bw, bh = base.width(), base.height()
                ow, oh = ov.width(), ov.height()
                if ow > 0 and oh > 0:
                    scale = min(bw / ow, bh / oh)
                    draw_w = int(ow * scale)
                    draw_h = int(oh * scale)
                    off_x = (bw - draw_w) // 2
                    off_y = (bh - draw_h) // 2
                    target = QRect(off_x, off_y, draw_w, draw_h)
                    painter.drawImage(target, ov)

            painter.setOpacity(1.0)

        painter.end()

        # Ensure folder exists
        out_dir = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(out_dir, exist_ok=True)

        pid = AppState.patient_id or "unknown"
        screenshot_name = f"{datetime.now():%Y_%m_%d_%H_%M_%S}_patient_{pid}_screenshot.png"
        out_path = os.path.join(out_dir, screenshot_name)
        result.save(out_path)
        self.footer.showMessage(f"Screenshot gespeichert: {os.path.basename(screenshot_name)}", 4000)
