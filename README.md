# MENACRAFT

Local-first misinformation analysis stack.

## Services

- `services/anonymizer`: PII cleaning and normalization prep.
- `services/classifier`: authenticity + contextual consistency detection (FastAPI, local storage, SQLite, optional Qdrant, OpenRouter via `requests`).
- `services/truth_retrieval`: claim/source intelligence retrieval.
- `services/source_credibility`: source quality scoring.
- `services/orchestrator`: extension-compatible aggregate endpoint.
- `sloppy/`: manual web console for testing direct and orchestrator flows.

## Quick start

```bash
docker compose up --build
```

Main ports:
- `8080` orchestrator
- `8081` anonymizer
- `8082` classifier
- `8083` truth retrieval
- `8084` source credibility
- `3000` sloppy web app (when started separately)

## Classifier v2 highlights

See [services/classifier/README.md](services/classifier/README.md) for complete setup.

- New modular architecture under `services/classifier/app/`.
- Shared library (`app/shared`) used by authenticity + contextual modules.
- New APIs:
	- `POST /v1/analyze`
	- `GET /v1/cases/{case_id}`
	- `GET /v1/cases/{case_id}/report`
	- `POST /v1/context/analyze`
	- `GET /v1/context/cases/{case_id}`
	- `GET /v1/context/cases/{case_id}/report`
- Legacy compatibility still available (`/classify`, `/context`).

## Notes

- The classifier stores state in local SQLite and artifacts on local disk.
- OpenRouter is used via `requests` only.
- Qdrant is optional and retrieval-focused for explainability.
