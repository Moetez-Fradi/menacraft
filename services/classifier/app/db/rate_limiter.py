from __future__ import annotations

import time

from fastapi import HTTPException, Request

from app.shared.config import settings
from app.shared.db import SQLiteRepository


class SQLiteSlidingWindowRateLimiter:
    def __init__(self, repo: SQLiteRepository) -> None:
        self.repo = repo

    def check(self, ip: str, endpoint: str, limit_per_minute: int) -> None:
        now = int(time.time())
        cutoff = now - 60
        self.repo.prune_rate_limit_events(cutoff_epoch=now - 600)
        seen = self.repo.count_recent_rate_limit_events(ip=ip, endpoint=endpoint, cutoff_epoch=cutoff)
        if seen >= limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {endpoint}: {limit_per_minute}/min",
            )
        self.repo.record_rate_limit_event(ip=ip, endpoint=endpoint, ts_epoch=now)


async def enforce_rate_limit(request: Request) -> None:
    repo = SQLiteRepository()
    limiter = SQLiteSlidingWindowRateLimiter(repo)
    endpoint = request.url.path
    ip = request.client.host if request.client else "unknown"
    limit = (
        settings.rate_limit_analyze_per_minute
        if endpoint.endswith("/analyze")
        else settings.rate_limit_default_per_minute
    )
    limiter.check(ip=ip, endpoint=endpoint, limit_per_minute=limit)
