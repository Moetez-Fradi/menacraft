"""Pre-download all model weights at Docker build time."""
import os
os.environ["TRANSFORMERS_OFFLINE"] = "0"

print("Downloading AI-text detector (openai-community/roberta-base-openai-detector)…")
from transformers import pipeline
pipe = pipeline(
    "text-classification",
    model="openai-community/roberta-base-openai-detector",
    device=-1,
    top_k=None,
)
# Quick sanity-check
result = pipe("The quick brown fox jumps over the lazy dog.", truncation=True)
print(f"  ✓ detector ready  sample={result}")

print("Downloading CLIP (openai/clip-vit-base-patch32)…")
from transformers import CLIPModel, CLIPProcessor
CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
print("  ✓ CLIP ready")

print("Downloading sentence transformer (paraphrase-MiniLM-L3-v2)…")
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("paraphrase-MiniLM-L3-v2", device="cpu")
_ = m.encode(["warmup"])
print("  ✓ sentence transformer ready")

print("All models cached.")
