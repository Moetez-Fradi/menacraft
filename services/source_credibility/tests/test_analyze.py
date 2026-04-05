"""
Pytest test suite for the Source Credibility Service.

Run:  pytest tests/ -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Health endpoint ─────────────────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ── Fully credible source ──────────────────────────────────────────────────

def test_credible_source():
    payload = {
        "text": "Breaking: The UN published its climate report today.",
        "author": {
            "username": "legit_reporter",
            "account_age_days": 1200,
            "followers": 50000,
            "following": 300,
            "posts_count": 4500,
        },
        "content_metadata": {
            "timestamp": "2026-04-04T12:00:00Z",
            "platform": "twitter",
        },
        "links": ["https://www.reuters.com/article/climate"],
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["credibility_score"] >= 0.75
    assert data["risk_level"] == "LOW"
    assert len(data["flags"]) == 0


# ── Suspicious source (new account + low followers + shady links) ──────────

def test_suspicious_source():
    payload = {
        "author": {
            "username": "bot_farm_42",
            "account_age_days": 3,
            "followers": 2,
            "following": 5000,
            "posts_count": 800,
        },
        "links": [
            "https://cnn-breaking-news.xyz/exclusive",
            "https://bit.ly/3abc",
        ],
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["credibility_score"] < 0.4
    assert data["risk_level"] == "HIGH"
    assert "new_account" in data["flags"]
    assert "low_followers" in data["flags"]
    assert "suspicious_domain" in data["flags"]


# ── Spam text triggers writing style flag (heuristic) ──────────────────────

def test_spam_text_heuristic():
    payload = {
        "text": "BUY NOW!!! LIMITED TIME OFFER!!! Click here to earn $1000 per day!!!",
        "author": {
            "username": "spammer",
            "account_age_days": 5,
            "followers": 0,
            "following": 100,
            "posts_count": 50,
        },
        "links": [],
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "inconsistent_writing_style" in data["flags"]
    assert data["risk_level"] in ("MEDIUM", "HIGH")


# ── Medium-risk source ─────────────────────────────────────────────────────

def test_medium_risk_source():
    payload = {
        "author": {
            "username": "new_user",
            "account_age_days": 15,
            "followers": 50,
            "following": 200,
            "posts_count": 30,
        },
        "links": [],
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # Only new_account flag → one deduction of 0.2 → score 0.8
    # Actually the account has 50 followers so not low_followers
    # Follow ratio 200/50 = 4 which is < 10 so not high_follow_ratio
    # Only flag is new_account
    assert data["credibility_score"] == 0.8
    assert data["risk_level"] == "LOW"  # 0.8 >= 0.75


# ── No text, no links — pure account analysis ──────────────────────────────

def test_account_only():
    payload = {
        "author": {
            "username": "minimal_user",
            "account_age_days": 365,
            "followers": 1000,
            "following": 500,
            "posts_count": 200,
        },
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["credibility_score"] == 1.0
    assert data["risk_level"] == "LOW"
    assert data["flags"] == []


# ── Validation error ───────────────────────────────────────────────────────

def test_missing_author_returns_422():
    resp = client.post("/analyze", json={"text": "hello"})
    assert resp.status_code == 422


def test_response_contains_explainability_payload():
    payload = {
        "text": "Major policy update announced by city council today.",
        "author": {
            "username": "civic_updates",
            "account_age_days": 400,
            "followers": 3200,
            "following": 120,
            "posts_count": 900,
        },
        "links": ["https://www.bbc.com/news"],
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "explainability" in data
    assert isinstance(data["explainability"], dict)
    assert "explanation" in data["explainability"]
    assert "signals" in data["explainability"]
    assert "score_breakdown" in data["explainability"]
    assert "debug" in data["explainability"]
    assert "traces" in data["explainability"]
