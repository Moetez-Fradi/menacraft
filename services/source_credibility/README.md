# Source Credibility Service

Real-time source credibility assessment for the Menacraft misinformation detection platform.

## Architecture

```
app/
├── main.py                  # FastAPI application & /analyze endpoint
├── config.py                # Env-var driven configuration
├── models.py                # Pydantic request/response schemas
├── scorer.py                # Score aggregation & risk mapping
└── analyzers/
    ├── account.py           # Account behaviour heuristics
    ├── links.py             # URL/domain reputation analysis
    └── writing_style.py     # LLM + heuristic writing style check
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python -m app.main
# → http://localhost:8084

# Run tests
pip install pytest
pytest tests/ -v
```

## Docker

```bash
docker build -t source-credibility .
docker run -p 8084:8084 source-credibility
```

## Configuration

Copy `.env.example` → `.env` and adjust values.  All settings are optional — the service runs with sane defaults.

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | _(empty)_ | Key for LLM-based writing analysis |
| `LLM_ENABLED` | `true` | Toggle LLM calls (falls back to heuristics) |
| `WEIGHT_ACCOUNT_SIGNAL` | `0.2` | Score deduction per account flag |
| `WEIGHT_SUSPICIOUS_DOMAIN` | `0.3` | Score deduction per suspicious domain |
| `WEIGHT_WRITING_STYLE` | `0.2` | Score deduction for inconsistent writing |
| `DOMAIN_CACHE_TTL` | `3600` | Domain reputation cache TTL (seconds) |
| `SERVICE_PORT` | `8084` | HTTP listen port |

## Example Request

```bash
curl -X POST http://localhost:8084/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "BREAKING!!! You wont believe what just happened!!!",
    "author": {
      "username": "news_bot_99",
      "account_age_days": 5,
      "followers": 3,
      "following": 4200,
      "posts_count": 900
    },
    "content_metadata": {
      "timestamp": "2026-04-04T12:00:00Z",
      "platform": "twitter"
    },
    "links": [
      "https://cnn-breaking.xyz/story",
      "https://bit.ly/abc123"
    ]
  }'
```

## Example Response

```json
{
  "credibility_score": 0.0,
  "risk_level": "HIGH",
  "flags": [
    "new_account",
    "low_followers",
    "high_follow_ratio",
    "high_post_frequency",
    "suspicious_domain",
    "inconsistent_writing_style"
  ],
  "explanation": "The source @news_bot_99 raises significant credibility concerns. The account is only 5 days old. The account has very few followers (3). The following-to-followers ratio is unusually high. The posting frequency is abnormally high. Suspicious domains detected: cnn-breaking.xyz, bit.ly. Writing style flagged (heuristic): matched pattern: (!!!|\\.{4,}|\\?{3,})."
}
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/analyze` | Analyse source credibility |
| `GET` | `/health` | Health / readiness probe |
| `GET` | `/docs` | Swagger UI (auto-generated) |
