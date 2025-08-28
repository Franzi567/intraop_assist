# model_worker.py
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from PIL import Image
import numpy as np
import queue, time, os, inspect, importlib

# torch is required for inference types/ops
import torch

# Optional Lightning (only for isinstance checks)
try:
    import lightning.pytorch as pl  # type: ignore
except Exception:
    pl = None


def _parse_rgba_env(name: str, default=(255, 0, 0, 255)):
    """
    Accepts:
      - "r,g,b" or "r,g,b,a"
      - "#RRGGBB" or "#RRGGBBAA"
    """
    s = os.environ.get(name, "").strip()
    if not s:
        return default
    try:
        if s.startswith("#"):
            s = s[1:]
            if len(s) == 6:
                r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16); a = 255
            elif len(s) == 8:
                r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16); a = int(s[6:8], 16)
            else:
                return default
            return (r, g, b, a)
        parts = [int(x.strip()) for x in s.split(",")]
        if len(parts) == 3:
            return (parts[0], parts[1], parts[2], 255)
        if len(parts) == 4:
            return (parts[0], parts[1], parts[2], parts[3])
    except Exception:
        pass
    return default


class ModelWorker(QThread):
    overlay_ready = Signal(QImage)
    error = Signal(str)
    started_ok = Signal()

    def __init__(
        self,
        target_fps: int = 5,
        max_queue: int = 2,
        hac_wrapper_cls=None,
        device=None,
    ):
        """
        target_fps: processing rate (approx)
        max_queue: frames buffered
        hac_wrapper_cls: optional class to use for HACWrapper (for testing)
        device: optional device string/torch.device forwarded to HACWrapper
        """
        super().__init__()
        self.target_fps = max(1, int(target_fps))
        self._period = 1.0 / self.target_fps
        self._q = queue.Queue(maxsize=max_queue)
        self._running = True
        self._hac = None
        self.hac_wrapper_cls = hac_wrapper_cls
        self.device = device

        # --- overlay shaping knobs from environment ---
        # Only probabilities above OVERLAY_THR contribute to alpha (after normalization).
        self._ov_thr = float(os.environ.get("OVERLAY_THR", 0.5))
        # OVERLAY_GAMMA > 1.0 compresses low confidences; < 1.0 expands them.
        self._ov_gamma = float(os.environ.get("OVERLAY_GAMMA", 1.5))
        # OVERLAY_COLOR e.g. "0,255,0,255" or "#00FF00CC"
        self._ov_color = _parse_rgba_env("OVERLAY_COLOR", (255, 0, 0, 255))

    # ---------------- thread entry ----------------
    def run(self):
        # lazy import / load inside thread
        try:
            if self.hac_wrapper_cls is None:
                # standard location for your wrapper
                mod = importlib.import_module("server.models.hac_wrapper")
                self.hac_wrapper_cls = getattr(mod, "HACWrapper")
            # instantiate (handle ctor signatures)
            try:
                self._hac = self.hac_wrapper_cls(device=self.device) if self.device is not None else self.hac_wrapper_cls()
            except TypeError:
                self._hac = self.hac_wrapper_cls()
        except Exception as e:
            self.error.emit(f"Model load failed: {e}")
            return

        self.started_ok.emit()
        last_time = 0.0

        while self._running:
            try:
                frame = self._q.get(timeout=0.25)  # numpy RGB (H,W,3) uint8
            except queue.Empty:
                continue

            now = time.time()
            if (now - last_time) < self._period:
                # throttle to target_fps
                continue
            last_time = now

            try:
                pil = Image.fromarray(frame)  # RGB
                # Prefer the wrapper’s own overlay method if available
                if hasattr(self._hac, "infer_to_overlay"):
                    overlay_pil = self._hac.infer_to_overlay(pil)
                    if overlay_pil.mode != "RGBA":
                        overlay_pil = overlay_pil.convert("RGBA")
                else:
                    # Fallback: do inference here and build overlay with thr/gamma
                    overlay_pil = self._infer_and_build_overlay(pil)

                # → QImage (RGBA8888)
                w, h = overlay_pil.size
                data = overlay_pil.tobytes("raw", "RGBA")
                qimg = QImage(data, w, h, QImage.Format.Format_RGBA8888).copy()
                self.overlay_ready.emit(qimg)

            except Exception as e:
                self.error.emit(f"Inference error: {e}")

        return

    # ----------------- helper: inference + overlay -----------------
    def _infer_and_build_overlay(self, pil_img: Image.Image) -> Image.Image:
        """
        Fallback path if HACWrapper lacks infer_to_overlay():
          - Try HACWrapper.infer() if present; otherwise call (preprocess → model)
          - Unify outputs (tuple/dict/tensor)
          - Convert logits→prob if needed
          - Build RGBA overlay with threshold+gamma mapping
        """
        # Try wrapper.infer(pil)
        out = None
        if hasattr(self._hac, "infer"):
            out = self._hac.infer(pil_img)
        else:
            # Try raw model with wrapper.preprocess
            if not hasattr(self._hac, "model"):
                raise RuntimeError("HAC interface provides neither infer_to_overlay nor infer/model.")
            if not hasattr(self._hac, "preprocess"):
                # Minimal preprocess if wrapper has none
                # Default input size via env: MODEL_INPUT_SIZE="512,512"
                in_size = tuple(map(int, os.environ.get("MODEL_INPUT_SIZE", "512,512").split(",")))
                img = pil_img.resize(in_size, Image.BILINEAR).convert("RGB")
                arr = np.asarray(img).astype("float32") / 255.0
                inp = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
                dev = getattr(self._hac, "device", torch.device("cpu"))
                inp = inp.to(dev)
            else:
                inp = self._hac.preprocess(pil_img)

            dev = getattr(self._hac, "device", torch.device("cpu"))
            model = self._hac.model
            model.eval()
            with torch.no_grad(), torch.autocast(device_type=(dev.type if isinstance(dev, torch.device) else "cuda"),
                                                 enabled=(isinstance(dev, torch.device) and dev.type == "cuda")):
                out = model(inp)

        # --- unify output to a single 4D tensor (B,1,H,W) logits/probs ---
        out = self._select_tensor_from_output(out)

        # --- to probabilities (numpy HxW) ---
        prob = self._tensor_to_prob(out)

        # --- build colored RGBA overlay with threshold + gamma ---
        overlay = self._prob_to_rgba_overlay(prob, pil_img.size)
        return overlay

    # ----------------- tensor utilities -----------------
    def _select_tensor_from_output(self, out):
        """Pick the most likely segmentation tensor from tuple/dict/tensor outputs."""
        if torch.is_tensor(out):
            return out
        if isinstance(out, (list, tuple)):
            tensors = [t for t in out if torch.is_tensor(t)]
            # Prefer 4D tensors (B,C,H,W); pick the last (often segmentation logits)
            four_d = [t for t in tensors if t.ndim == 4]
            if four_d:
                return four_d[-1]
            if tensors:
                return tensors[-1]
            raise RuntimeError("Model returned tuple/list without tensor entries.")
        if isinstance(out, dict):
            for key in ("mask", "pred", "out", "logits", "probs", "prediction", "seg_logits"):
                if key in out and torch.is_tensor(out[key]):
                    return out[key]
            vals = [v for v in out.values() if torch.is_tensor(v)]
            if not vals:
                raise RuntimeError("Model returned dict without tensor values.")
            return vals[0]
        raise RuntimeError(f"Unsupported model output type: {type(out)}")

    def _tensor_to_prob(self, t: torch.Tensor) -> np.ndarray:
        """
        Convert logits/probs tensor to (H,W) numpy probabilities in [0,1].
        """
        # Make sure it's on CPU and detached
        # Detect logits by range and apply sigmoid if needed
        if t.max() > 1.5 or t.min() < -0.5:
            p = torch.sigmoid(t)
        else:
            p = t
        if p.ndim == 4:
            # Use first channel
            p = p[:, 0:1, :, :]
        p = p.squeeze().detach().cpu().numpy().astype("float32")
        # Clamp numerically
        return np.clip(p, 0.0, 1.0)

    def _prob_to_rgba_overlay(self, prob: np.ndarray, out_size) -> Image.Image:
        """
        Map prob → alpha using threshold + gamma, then colorize as RGBA.
        """
        thr = float(self._ov_thr)
        gamma = float(self._ov_gamma)
        # keep only values above threshold, renormalize to 0..1
        if thr > 0.0:
            prob = np.clip((prob - thr) / max(1e-6, 1.0 - thr), 0.0, 1.0)
        # apply gamma (gamma>1 suppresses low alphas)
        if abs(gamma - 1.0) > 1e-6:
            prob = prob ** (1.0 / gamma)

        alpha = (prob * 255.0).astype("uint8")
        a_img = Image.fromarray(alpha, mode="L")

        r, g, b, a = self._ov_color  # base color (we’ll override alpha)
        overlay = Image.new("RGBA", a_img.size, (r, g, b, 0))
        overlay.putalpha(a_img)

        if a != 255:
            # global alpha cap from color's A
            # multiply current alpha by a/255
            if a < 255:
                alpha_scaled = (alpha.astype(np.uint16) * a // 255).astype("uint8")
                overlay = Image.merge("RGBA", (
                    Image.new("L", a_img.size, r),
                    Image.new("L", a_img.size, g),
                    Image.new("L", a_img.size, b),
                    Image.fromarray(alpha_scaled, mode="L")
                ))

        if overlay.size != out_size:
            overlay = overlay.resize(out_size, Image.BILINEAR)
        return overlay

    # ----------------- public API -----------------
    def enqueue_frame(self, arr: np.ndarray):
        try:
            if not isinstance(arr, np.ndarray):
                return
            if not arr.flags["C_CONTIGUOUS"]:
                arr = np.ascontiguousarray(arr)
            if self._q.full():
                try:
                    self._q.get_nowait()
                except Exception:
                    pass
            self._q.put_nowait(arr)
        except Exception:
            pass

    def stop(self):
        self._running = False
        try:
            self.wait(300)
        except Exception:
            pass




