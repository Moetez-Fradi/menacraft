from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.analyzers.account import AccountResult
from app.analyzers.links import LinksResult
from app.analyzers.writing_style import WritingStyleResult
from app.config import LLM_ENABLED, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL
from app.models import CredibilityRequest
from app.scorer import ScoreResult

logger = logging.getLogger(__name__)


async def _llm_explainability(prompt_payload: dict[str, Any]) -> dict[str, Any] | None:
    if not LLM_ENABLED or not OPENROUTER_API_KEY:
        return None

    system_prompt = (
        "You are a source-credibility explainability engine. "
        "Given scoring inputs, produce concise, factual JSON. "
        "Respond with valid JSON only and no markdown."
    )

    user_prompt = {
        "task": "Generate explainability for source credibility scoring",
        "input": prompt_payload,
        "output_schema": {
            "summary": "string",
            "signals": [
                {
                    "name": "string",
                    "impact": "low|medium|high",
                    "reason": "string",
                }
            ],
            "recommended_action": "string",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(user_prompt)},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 350,
                },
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            summary = str(parsed.get("summary", "")).strip()
            signals = parsed.get("signals", [])
            recommended_action = str(parsed.get("recommended_action", "")).strip()

            if not summary:
                return None

            return {
                "summary": summary,
                "signals": signals if isinstance(signals, list) else [],
                "recommended_action": recommended_action,
                "method": "llm",
            }
    except Exception as exc:
        logger.warning("Explainability LLM failed, using deterministic fallback: %s", exc)
        return None


def _deterministic_explainability(
    req: CredibilityRequest,
    account: AccountResult,
    links: LinksResult,
    writing: WritingStyleResult,
    score: ScoreResult,
) -> dict[str, Any]:
    signals: list[dict[str, str]] = []

    for flag in account.flags:
        signals.append(
            {
                "name": flag,
                "impact": "high" if flag in {"new_account", "high_follow_ratio"} else "medium",
                "reason": "Account-level behavioral heuristic triggered",
            }
        )

    if links.suspicious_domains:
        signals.append(
            {
                "name": "suspicious_domain",
                "impact": "high",
                "reason": f"Suspicious domains found: {', '.join(links.suspicious_domains[:3])}",
            }
        )

    if writing.inconsistent:
        signals.append(
            {
                "name": "inconsistent_writing_style",
                "impact": "medium",
                "reason": writing.detail,
            }
        )

    if not signals:
        signals.append(
            {
                "name": "no_major_signals",
                "impact": "low",
                "reason": "No strong suspicious signals were detected",
            }
        )

    summary = (
        f"Source @{req.author.username} scored {score.score:.2f} with risk {score.risk_level}. "
        f"{len(signals)} explainability signal(s) contributed to this assessment."
    )

    return {
        "summary": summary,
        "signals": signals,
        "recommended_action": (
            "Escalate to manual review" if score.risk_level in {"HIGH", "MEDIUM"} else "Low risk; monitor normally"
        ),
        "method": "deterministic",
    }


async def build_explainability(
    req: CredibilityRequest,
    account: AccountResult,
    links: LinksResult,
    writing: WritingStyleResult,
    score: ScoreResult,
) -> dict[str, Any]:
    base_payload = {
        "author": {
            "username": req.author.username,
            "account_age_days": req.author.account_age_days,
            "followers": req.author.followers,
            "following": req.author.following,
            "posts_count": req.author.posts_count,
        },
        "link_count": len(req.links),
        "suspicious_domains": links.suspicious_domains,
        "account_flags": account.flags,
        "writing": {
            "inconsistent": writing.inconsistent,
            "method": writing.method,
            "detail": writing.detail,
        },
        "score": {
            "credibility_score": score.score,
            "risk_level": score.risk_level,
        },
    }

    llm_result = await _llm_explainability(base_payload)
    fallback = _deterministic_explainability(req, account, links, writing, score)

    chosen = llm_result if llm_result is not None else fallback

    return {
        "explanation": chosen["summary"],
        "signals": chosen["signals"],
        "recommended_action": chosen["recommended_action"],
        "score_breakdown": {
            "base_score": 1.0,
            "account_penalty": account.penalty,
            "suspicious_domain_penalty": links.penalty,
            "writing_penalty": 1.0 if writing.inconsistent else 0.0,
            "final_score": score.score,
        },
        "debug": {
            "llm_enabled": LLM_ENABLED,
            "llm_api_key_present": bool(OPENROUTER_API_KEY),
            "writing_analysis_method": writing.method,
            "writing_detail": writing.detail,
            "llm_explainability_used": chosen["method"] == "llm",
            "account_flags": account.flags,
            "suspicious_domains": links.suspicious_domains,
        },
        "traces": [
            {
                "service": "source_credibility.account",
                "ok": True,
                "flags": account.flags,
            },
            {
                "service": "source_credibility.links",
                "ok": True,
                "suspicious_domains": links.suspicious_domains,
            },
            {
                "service": "source_credibility.writing_style",
                "ok": True,
                "method": writing.method,
                "inconsistent": writing.inconsistent,
            },
            {
                "service": "source_credibility.explainability",
                "ok": True,
                "method": chosen["method"],
            },
        ],
    }
