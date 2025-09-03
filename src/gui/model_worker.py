# model_worker.py — robust model importer + latency-synced overlay (emits with frame_id)
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import numpy as np
import queue, time, os, importlib
from typing import Optional, Tuple

try:
    import torch
    TORCH_OK = True
    torch.set_grad_enabled(False)
    try:
        torch.backends.cudnn.benchmark = True  # speed up convs on fixed-size inputs
    except Exception:
        pass
except Exception:
    torch = None  # type: ignore
    TORCH_OK = False

try:
    import lightning.pytorch as pl  # type: ignore
except Exception:
    pl = None  # type: ignore


def _import_first(names: list[str]):
    """Try importing the first module path that succeeds; return module or None."""
    for n in names:
        try:
            return importlib.import_module(n)
        except Exception:
            continue
    return None


class ModelWorker(QThread):
    started_ok = Signal()
    started = Signal()
    overlay_ready = Signal(QImage, int)  # (overlay_qimage, frame_id)
    debug = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        ckpt_path: Optional[str] = None,
        device: Optional[str] = None,
        input_size: tuple[int, int] = (512, 512),
        color_rgba: tuple[int, int, int, int] = (0, 140, 255, 180),
        target_fps: Optional[float] = None,   # optional pacing, but UI is event-driven
        max_queue: int = 1,
        attn_ckpt: Optional[str] = None,
        unet_ckpt: Optional[str] = None,
        **_: object,
    ):
        super().__init__()
        self.daemon = True
        self.ckpt_path = ckpt_path or os.environ.get("MODEL_CKPT", "")
        self.attn_ckpt = attn_ckpt or os.environ.get("ATTN_CKPT")
        self.unet_ckpt = unet_ckpt or os.environ.get("UNET_CKPT")
        self.device = device or ("cuda" if TORCH_OK and torch.cuda.is_available() else "cpu")
        self.input_size = input_size
        self.color_rgba = color_rgba
        self.target_delay = (1.0 / float(target_fps)) if (target_fps and target_fps > 0) else None

        import queue as _q
        # Queue holds tuples: (frame_rgb_np, frame_id)
        self._q: "_q.Queue[Tuple[np.ndarray | None, Optional[int]]]" = _q.Queue(maxsize=max(1, int(max_queue)))
        self._running = False
        self._enabled = True
        self._model = None
        self._use_dummy = not TORCH_OK  # if no torch, force dummy

    # ---------------- public API ----------------
    def feed_frame(self, rgb_frame: np.ndarray, frame_id: int) -> None:
        if not isinstance(rgb_frame, np.ndarray) or rgb_frame.ndim != 3:
            return
        try:
            if self._q.full():
                _ = self._q.get_nowait()
            self._q.put_nowait((rgb_frame, frame_id))
        except Exception:
            pass

    # Backward-compat (signature kept but frame_id missing → ignored)
    def enqueue_frame(self, rgb_frame: np.ndarray) -> None:
        try:
            self.feed_frame(rgb_frame, -1)
        except Exception:
            pass

    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    # ---------------- thread ----------------
    def run(self):
        self._running = True
        self._log(f"ModelWorker starting on device={self.device} …")
        try:
            if not self._use_dummy:
                self._load_model()
        except Exception as e:
            self._use_dummy = True
            self.error.emit(f"Model load failed: {e}")

        self.started_ok.emit()
        self.started.emit()

        last_emit = 0.0
        while self._running:
            try:
                frame, fid = self._q.get(timeout=0.25)
            except Exception:
                continue
            if frame is None or fid is None:
                continue

            try:
                if not self._enabled:
                    # Emit transparent overlay of same size so UI can "pair" and still draw raw frame if desired
                    h, w, _ = frame.shape
                    empty = QImage(w, h, QImage.Format_RGBA8888)
                    empty.fill(0)
                    self.overlay_ready.emit(empty, int(fid))
                    continue

                if self.target_delay is not None:
                    now = time.time()
                    wait = self.target_delay - (now - last_emit)
                    if wait > 0:
                        time.sleep(wait)

                qimg = self._infer_overlay(frame)
                self.overlay_ready.emit(qimg, int(fid))
                last_emit = time.time()
            except Exception as e:
                self.error.emit(f"Inference error: {e}")
                self._log(f"Inference error: {e}")

        self._log("ModelWorker stopped.")

    def stop(self):
        self._running = False
        try:
            self._q.put_nowait((None, None))
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

    # ---------------- model loading ----------------
    def _load_model(self) -> None:
        # Try multiple paths so GUI can live in src/gui and models in src/models or src/hac/models
        hac_mod = _import_first([
            "src.hac.models.hac_joint_module",
            "src.models.hac_joint_module",
            "hac_joint_module",
            f"{__package__}.hac_joint_module" if __package__ else "hac_joint_module",
        ])
        if hac_mod is None:
            self._log("Import HACJointModule failed. Using dummy overlay.")
            self._use_dummy = True
            return

        HACJointModule = getattr(hac_mod, "HACJointModule", None)
        if HACJointModule is None:
            self._log("HACJointModule symbol not found. Using dummy overlay.")
            self._use_dummy = True
            return

        # Load from checkpoint if given; otherwise expect attn/unet ckpts
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
                self._log("Loaded HAC model from checkpoint.")
                return
            except Exception as e:
                self._log(f"HAC load_from_checkpoint failed: {e}")
                self.error.emit(f"HAC load failed: {e}")

        # If we get here, no full ckpt; try to construct from partial ckpts/configs if supported
        if self.attn_ckpt or self.unet_ckpt:
            try:
                self._model = HACJointModule(attn_ckpt=self.attn_ckpt, unet_ckpt=self.unet_ckpt)
                self._model.eval().to(self.device)
                self._log("Constructed HAC from partial ckpts.")
                return
            except Exception as e:
                self._log(f"Partial HAC construction failed: {e}")

        self._log("No model available — using dummy overlay.")
        self._use_dummy = True

    # ---------------- inference ----------------
    def _infer_overlay(self, frame: np.ndarray) -> QImage:
        h, w, _ = frame.shape
        if self._use_dummy or self._model is None or not TORCH_OK:
            # Fast edge magnitude → mask
            gray = np.dot(frame[..., :3].astype(np.float32), [0.299, 0.587, 0.114])
            gy, gx = np.gradient(gray)
            mag = np.sqrt(gx * gx + gy * gy)
            mag = (mag / (mag.max() + 1e-6))
            mask = (mag > 0.25).astype(np.uint8)
        else:
            import PIL.Image as PILImage
            # autocast to speed up on CUDA
            autocast = torch.cuda.amp.autocast if (self.device == "cuda") else torch.cpu.amp.autocast  # type: ignore[attr-defined]
            with torch.no_grad(), autocast():
                img = PILImage.fromarray(frame).resize(self.input_size)
                x = np.asarray(img).astype(np.float32) / 255.0
                x = np.transpose(x, (2, 0, 1))[None, ...]
                x_t = torch.from_numpy(x).to(self.device)  # type: ignore
                out = self._model(x_t)
                logits = out[1] if isinstance(out, (list, tuple)) and len(out) > 1 else out
                if logits.ndim == 4 and logits.size(1) > 1:  # type: ignore
                    prob = torch.softmax(logits, dim=1)[:, 1:2]  # type: ignore
                else:
                    prob = torch.sigmoid(logits)  # type: ignore
                prob = torch.nn.functional.interpolate(prob, size=(h, w), mode="bilinear", align_corners=False)  # type: ignore
                mask = (prob >= 0.5).float().cpu().numpy()[0, 0].astype(np.uint8)  # type: ignore

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
        try:
            self.debug.emit(s)
        except Exception:
            pass
