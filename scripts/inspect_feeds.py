"""Measure feed text and its fit within the configured reading-time range."""

from __future__ import annotations

import argparse
import html
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import feedparser
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    BROWSER_USER_AGENT,
    FEEDS,
    FETCH_TIMEOUT_SECONDS,
    MAX_READ_MINUTES,
    MIN_READ_MINUTES,
    USER_AGENT,
)
from src.readtime import estimate_minutes, word_count  # noqa: E402

ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"

TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")


def strip_html(raw: str) -> str:
    """Convert HTML to text, unescaping only after tags are removed."""
    if not raw:
        return ""
    text = TAG.sub(" ", raw)
    text = html.unescape(text)
    return WHITESPACE.sub(" ", text).strip()


def extract(entry) -> tuple[str, str]:
    """Return the preferred source field and text for a feed entry."""
    if entry.get("content"):
        return "content", strip_html(entry.content[0].get("value", ""))
    if entry.get("summary"):
        return "summary", strip_html(entry.summary)
    return "none", ""


def fetch(url: str):
    for agent in (USER_AGENT, BROWSER_USER_AGENT):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": agent, "Accept": ACCEPT},
                timeout=FETCH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            return None, f"{type(e).__name__}: {e}"
        if r.status_code == 200:
            return feedparser.parse(r.content), None
        if r.status_code != 403:
            break
    return None, f"HTTP {r.status_code}"


def inspect(feed, verbose: bool = False) -> dict | None:
    parsed, error = fetch(feed.url)
    if parsed is None:
        print(f"[FAILED  ] {feed.bucket:<10} {feed.name:<22} {error}")
        return None

    fields = Counter()
    counts = []
    in_range = 0

    for entry in parsed.entries:
        field, text = extract(entry)
        fields[field] += 1
        words = word_count(text)
        counts.append(words)
        minutes = estimate_minutes(text)
        if MIN_READ_MINUTES <= minutes <= MAX_READ_MINUTES:
            in_range += 1
        if verbose:
            print(f"{'':13} {field:<8} {words:>6}w  {minutes:>3}min  "
                  f"{entry.get('title', '?')[:50]}")

    n = len(parsed.entries)
    median = int(statistics.median(counts)) if counts else 0

    pct = (in_range / n * 100) if n else 0
    verdict = "GOOD" if pct >= 30 else ("THIN" if pct > 0 else "DEAD")

    print(
        f"[{verdict:<8}] {feed.bucket:<10} {feed.name:<22} "
        f"{n:>3} entries  "
        f"content={fields['content']:>3} summary={fields['summary']:>3} "
        f"none={fields['none']:>3}  "
        f"median={median:>5}w  usable={in_range:>3} ({pct:.0f}%)"
    )

    return {
        "name": feed.name,
        "bucket": feed.bucket,
        "entries": n,
        "content": fields["content"],
        "summary": fields["summary"],
        "median_words": median,
        "in_range": in_range,
        "pct": pct,
        "verdict": verdict,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", help="inspect only one bucket")
    ap.add_argument("--verbose", action="store_true",
                    help="print every entry, not just the summary line")
    args = ap.parse_args()

    feeds = FEEDS
    if args.bucket:
        feeds = [f for f in feeds if f.bucket == args.bucket]

    results = [r for f in feeds if (r := inspect(f, args.verbose))]

    print(f"\n{'=' * 78}")
    verdicts = Counter(r["verdict"] for r in results)
    print(f"GOOD (>=30% usable): {verdicts['GOOD']}   "
          f"THIN: {verdicts['THIN']}   DEAD (0 usable): {verdicts['DEAD']}")

    full = sum(1 for r in results if r["content"] > r["summary"])
    print(f"Feeds publishing mostly full text: {full}/{len(results)}")

    print("\nUsable articles per bucket (this is the pool the picker sees):")
    per_bucket = Counter()
    for r in results:
        per_bucket[r["bucket"]] += r["in_range"]
    for bucket, total in sorted(per_bucket.items(), key=lambda x: -x[1]):
        print(f"  {bucket:<10} {total:>4}")

    dead = [r["name"] for r in results if r["verdict"] == "DEAD"]
    if dead:
        print(f"\nContributing nothing: {', '.join(dead)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
