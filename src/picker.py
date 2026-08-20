"""The article selection algorithm.

Deliberately has no memory beyond the DB: no personalisation, no learning,
no signal from what was tapped. Surprise is the product.
"""

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


def core_buckets_in_weighted_order(
    rng: random.Random, exclude: Optional[str] = None
) -> Iterator[str]:
    """Yield every core bucket, weighted-random, without replacement.

    The first bucket comes out with exactly the configured weights, so
    the distribution is unchanged on any day the first choice has an
    article. The rest of the sequence only matters when it doesn't.

    Lazy on purpose: a caller that stops after the first bucket consumes
    exactly one draw from `rng`, same as choose_core_bucket did.
    """
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
    """Choose today's article, or None if nothing anywhere qualifies.

    Buckets are tried in order until one yields a candidate. A thin
    bucket used to mean no notification at all that morning: the roll
    landed on it, both freshness windows came back empty, and the
    function returned None while other buckets sat full. Now an empty
    bucket costs a fall-through, not the day.
    """
    rng = rng or random.Random()

    # Anti-repetition: never the same core bucket two days running. It
    # holds across the whole fall-through chain, not just the first roll
    # — otherwise a thin bucket would quietly reintroduce the repeats.
    # Only applies to core; no core bucket shares a wildcard's name.
    last = db.last_sent_bucket()
    wildcard_pool = list(WILDCARD_BUCKETS)
    core_pools = ([b] for b in core_buckets_in_weighted_order(rng, exclude=last))

    if rng.random() < WILDCARD_PROBABILITY:
        attempts = itertools.chain([wildcard_pool], core_pools)
    else:
        attempts = itertools.chain(core_pools, [wildcard_pool])

    capped = db.sources_at_cap()

    for buckets in attempts:
        # Try fresh first; widen the window only if that comes back
        # empty. Both windows are exhausted for a bucket before moving
        # on, so a slightly stale article from the bucket we actually
        # rolled beats a fresh one from a bucket we didn't.
        for fresh_days in (FRESHNESS_DAYS, FALLBACK_FRESHNESS_DAYS):
            candidates = db.unsent_articles(
                buckets, MIN_READ_MINUTES, MAX_READ_MINUTES, fresh_days
            )
            # Source cap is a post-filter, not part of the SQL. It
            # depends on send history rather than article attributes, and
            # applying it after keeps the query about the article and the
            # cap about the source.
            candidates = [a for a in candidates if a.source not in capped]
            if candidates:
                return rng.choice(candidates)

    return None