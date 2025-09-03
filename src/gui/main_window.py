from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QPlainTextEdit,
    QStatusBar, QFrame, QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QDateTime, QThread
from PySide6.QtGui import QPixmap, QImage, QPalette, QColor

from datetime import datetime
import os
import numpy as np

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
        #self._pending_video_src = r"C:\Git\intraop_assist\data\Video_Snippet_1.mp4"

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
        self._camera_connected = False
        self.topbar.set_camera_connected(False)
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
        if hasattr(self.model_worker, "debug"):
            self.model_worker.debug.connect(lambda msg: self.footer.showMessage(msg, 5000))
        if hasattr(self.model_worker, "started_ok"):
            self.model_worker.started_ok.connect(self.on_model_ready)

        # start worker thread
        self.model_worker.start()
        # start the video now; if no camera on 'auto', a file picker pops up
        self.start_video_thread("auto")

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
        self.vessel_toggle.toggled.connect(self.model_worker.set_enabled)
        self.vessel_toggle.toggled.connect(self._on_vessel_toggle)
        self.vessel_toggle.toggled.connect(
            lambda on: getattr(self.model_worker, "set_enabled")(bool(on)) if hasattr(self, "model_worker") else None
        )

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
        self.video_label.roiClicked.connect(self.on_roi_marked)

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
        left_col.addWidget(video_card)
        row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0,0,0,0); row_layout.setSpacing(16)
        row_layout.addWidget(cov_card, 1); row_layout.addWidget(score_card, 1)
        left_col.addWidget(row)
        left_col.addWidget(notes_card)

        left_col.setStretch(0, 3)  # video
        left_col.setStretch(1, 1)  # row with Abdeckung + Gewebe-Score
        left_col.setStretch(2, 1)  # Notizen

        left_wrap = QWidget(); left_wrap.setLayout(left_col)
        #
        # # Right column
        # model_card = Card("src/gui/icons/Bladder.png", "Digitales Blasenmodell")
        # self.model_area = QLabel("3D-Modell (Platzhalter)")
        # self.model_area.setObjectName("ModelArea")
        # self.model_area.setAlignment(Qt.AlignCenter)
        # model_card.inner_layout.addWidget(self.model_area, 1)
        #
        # root.addWidget(left_wrap, 2)
        # root.addWidget(model_card, 3)

        self.open_video_btn.clicked.connect(self.on_open_video_clicked)

        # --- Right column (TOP: model, BOTTOM: extra area) ---
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(16)

        # TOP card: Digitales Blasenmodell (as before)
        model_card = Card("src/gui/icons/bladder.png", "Digitales Blasenmodell")
        self.model_area = QLabel("3D-Modell (Platzhalter)")
        self.model_area.setObjectName("ModelArea")
        self.model_area.setAlignment(Qt.AlignCenter)
        model_card.inner_layout.addWidget(self.model_area, 1)
        right_col.addWidget(model_card)  # <- matches left video (stretch 3)

        # BOTTOM card: new extra area (bottom-right corner)
        extra_card = Card("src/gui/icons/navigation.png", "Navigation")
        extra_placeholder = QLabel("Inhalt (Platzhalter)")
        extra_placeholder.setAlignment(Qt.AlignCenter)
        extra_card.inner_layout.addWidget(extra_placeholder, 1)
        right_col.addWidget(extra_card)  # <- matches left (Abdeckung/Score + Notizen) = 1 + 1
        right_col.setStretch(0, 3)  # top matches left video
        right_col.setStretch(1, 1)  # bottom matches left "row" height

        # Wrap the right column
        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        # Add to root layout
        # (Replace your previous: root.addWidget(model_card, 3))
        root.addWidget(left_wrap, 2)
        root.addWidget(right_wrap, 3)

    def on_model_ready(self):
        """Called when ModelWorker finished loading."""
        self._model_ready = True
        self.footer.showMessage("Modell geladen – starte Video…", 3000)
        # Start the video now (using whatever source we have queued)
        self.start_video_thread("auto")

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
           if hasattr(self, "model_worker") and getattr(self.model_worker, "feed_frame", None):
               self.model_worker.feed_frame(np_frame)
       except Exception:
           pass

    def on_overlay_ready(self, overlay_qimg: QImage):
        self._last_overlay_qimg = overlay_qimg
        if self.vessel_toggle.isChecked():
            self.video_label.set_overlay(overlay_qimg)
            self.video_label.set_overlay_opacity(self.overlay_slider.value() / 100.0)

    def _on_vessel_toggle(self, on: bool):
        if not on:
            if hasattr(self.video_label, "clear_overlay"):
                self.video_label.clear_overlay()
            else:
                # Fallback: set a fully transparent/empty overlay
                try:
                    self.video_label.set_overlay(None)
                except Exception:
                    pass
            if getattr(self, "_last_frame_qimg", None) is not None:
                self.video_label.set_frame(self._last_frame_qimg)
        else:
            if getattr(self, "_last_overlay_qimg", None) is not None:
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
        # Stop existing thread
        if hasattr(self, "vthread") and self.vthread is not None:
            try:
                self.vthread.stop()
                self.vthread.wait(500)
            except Exception:
                pass

        # Try "new" API first (src/width/height...), else fall back to simple (path)
        try:
            self.vthread = VideoThread(src=src, width=1280, height=720, target_fps=22.74, loop_video=True)
            new_api = True
        except TypeError:
            cam_or_path = 0 if (isinstance(src, str) and src == "auto") else src
            self.vthread = VideoThread(cam_or_path)
            new_api = False

        # Connect whichever signals exist
        if hasattr(self.vthread, "frame"):
            self.vthread.frame.connect(self.update_video_frame)
        if hasattr(self.vthread, "frame_ready"):
            self.vthread.frame_ready.connect(self.update_video_frame)
        if hasattr(self.vthread, "frame_raw"):
            self.vthread.frame_raw.connect(self.on_frame_for_model)

        if hasattr(self.vthread, "connection_changed"):
            self.vthread.connection_changed.connect(self.set_connection_status)
        if hasattr(self.vthread, "video_finished"):
            self.vthread.video_finished.connect(lambda: self.footer.showMessage("Video finished", 3000))

        if hasattr(self.vthread, "error"):
            self.vthread.error.connect(lambda msg: (
                self.footer.showMessage(msg, 5000),
                self.on_auto_no_camera() if (isinstance(src, str) and src == "auto"
                                             and "No camera found for 'auto' source" in msg) else None
            ))

        if hasattr(self.vthread, "debug"):
            self.vthread.debug.connect(lambda msg: self.footer.showMessage(msg, 4000))

        # Start
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
        # Also feed the model (ModelWorker expects RGB np.ndarray)
        try:
            qi = qimg.convertToFormat(QImage.Format_RGB888)
            w, h = qi.width(), qi.height()
            ptr = qi.constBits()
            ptr.setsize(h * qi.bytesPerLine())
            arr = np.frombuffer(ptr, np.uint8).reshape(h, qi.bytesPerLine() // 3, 3)[:, :w, :]
            self.on_frame_for_model(arr)
        except Exception:
            pass
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

        if not getattr(self, "_camera_connected", False):
            self._camera_connected = True
            self.set_connection_status(True)

        # Convert QImage → numpy RGB and send to model
        try:
            qimg = qimg.convertToFormat(QImage.Format_RGB888)
            w, h = qimg.width(), qimg.height()
            ptr = qimg.bits()
            ptr.setsize(qimg.bytesPerLine() * h)
            arr = np.frombuffer(ptr, np.uint8).reshape((h, qimg.bytesPerLine() // 3, 3))[:, :w, :]
            if hasattr(self, "model_worker"):
                self.model_worker.feed_frame(arr.copy())
        except Exception:
            pass

    # camera connected status → flip pill color
    def set_connection_status(self, connected: bool):
        self.topbar.set_camera_connected(connected)

    # ROI button behavior
    def on_roi_toggled(self, checked: bool):
        #VideoCanvas exposes set_roi_mode(), not begin_annotation/cancel_annotation
        self.video_label.set_roi_mode(checked)

    # When user clicks the frame in ROI mode
    def on_roi_marked(self, x: int, y: int):
        idx = self._note_counter  # current note number
        self.video_label.add_marker(x, y, idx)  # pass it to the canvas

        t = QDateTime.currentDateTime().toString("yyyy.MM.dd HH:mm")
        text = self.comment.text().strip() or "Auffälligkeit"
        line = f"#{idx} {t} – {text}"
        self.notes_view.appendPlainText(line)

        self._note_counter += 1
        self.roi_btn.setChecked(False)
        self.comment.clear()


