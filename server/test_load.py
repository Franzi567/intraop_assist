# server/test_load.py
from dotenv import load_dotenv
from pathlib import Path
import os

# --- load .env from project root BEFORE importing project modules ---
root = Path(__file__).resolve().parents[1]   # project root (parent of server/)
load_dotenv(root / ".env")

# sensible defaults if .env missing keys
os.environ.setdefault("MODEL_MODULE", "server.models.hac_module")
os.environ.setdefault("MODEL_CLASS", "HACJointModule")
os.environ.setdefault("MODEL_PATH", "server/models/checkpoints/epoch019-best.ckpt")
os.environ.setdefault("DEVICE", "cpu")

# now import project code that may rely on those env vars
from .models.hac_wrapper import HACWrapper

print("MODEL_MODULE:", os.environ.get("MODEL_MODULE"))
print("MODEL_CLASS:", os.environ.get("MODEL_CLASS"))
print("MODEL_PATH:", os.environ.get("MODEL_PATH"))
print("DEVICE:", os.environ.get("DEVICE"))

# create wrapper (will pick up env defaults, or you can pass explicit args)
w = HACWrapper()
print("Loaded models object:", type(w.model), "on device", w.device)
