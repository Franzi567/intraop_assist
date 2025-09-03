# model_worker.py — add aliases & error signal
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import numpy as np
import queue, time, os, importlib
import torch

try:
    import lightning.pytorch as pl
except Exception:
    pl = None

class ModelWorker(QThread):
    started_ok = Signal()      # original
    started = Signal()         # alias for MainWindow
    overlay_ready = Signal(QImage)
    debug = Signal(str)
    error = Signal(str)        # NEW

    def __init__(self,
                 ckpt_path: str | None = None,
                 device: str | None = None,
                 input_size: tuple[int, int] = (512, 512),
                 color_rgba: tuple[int, int, int, int] = (0, 140, 255, 180),
                 target_fps: float | None = None,
                 max_queue: int = 1,
                 attn_ckpt: str | None = None,
                 unet_ckpt: str | None = None,
                 **_: object):
        super().__init__()
        self.daemon = True
        self.ckpt_path = ckpt_path or os.environ.get("MODEL_CKPT", "")
        self.attn_ckpt = attn_ckpt or os.environ.get("ATTN_CKPT")
        self.unet_ckpt = unet_ckpt or os.environ.get("UNET_CKPT")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.input_size = input_size
        self.color_rgba = color_rgba
        self.target_delay = (1.0 / float(target_fps)) if (target_fps and target_fps > 0) else None

        self._q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=max(1, int(max_queue)))
        self._running = False
        self._enabled = True
        self._model = None
        self._use_dummy = False

    # public API
    def feed_frame(self, rgb_frame: np.ndarray) -> None:
        if not isinstance(rgb_frame, np.ndarray) or rgb_frame.ndim != 3:
            return
        try:
            if self._q.full():
                _ = self._q.get_nowait()
            self._q.put_nowait(rgb_frame)
        except Exception:
            pass

    # alias expected by MainWindow
    def enqueue_frame(self, rgb_frame: np.ndarray) -> None:
        self.feed_frame(rgb_frame)

    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    # thread
    def run(self):
        self._running = True
        self._log("ModelWorker starting…")
        try:
            self._load_model()
        except Exception as e:
            self._use_dummy = True
            self.error.emit(f"Model load failed: {e}")

        # fire both signals for compatibility
        self.started_ok.emit()
        self.started.emit()

        last_emit = 0.0
        while self._running:
            try:
                frame = self._q.get(timeout=0.25)
            except Exception:
                continue
            if frame is None:
                continue

            try:
                # disabled → emit empty transparent overlay of same size
                if not self._enabled:
                    h, w, _ = frame.shape
                    empty = QImage(w, h, QImage.Format_RGBA8888)
                    empty.fill(0)
                    self.overlay_ready.emit(empty)
                    continue

                if self.target_delay is not None:
                    now = time.time()
                    wait = self.target_delay - (now - last_emit)
                    if wait > 0:
                        time.sleep(wait)

                qimg = self._infer_overlay(frame)
                self.overlay_ready.emit(qimg)
                last_emit = time.time()
            except Exception as e:
                self.error.emit(f"Inference error: {e}")
                self._log(f"Inference error: {e}")

        self._log("ModelWorker stopped.")

    def stop(self):
        self._running = False
        # unblock the .get(timeout=...) immediately
        try:
            self._q.put_nowait(None)
        except Exception:
            pass
        try:
            if self.isRunning():
                self.wait(1500)
        except Exception:
            pass

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    # model loading
    def _load_model(self) -> None:
        try:
            hac_mod = importlib.import_module(".hac_joint_module", package=__package__)
            HACJointModule = getattr(hac_mod, "HACJointModule")
        except Exception as e:
            self._log(f"Import HACJointModule failed ({e}). Using dummy overlay.")
            self._use_dummy = True
            return

        if self.ckpt_path and os.path.exists(self.ckpt_path):
            try:
                if pl is not None and hasattr(HACJointModule, "load_from_checkpoint"):
                    kw = {"map_location": self.device}
                    if self.attn_ckpt: kw["attn_ckpt"] = self.attn_ckpt
                    if self.unet_ckpt: kw["unet_ckpt"] = self.unet_ckpt
                    self._model = HACJointModule.load_from_checkpoint(self.ckpt_path, **kw)
                else:
                    self._model = HACJointModule.from_checkpoint(self.ckpt_path, device=self.device)  # type: ignore
                self._model.eval().to(self.device)
                self._log("Loaded HAC from checkpoint.")
                return
            except Exception as e:
                self._log(f"HAC load_from_checkpoint failed: {e}")
                self.error.emit(f"HAC load failed: {e}")

        # fallback to UNet
        try:
            u_mod = importlib.import_module(".unet_module", package=__package__)
            UNetModule = getattr(u_mod, "UNetModule")
            if self.ckpt_path and os.path.exists(self.ckpt_path) and pl is not None and hasattr(UNetModule, "load_from_checkpoint"):
                self._model = UNetModule.load_from_checkpoint(self.ckpt_path, map_location=self.device)
                self._model.eval().to(self.device)
                self._log("Loaded UNet fallback from checkpoint.")
                return
        except Exception as e:
            self._log(f"UNet fallback failed: {e}")

        self._log("No model available — using dummy overlay.")
        self._use_dummy = True

    # inference
    @torch.no_grad()
    def _infer_overlay(self, frame: np.ndarray) -> QImage:
        h, w, _ = frame.shape
        if self._use_dummy or self._model is None:
            # simple edge magnitude → mask
            gray = np.dot(frame[..., :3].astype(np.float32), [0.299, 0.587, 0.114])
            x = np.transpose(x, (2, 0, 1))[None, ...]
            gy, gx = np.gradient(gray)
            mag = np.sqrt(gx * gx + gy * gy)
            mag = (mag / (mag.max() + 1e-6))
            mask = (mag > 0.25).astype(np.uint8)
        else:
            from PIL import Image
            img = Image.fromarray(frame).resize(self.input_size)
            x = np.asarray(img).astype(np.float32) / 255.0
            x = np.transpose(x, (2, 0, 1))[None, ...]
            x = torch.from_numpy(x).to(self.device)
            out = self._model(x)
            logits = out[1] if isinstance(out, (list, tuple)) and len(out) > 1 else out
            if logits.ndim == 4 and logits.size(1) > 1:
                prob = torch.softmax(logits, dim=1)[:, 1:2]
            else:
                prob = torch.sigmoid(logits)
            prob = torch.nn.functional.interpolate(prob, size=(h, w), mode="bilinear", align_corners=False)
            mask = (prob >= 0.5).float().cpu().numpy()[0, 0].astype(np.uint8)

        r, g, b, a = self.color_rgba
        alpha = (mask * a).astype(np.uint8)
        rgba = np.dstack([
            np.full_like(mask, r, np.uint8),
            np.full_like(mask, g, np.uint8),
            np.full_like(mask, b, np.uint8),
            alpha,
        ])
        qimg = QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888)
        return qimg.copy()

    def _log(self, s: str) -> None:
        self.debug.emit(s)
