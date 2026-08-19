"""The article selection algorithm.

Deliberately has no memory beyond the DB: no personalisation, no learning,
no signal from what was tapped. Surprise is the product.
"""

from __future__ import annotations

import random
from typing import Optional

from src.config import (
    CORE_BUCKET_WEIGHTS,
    FALLBACK_FRESHNESS_DAYS,
    FRESHNESS_DAYS,
    MAX_READ_MINUTES,
    MIN_READ_MINUTES,
    WILDCARD_BUCKETS,
    WILDCARD_PROBABILITY,
)
from src.db import Article, ArticleDB


def choose_core_bucket(
    rng: random.Random, exclude: Optional[str] = None
) -> str:
    """Weighted pick from CORE_BUCKET_WEIGHTS, optionally excluding one.

    Excluding renormalises across what's left rather than re-rolling in a
    loop — a loop would terminate eventually but has no bound, and the
    relative weights of the survivors are identical either way.
    """
    buckets = list(CORE_BUCKET_WEIGHTS)
    weights = [CORE_BUCKET_WEIGHTS[b] for b in buckets]

    if exclude is not None and exclude in CORE_BUCKET_WEIGHTS:
        pairs = [(b, w) for b, w in zip(buckets, weights) if b != exclude]
        buckets = [b for b, _ in pairs]
        weights = [w for _, w in pairs]

    return rng.choices(buckets, weights=weights, k=1)[0]


def pick_article(
    db: ArticleDB, rng: Optional[random.Random] = None
) -> Optional[Article]:
    """Choose today's article, or None if nothing qualifies."""
    rng = rng or random.Random()

    if rng.random() < WILDCARD_PROBABILITY:
        buckets = list(WILDCARD_BUCKETS)
    else:
        # Anti-repetition: never the same core bucket two days running.
        # Only applies to core — a wildcard yesterday doesn't constrain
        # today's core roll, since no core bucket shares its name.
        buckets = [choose_core_bucket(rng, exclude=db.last_sent_bucket())]

    capped = db.sources_at_cap()

    # Try fresh first; widen the window only if that comes back empty.
    for fresh_days in (FRESHNESS_DAYS, FALLBACK_FRESHNESS_DAYS):
        candidates = db.unsent_articles(
            buckets, MIN_READ_MINUTES, MAX_READ_MINUTES, fresh_days
        )
        # Source cap is a post-filter, not part of the SQL. It depends on
        # send history rather than article attributes, and applying it
        # after keeps the query about the article and the cap about the
        # source.
        candidates = [a for a in candidates if a.source not in capped]
        if candidates:
            return rng.choice(candidates)

    return None