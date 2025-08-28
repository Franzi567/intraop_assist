# video_thread.py
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import sys, time, os, glob
import cv2
import numpy as np

class VideoThread(QThread):
    # QImage for UI display (safe to pass between threads)
    frame_ready = Signal(QImage)
    # numpy frame (H,W,3) uint8 RGB for model processing
    frame_raw = Signal(object)
    # connection status (camera/file opened)
    connection_changed = Signal(bool)
    # emitted when a file finishes (non-looping)
    video_finished = Signal()
    # error messages
    error = Signal(str)

    def __init__(self, src=0, width=640, height=480, target_fps=22.74, loop_video=True, test_cameras=4):
        """
        src:
          - int (camera index) or string path (video file) or "auto".
        loop_video:
          - if True and src is a file, playback loops.
        test_cameras:
          - when src == "auto", test indices 0..test_cameras-1
        """
        super().__init__()
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        self._requested_src = src
        self._active_src = None
        self.width = width
        self.height = height
        self.target_fps = float(target_fps) if target_fps else 22.0
        self.loop_video = bool(loop_video)
        self.test_cameras = int(test_cameras)
        self._running = True
        self._is_file = False
        self._cap = None
        self._period = 1.0 / max(1.0, self.target_fps)
        # small warmup delay before first capture attempt (ms)
        self._warmup_ms = 150

    # backwards-compatible property
    @property
    def src(self):
        return self._requested_src

    # ----- public API -----
    def set_source(self, src):
        """Change the requested source at runtime. Thread will reopen on next loop."""
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        self._requested_src = src
        # force reopen by releasing cap; next loop will reopen new source
        try:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
        except Exception:
            pass

    def stop(self):
        self._running = False
        # wake thread if sleeping
        try:
            self.wait(200)
        except Exception:
            pass
        try:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
        except Exception:
            pass

    def is_camera_available(self):
        """Quick check if any camera index 0..test_cameras-1 responds."""
        for idx in range(self.test_cameras):
            cap = self._open_cap(idx)
            if cap is None:
                continue
            ok, _ = cap.read()
            try:
                cap.release()
            except Exception:
                pass
            if ok:
                return True
        return False

    # ----- internal helpers -----
    def _open_cap(self, src):
        # ...
        if sys.platform.startswith("win"):
            apis = [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]  # MSMF first on Windows
        else:
            apis = [cv2.CAP_ANY]
        for api in apis:
            cap = None
            try:
                cap = cv2.VideoCapture(src, api)
            except Exception:
                try:
                    cap = cv2.VideoCapture(src)
                except Exception:
                    cap = None
            if cap and cap.isOpened():
                # set prefs (best-effort)
                try:
                    if self.width:  cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
                    if self.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    if self.target_fps: cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                    # reduce buffers if supported
                    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                        try:
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        except Exception:
                            pass
                except Exception:
                    pass
                return cap
            else:
                try:
                    if cap:
                        cap.release()
                except Exception:
                    pass
        return None

    def _detect_camera(self):
        """Return first working camera index, or None."""
        for idx in range(self.test_cameras):
            cap = self._open_cap(idx)
            if cap is None:
                continue
            # try to read a frame (short warmup)
            ret, _ = cap.read()
            try:
                cap.release()
            except Exception:
                pass
            if ret:
                return idx
        return None

    def _find_default_video_file(self):
        """If no camera found for 'auto', try to find a video file in cwd."""
        exts = ("*.mp4", "*.mov", "*.mkv", "*.avi", "*.webm")
        files = []
        for e in exts:
            files.extend(glob.glob(e))
        if not files:
            for d in ("videos", "data", "media"):
                if os.path.isdir(d):
                    for e in exts:
                        files.extend(glob.glob(os.path.join(d, e)))
        return files[0] if files else None

    # ----- main thread loop -----
    def run(self):
        cap = None
        connected = False

        # Determine actual source (detect camera if requested)
        actual_src = self._requested_src
        if actual_src == "auto":
            cam_idx = self._detect_camera()
            if cam_idx is not None:
                actual_src = cam_idx
            else:
                # try to find a default video file before failing
                default_file = self._find_default_video_file()
                if default_file:
                    actual_src = default_file
                else:
                    self.error.emit("No camera found for 'auto' source. Please pass a video file path instead.")
                    return

        # if source is a string and is an existing file => file mode
        if isinstance(actual_src, str) and os.path.isfile(actual_src):
            self._is_file = True
        else:
            self._is_file = False

        # default period (will be overridden for files if file FPS available)
        base_period = 1.0 / max(1, self.target_fps)

        start_time = None
        frame_index = 0

        period = base_period

        while self._running:
            # pick up requested source each loop so set_source() works
            actual_src = self._requested_src

            # if auto requested, try detect camera once (or every reopen)
            if actual_src == "auto":
                cam_idx = self._detect_camera()
                if cam_idx is not None:
                    actual_src = cam_idx
                else:
                    # if no camera, try to find a default file as a fallback
                    default_file = self._find_default_video_file()
                    if default_file:
                        actual_src = default_file
                    else:
                        self.error.emit("No camera found for 'auto' source. Please pass a video file path instead.")
                        return

            # determine file vs camera
            if isinstance(actual_src, str) and os.path.isfile(actual_src):
                self._is_file = True
            else:
                self._is_file = False

            # open if needed
            if cap is None or not cap.isOpened() or self._active_src != actual_src:
                # ensure previous cap closed
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
                cap = self._open_cap(actual_src)
                self._active_src = actual_src
                if cap is None:
                    if connected:
                        self.connection_changed.emit(False)
                        connected = False
                    if self._is_file:
                        self.error.emit(f"Failed to open video file: {actual_src}")
                        return
                    # camera: retry after short pause
                    self.msleep(500)
                    continue
                else:
                    # successfully opened
                    if not connected:
                        self.connection_changed.emit(True)
                        connected = True

                    # decide playback period
                    period = base_period
                    if self._is_file:
                        try:
                            file_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                            if file_fps > 1.0:
                                period = 1.0 / file_fps
                        except Exception:
                            period = base_period
                    else:
                        period = base_period

                    # reset timing baseline for this opened stream
                    start_time = time.monotonic()
                    frame_index = 0
                    # small warmup
                    if self._warmup_ms:
                        self.msleep(int(self._warmup_ms))

            # read frame
            ok, frame = cap.read()
            if not ok:
                # EOF for file
                if self._is_file:
                    if self.loop_video:
                        try:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            start_time = time.monotonic()
                            frame_index = 0
                            self.msleep(10)
                            continue
                        except Exception:
                            self.video_finished.emit()
                            break
                    else:
                        self.video_finished.emit()
                        break
                # camera hiccup: close and retry
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
                if connected:
                    self.connection_changed.emit(False)
                    connected = False
                self.msleep(200)
                continue

            # convert frame to RGB (numpy)
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            except Exception:
                rgb = frame[..., ::-1]

            # timing: compute intended emit time for this frame index
            now = time.monotonic()
            if start_time is None:
                start_time = now

            intended = start_time + frame_index * period

            # If we're ahead of schedule, sleep until it's time to emit.
            if now < intended:
                to_sleep = intended - now
                ms = int(max(1, min(to_sleep * 1000, 1000)))
                self.msleep(ms)
                now = time.monotonic()

            # catch-up if we're far behind
            if now - intended > period * 1.5:
                behind = now - intended
                skip = int(behind // period)
                frame_index += skip
                intended = start_time + frame_index * period

            # Emit frame (build QImage copy) and the raw numpy for model
            h, w = rgb.shape[:2]
            arr = np.ascontiguousarray(rgb)
            qimg = QImage(arr.data, w, h, arr.strides[0], QImage.Format.Format_RGB888).copy()
            try:
                self.frame_ready.emit(qimg)
                self.frame_raw.emit(arr.copy())
            except Exception:
                # if emit fails, swallow (UI might be shutting down)
                pass

            frame_index += 1

        # cleanup on exit
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass
        return
