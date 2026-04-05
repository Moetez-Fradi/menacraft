from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app.db.rate_limiter import SQLiteSlidingWindowRateLimiter
from app.shared.db import SQLiteRepository


def test_rate_limiter_blocks_after_limit(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "test.db"))
    limiter = SQLiteSlidingWindowRateLimiter(repo)
    ip = "127.0.0.1"
    endpoint = "/v1/analyze"

    limiter.check(ip, endpoint, limit_per_minute=2)
    limiter.check(ip, endpoint, limit_per_minute=2)

    with pytest.raises(HTTPException) as exc:
        limiter.check(ip, endpoint, limit_per_minute=2)

    assert exc.value.status_code == 429


def test_rate_limiter_allows_after_window(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "test.db"))
    limiter = SQLiteSlidingWindowRateLimiter(repo)
    ip = "127.0.0.2"
    endpoint = "/v1/models"

    now = int(time.time())
    repo.record_rate_limit_event(ip, endpoint, now - 200)
    limiter.check(ip, endpoint, limit_per_minute=1)
