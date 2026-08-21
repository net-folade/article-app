"""Persist articles in SQLite through an S3-ready context manager."""

from __future__ import annotations

import contextlib
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator, Optional

from src.config import PER_SOURCE_MONTHLY_CAP, SOURCE_CAP_WINDOW_DAYS

STATUS_NEW = 'new'
STATUS_SENT = 'sent'


def utcnow() -> str:
    """Return UTC ISO text with microseconds to preserve send ordering."""
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def days_ago(days: int) -> str:
    """ISO timestamp `days` in the past. Used for freshness cutoffs."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec='microseconds'
    )


@dataclass
class Article:
    """One article. `url_hash` is the primary key and the dedupe mechanism."""

    url_hash: str
    url: str
    title: str
    source: str
    bucket: str
    read_minutes: int
    body_excerpt: str = ''
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=utcnow)
    status: str = STATUS_NEW
    sent_at: Optional[str] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    url_hash      TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    source        TEXT NOT NULL,
    bucket        TEXT NOT NULL,
    read_minutes  INTEGER NOT NULL,
    body_excerpt  TEXT NOT NULL DEFAULT '',
    published_at  TEXT,
    fetched_at    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',
    sent_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_pick
    ON articles (status, bucket, read_minutes, fetched_at);

CREATE INDEX IF NOT EXISTS idx_sent
    ON articles (status, sent_at);
"""


class ArticleDB:
    """Thin wrapper over SQLite. Every query is parameterised."""

    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> 'ArticleDB':
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def upsert_articles(self, articles: Iterable[Article]) -> int:
        """Insert new articles without resurrecting existing or sent rows."""
        rows = [
            (
                a.url_hash, a.url, a.title, a.source, a.bucket,
                a.read_minutes, a.body_excerpt, a.published_at,
                a.fetched_at, a.status, a.sent_at,
            )
            for a in articles
        ]
        if not rows:
            return 0
        before = self.conn.total_changes
        self.conn.executemany(
            """
            INSERT INTO articles (
                url_hash, url, title, source, bucket, read_minutes,
                body_excerpt, published_at, fetched_at, status, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_hash) DO NOTHING
            """,
            rows,
        )
        self.conn.commit()
        return self.conn.total_changes - before

    def mark_sent(self, url_hash: str) -> None:
        self.conn.execute(
            'UPDATE articles SET status = ?, sent_at = ? WHERE url_hash = ?',
            (STATUS_SENT, utcnow(), url_hash),
        )
        self.conn.commit()

    def unsent_articles(
        self,
        buckets: Iterable[str],
        min_minutes: int,
        max_minutes: int,
        fresh_days: int,
    ) -> list[Article]:
        """Candidates matching bucket, read-time window, and freshness."""
        buckets = list(buckets)
        if not buckets:
            return []
        # SQLite requires one parameterized placeholder per IN value.
        placeholders = ','.join('?' for _ in buckets)
        sql = f"""
            SELECT * FROM articles
             WHERE status = ?
               AND bucket IN ({placeholders})
               AND read_minutes BETWEEN ? AND ?
               AND fetched_at >= ?
        """
        params = [
            STATUS_NEW, *buckets, min_minutes, max_minutes,
            days_ago(fresh_days),
        ]
        rows = self.conn.execute(sql, params).fetchall()
        return [Article(**dict(row)) for row in rows]

    def last_sent_bucket(self) -> Optional[str]:
        """Bucket of the most recently sent article, or None."""
        row = self.conn.execute(
            """
            SELECT bucket FROM articles
             WHERE status = ? AND sent_at IS NOT NULL
             ORDER BY sent_at DESC
             LIMIT 1
            """,
            (STATUS_SENT,),
        ).fetchone()
        return row['bucket'] if row else None

    def source_picks_last_30_days(self) -> dict[str, int]:
        """How many times each source has been sent inside the cap window."""
        rows = self.conn.execute(
            """
            SELECT source, COUNT(*) AS n FROM articles
             WHERE status = ? AND sent_at >= ?
             GROUP BY source
            """,
            (STATUS_SENT, days_ago(SOURCE_CAP_WINDOW_DAYS)),
        ).fetchall()
        return {row['source']: row['n'] for row in rows}

    def sources_at_cap(self) -> set[str]:
        counts = self.source_picks_last_30_days()
        return {s for s, n in counts.items() if n >= PER_SOURCE_MONTHLY_CAP}


def _s3_client():
    """Create an S3 client only when needed."""
    import boto3

    return boto3.client('s3')


def _download_state(client, bucket: str, key: str, local_path: str) -> bool:
    """Download state.db, or return False when it does not exist."""
    from botocore.exceptions import ClientError

    try:
        client.download_file(bucket, key, local_path)
    except ClientError as exc:
        code = exc.response.get('Error', {}).get('Code')
        # A missing file is normal on the first run. Raise all other errors.
        if code in ('404', 'NoSuchKey'):
            return False
        raise
    return True


@contextlib.contextmanager
def s3_backed_db(
    bucket: Optional[str] = None,
    key: str = 'state.db',
    local_path: Optional[str] = None,
) -> Iterator[ArticleDB]:
    """Use a local database and sync it with S3 when given a bucket."""
    if local_path is None:
        fd, local_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        cleanup = True
    else:
        cleanup = False

    client = _s3_client() if bucket is not None else None
    if client is not None:
        _download_state(client, bucket, key, local_path)

    db = ArticleDB(local_path)
    uploaded = False
    try:
        yield db
        # Upload only after a successful run.
        db.close()
        if client is not None:
            client.upload_file(local_path, bucket, key)
            uploaded = True
    finally:
        if not uploaded:
            db.close()
        if cleanup:
            with contextlib.suppress(FileNotFoundError):
                os.remove(local_path)
