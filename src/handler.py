"""Run the daily fetch, select, push, and persistence sequence."""

from __future__ import annotations

import logging
import os
from typing import Optional

from src.db import s3_backed_db
from src.fetcher import fetch_all
from src.picker import pick_article
from src.pusher import push_article

log = logging.getLogger()
log.setLevel(logging.INFO)


def run(bucket: Optional[str] = None, push: bool = True) -> dict:
    """Run one cycle and return a log-friendly summary."""
    with s3_backed_db(bucket=bucket) as db:
        articles = fetch_all()
        inserted = db.upsert_articles(articles)
        log.info("fetched %d articles, %d new", len(articles), inserted)

        chosen = pick_article(db)
        if chosen is None:
            log.info("nothing qualified today")
            return {
                "fetched": len(articles),
                "inserted": inserted,
                "sent": None,
            }

        if push:
            push_article(chosen)
        # Mark only after a successful push so failures remain eligible.
        db.mark_sent(chosen.url_hash)

        log.info("sent %s — %s", chosen.source, chosen.title)
        return {
            "fetched": len(articles),
            "inserted": inserted,
            "sent": {
                "title": chosen.title,
                "source": chosen.source,
                "bucket": chosen.bucket,
                "read_minutes": chosen.read_minutes,
                "url": chosen.url,
            },
        }


def lambda_handler(event, context) -> dict:
    """AWS Lambda entrypoint. S3_BUCKET is set by Terraform."""
    return run(bucket=os.environ.get("S3_BUCKET"))
