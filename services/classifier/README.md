# MENACRAFT Classifier Service (Local-First)

This service provides two modules in one FastAPI app:
- **Authenticity detection** (`/v1/analyze`) for manipulation + AI-generated scoring.
- **Contextual consistency detection** (`/v1/context/analyze`) for claim-vs-content mismatch and reused-context checks.

It keeps compatibility with existing legacy routes:
- `POST /classify`
- `POST /context`
- `GET /health`

## Architecture

Code is organized under `app/`:

- `app/shared/` shared config, schemas, db, storage, utils, clients
- `app/normalizers/` ingestion normalization into canonical artifacts
- `app/analyzers/` text/image/audio/video analyzers
- `app/fusion/` fusion scorer and verdict logic
- `app/contextual_consistency/` claim parsing, retrieval, rules, entailment, llm judge, fusion
- `app/api/` API routes

Persistence:
- **SQLite** for cases, jobs, model runs, evidence summaries, rate-limit state, feedback
- **Filesystem** for case input payloads and normalized artifacts
- **Qdrant (optional)** for retrieval and explainability vectors

## System dependencies

Install locally:
- Python 3.11+ (3.12 recommended; 3.14 supported with the current dependency set)
- `ffmpeg`
- (optional) OCR tools only if you extend OCR

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## Python dependencies

```bash
cd services/classifier
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# or with uv
uv pip install -r requirements.txt
```

If install fails on very new Python versions, prefer Python 3.11/3.12 for this service.

## Configuration

```bash
cp .env.example .env
```

Required for strong text/context LLM features:
- local Ollama server with a pulled model

Main vars:
- `OLLAMA_MODEL` (default `llama3.1:8b-instruct-q4_K_M`)
- `OLLAMA_VISION_MODEL` (default `llava:7b`)
- `OLLAMA_BASE_URL` (default `http://localhost:11434/api/chat`)
- `REQUIRE_OLLAMA_FOR_ANALYZE=true|false` (default `true`)
- `REQUIRE_OLLAMA_FOR_IMAGE_ANALYZE=true|false` (default `true`)
- `QDRANT_ENABLED=true|false`
- `QDRANT_URL=http://localhost:6333`
- `SQLITE_PATH=./data/classifier.db`

### Ollama setup

Run Ollama locally and pull a model:

```bash
ollama serve
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull llava:7b
```

If Ollama is on another host, set `OLLAMA_BASE_URL` in `.env`.

When `REQUIRE_OLLAMA_FOR_ANALYZE=true`, `POST /v1/analyze` fails for text inputs if Ollama is unavailable or errors, instead of silently falling back.
When `REQUIRE_OLLAMA_FOR_IMAGE_ANALYZE=true`, `POST /v1/analyze` fails for image inputs if vision inference is unavailable, instead of silently falling back to heuristics.

## Run service

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8082
```

Health:

```bash
curl http://localhost:8082/v1/health
```

## API endpoints

Core:
- `POST /v1/analyze`
- `GET /v1/cases/{case_id}`
- `GET /v1/cases/{case_id}/report`
- `POST /v1/context/analyze`
- `GET /v1/context/cases/{case_id}`
- `GET /v1/context/cases/{case_id}/report`
- `GET /v1/models`
- `POST /v1/feedback`

Legacy-compatible:
- `POST /classify`
- `POST /context`

## Example request/response

Analyze request:

```json
{
  "session_id": "abc123",
  "text": "This happened today in Paris",
  "image_base64": "<base64>",
  "content_type": "image",
  "metadata": {
    "platform": "twitter"
  }
}
```

Analyze accepted response:

```json
{
  "case_id": "abc123",
  "job_status": "completed",
  "accepted_at": "2026-04-05T12:00:00Z",
  "input_summary": {
    "content_type": "image",
    "text_length": 28,
    "image_count": 1,
    "video_frame_count": 0,
    "audio_count": 0
  }
}
```

Context analyze request:

```json
{
  "case_id": "abc123",
  "claim_text": "this happened today in Paris",
  "platform_metadata": {
    "platform": "twitter"
  }
}
```

## Qdrant setup and seeding

Run local Qdrant:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Enable in `.env`:

```bash
QDRANT_ENABLED=true
QDRANT_URL=http://localhost:6333
```

Use notebooks in `notebooks/`:
- `01_build_reference_embeddings.ipynb`
- `02_train_meta_classifier.ipynb`
- `03_threshold_calibration.ipynb`

## Testing

```bash
pytest -q
```

Included tests:
- unit: normalizer, rate limiter, ollama client, fusion, claim parsing, context fusion
- integration: ingest-to-report flow

## Notes on AI feature failures

This service surfaces AI feature failures explicitly in `debug` payloads (for example `ollama_not_configured` or `transcription_not_available`) and does not silently pretend full model coverage when a required AI component is unavailable.
