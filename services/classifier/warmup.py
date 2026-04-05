"""Pre-download local model weights used by the modular classifier service."""
import os
os.environ["TRANSFORMERS_OFFLINE"] = "0"

print("Downloading sentence transformer (all-MiniLM-L6-v2)…")
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
_ = m.encode(["warmup"])
print("  ✓ sentence transformer ready")

print("All models cached.")
