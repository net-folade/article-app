"""Select an article using only persisted send history."""

from __future__ import annotations

import itertools
import random
from typing import Iterator, Optional

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
    """Choose a weighted core bucket, optionally excluding one."""
    buckets = list(CORE_BUCKET_WEIGHTS)
    weights = [CORE_BUCKET_WEIGHTS[b] for b in buckets]

    if exclude is not None and exclude in CORE_BUCKET_WEIGHTS:
        pairs = [(b, w) for b, w in zip(buckets, weights) if b != exclude]
        buckets = [b for b, _ in pairs]
        weights = [w for _, w in pairs]

    return rng.choices(buckets, weights=weights, k=1)[0]


def core_buckets_in_weighted_order(
    rng: random.Random, exclude: Optional[str] = None
) -> Iterator[str]:
    """Yield core buckets in weighted-random order without replacement."""
    remaining = {
        b: w for b, w in CORE_BUCKET_WEIGHTS.items() if b != exclude
    }
    while remaining:
        buckets = list(remaining)
        weights = [remaining[b] for b in buckets]
        chosen = rng.choices(buckets, weights=weights, k=1)[0]
        yield chosen
        del remaining[chosen]


def pick_article(
    db: ArticleDB, rng: Optional[random.Random] = None
) -> Optional[Article]:
    """Choose an eligible article, falling through empty buckets."""
    rng = rng or random.Random()

    # Exclude yesterday's core bucket throughout the fallback chain.
    last = db.last_sent_bucket()
    wildcard_pool = list(WILDCARD_BUCKETS)
    core_pools = ([b] for b in core_buckets_in_weighted_order(rng, exclude=last))

    if rng.random() < WILDCARD_PROBABILITY:
        attempts = itertools.chain([wildcard_pool], core_pools)
    else:
        attempts = itertools.chain(core_pools, [wildcard_pool])

    capped = db.sources_at_cap()

    for buckets in attempts:
        # Exhaust both freshness windows before falling through.
        for fresh_days in (FRESHNESS_DAYS, FALLBACK_FRESHNESS_DAYS):
            candidates = db.unsent_articles(
                buckets, MIN_READ_MINUTES, MAX_READ_MINUTES, fresh_days
            )
            candidates = [a for a in candidates if a.source not in capped]
            if candidates:
                return rng.choice(candidates)

    return None
