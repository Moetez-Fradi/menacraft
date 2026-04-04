"""Pre-download sentence transformer at Docker build time."""
print("Downloading sentence transformer (paraphrase-MiniLM-L3-v2)…")
from sentence_transformers import SentenceTransformer
SentenceTransformer("paraphrase-MiniLM-L3-v2", device="cpu")
print("  ✓ sentence transformer ready")
