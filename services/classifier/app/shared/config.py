from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MENACRAFT Classifier Service"
    app_env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8082

    data_dir: str = "./data"
    sqlite_path: str = "./data/classifier.db"

    rate_limit_default_per_minute: int = 30
    rate_limit_analyze_per_minute: int = 12

    ollama_model: str = "llama3.1:8b-instruct-q4_K_M"
    ollama_vision_model: str = "llava:7b"
    ollama_base_url: str = "http://localhost:11434/api/chat"
    ollama_timeout_seconds: int = 45
    ollama_retries: int = 2
    require_ollama_for_analyze: bool = True
    require_ollama_for_image_analyze: bool = True

    qdrant_enabled: bool = False
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_http_similarity_enabled: bool = False
    qdrant_http_similarity_threshold: float = 0.92
    qdrant_http_similarity_timeout_seconds: int = 4

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    transcription_enabled: bool = False

    max_upload_mb: int = Field(default=50, ge=1, le=500)


settings = Settings()
