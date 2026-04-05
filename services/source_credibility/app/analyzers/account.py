"""
Account behaviour heuristics.

Signals detected:
  - new_account        : account younger than 30 days
  - low_followers      : fewer than 10 followers
  - high_follow_ratio  : following / followers > 10
  - high_post_frequency: posts_count / account_age_days > 50
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from app.models import AuthorInfo

logger = logging.getLogger(__name__)

# ── Thresholds (could be moved to config if needed) ─────────────────────────

NEW_ACCOUNT_DAYS = 30
LOW_FOLLOWERS_THRESHOLD = 10
HIGH_FOLLOW_RATIO = 10.0
HIGH_POST_FREQ = 50  # posts per day


class AccountResult(NamedTuple):
    flags: list[str]
    penalty: float  # total deduction


def analyze_account(author: AuthorInfo) -> AccountResult:
    """Return flags and total penalty for account-level heuristics."""

    flags: list[str] = []
    penalty = 0.0

    # 1. New account
    if author.account_age_days < NEW_ACCOUNT_DAYS:
        flags.append("new_account")
        logger.info(
            "Flag: new_account — %s is %d days old",
            author.username,
            author.account_age_days,
        )

    # 2. Low followers
    if author.followers < LOW_FOLLOWERS_THRESHOLD:
        flags.append("low_followers")
        logger.info(
            "Flag: low_followers — %s has %d followers",
            author.username,
            author.followers,
        )

    # 3. High following-to-followers ratio
    if author.followers > 0 and (author.following / author.followers) > HIGH_FOLLOW_RATIO:
        flags.append("high_follow_ratio")
        logger.info(
            "Flag: high_follow_ratio — %s ratio %.1f",
            author.username,
            author.following / author.followers,
        )
    elif author.followers == 0 and author.following > 0:
        flags.append("high_follow_ratio")
        logger.info(
            "Flag: high_follow_ratio — %s has 0 followers but %d following",
            author.username,
            author.following,
        )

    # 4. Extremely high posting frequency
    if author.account_age_days > 0:
        freq = author.posts_count / author.account_age_days
        if freq > HIGH_POST_FREQ:
            flags.append("high_post_frequency")
            logger.info(
                "Flag: high_post_frequency — %s posts/day %.1f",
                author.username,
                freq,
            )

    # Each flag carries the same per-signal weight (applied in scorer)
    penalty = len(flags)  # caller multiplies by WEIGHT_ACCOUNT_SIGNAL

    return AccountResult(flags=flags, penalty=penalty)
