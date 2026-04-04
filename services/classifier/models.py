"""
Lazy-loaded, CPU-only model registry.
Models are initialized once on first use and cached for the process lifetime.
"""
from __future__ import annotations

import threading
from typing import Optional

# ─── Text AI-detector ────────────────────────────────────────────────────────
# openai-community/roberta-base-openai-detector
#   Labels: "Real" (human-written) | "Fake" (AI-generated)
#   Trained by OpenAI on GPT-2 output; generalizes reasonably to modern LLMs.

_text_lock     = threading.Lock()
_text_pipeline = None


def get_text_classifier():
    global _text_pipeline
    if _text_pipeline is None:
        with _text_lock:
            if _text_pipeline is None:
                from transformers import pipeline
                _text_pipeline = pipeline(
                    "text-classification",
                    model="openai-community/roberta-base-openai-detector",
                    device=-1,   # CPU
                    top_k=None,
                )
    return _text_pipeline


# ─── CLIP (text-image consistency, Axis 2) ───────────────────────────────────

_clip_lock      = threading.Lock()
_clip_model     = None
_clip_processor = None


def get_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        with _clip_lock:
            if _clip_model is None:
                from transformers import CLIPModel, CLIPProcessor
                _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                _clip_model.eval()
                _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return _clip_model, _clip_processor


# ─── Sentence similarity (Axes 2 + 4) ────────────────────────────────────────

_sim_lock  = threading.Lock()
_sim_model = None


def get_similarity_model():
    global _sim_model
    if _sim_model is None:
        with _sim_lock:
            if _sim_model is None:
                from sentence_transformers import SentenceTransformer
                _sim_model = SentenceTransformer(
                    "paraphrase-MiniLM-L3-v2",
                    device="cpu",
                )
    return _sim_model
