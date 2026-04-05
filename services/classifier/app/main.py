from __future__ import annotations

from fastapi import FastAPI

from app.api.router import legacy_router, router
from app.shared.logging import configure_logging

configure_logging()

app = FastAPI(title="MENACRAFT Classifier", version="2.0.0")
app.include_router(router)
app.include_router(legacy_router)
