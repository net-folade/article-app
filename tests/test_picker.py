import os
import random
import tempfile
from collections import Counter

import pytest

from src.config import CORE_BUCKET_WEIGHTS, WILDCARD_BUCKETS
from src.db import Article, ArticleDB, days_ago, utcnow
from src.picker import choose_core_bucket, pick_article

ALL_BUCKETS = list(CORE_BUCKET_WEIGHTS) + list(WILDCARD_BUCKETS)


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = ArticleDB(path)
    yield database
    database.close()
    os.remove(path)


def article(url_hash, bucket, source=None, read_minutes=8, fetched_at=None):
    return Article(
        url_hash=url_hash,
        url=f"https://example.com/{url_hash}",
        title=f"Article {url_hash}",
        source=source or f"src-{url_hash}",
        bucket=bucket,
        read_minutes=read_minutes,
        fetched_at=fetched_at or utcnow(),
    )


def stock(db, per_bucket=40, buckets=None, **kw):
    """Fill every bucket with articles, each from a unique source.

    Unique sources matter: with a shared source the 3-per-30-days cap
    drains the pool after three picks and the statistical tests measure
    the cap instead of the thing they claim to measure.
    """
    buckets = buckets or ALL_BUCKETS
    rows = [
        article(f"{b}-{i}", b, **kw)
        for b in buckets
        for i in range(per_bucket)
    ]
    db.upsert_articles(rows)


# --- statistical --------------------------------------------------------


def test_wildcard_rate_is_30_percent_over_1000_runs(db):
    """Nothing is marked sent, so no anti-repetition or cap interference."""
    stock(db)
    rng = random.Random(42)
    wildcard = sum(
        1 for _ in range(1000)
        if pick_article(db, rng).bucket in WILDCARD_BUCKETS
    )
    assert 0.23 <= wildcard / 1000 <= 0.37


def test_core_bucket_weights_respected_over_many_runs(db):
    stock(db)
    rng = random.Random(7)
    counts = Counter()
    for _ in range(5000):
        picked = pick_article(db, rng)
        if picked.bucket in CORE_BUCKET_WEIGHTS:
            counts[picked.bucket] += 1

    total = sum(counts.values())
    for bucket, weight in CORE_BUCKET_WEIGHTS.items():
        assert abs(counts[bucket] / total - weight) < 0.06, bucket


def test_choose_core_bucket_never_returns_excluded():
    rng = random.Random(1)
    assert all(
        choose_core_bucket(rng, exclude="ai") != "ai" for _ in range(500)
    )


# --- anti-repetition ----------------------------------------------------


def test_anti_repetition_no_back_to_back_core_buckets(db):
    stock(db, per_bucket=40)
    rng = random.Random(99)
    previous = None
    for _ in range(80):
        picked = pick_article(db, rng)
        assert picked is not None
        if (
            previous in CORE_BUCKET_WEIGHTS
            and picked.bucket in CORE_BUCKET_WEIGHTS
        ):
            assert picked.bucket != previous
        db.mark_sent(picked.url_hash)
        previous = picked.bucket


# --- filters ------------------------------------------------------------

def test_returns_none_when_db_completely_empty(db):
    assert pick_article(db, random.Random(0)) is None


def test_read_time_filter_excludes_out_of_range(db):
    db.upsert_articles([
        article("too-short", "ai", read_minutes=2),
        article("too-long", "ai", read_minutes=30),
        article("just-right", "ai", read_minutes=9),
    ])
    rng = random.Random(3)
    for _ in range(60):
        picked = pick_article(db, rng)
        if picked is not None:
            assert picked.url_hash == "just-right"


def test_fallback_widens_when_no_fresh_articles_in_bucket(db):
    """Everything is 10 days old: outside 7, inside the 14-day fallback."""
    stock(db, per_bucket=5, fetched_at=days_ago(10))
    picked = pick_article(db, random.Random(11))
    assert picked is not None


def test_nothing_picked_when_all_articles_beyond_fallback(db):
    stock(db, per_bucket=5, fetched_at=days_ago(30))
    assert pick_article(db, random.Random(11)) is None


def test_source_cap_prevents_dominance(db):
    """Aeon is already at the cap; its articles must never be picked."""
    for i in range(3):
        db.upsert_articles([article(f"sent{i}", "essays", source="Aeon")])
        db.mark_sent(f"sent{i}")

    db.upsert_articles([
        article("aeon-new", "essays", source="Aeon"),
        article("lrb-new", "essays", source="LRB"),
    ])

    rng = random.Random(5)
    for _ in range(100):
        picked = pick_article(db, rng)
        if picked is not None:
            assert picked.source != "Aeon"


def test_sent_articles_are_never_resurfaced(db):
    db.upsert_articles([article("only", "ai")])
    rng = random.Random(2)
    first = None
    while first is None:
        first = pick_article(db, rng)
    db.mark_sent(first.url_hash)
    assert all(pick_article(db, rng) is None for _ in range(30))