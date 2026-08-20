"""Check every feed in config.FEEDS against reality.

Feeds die, move, and go paywalled. This is a maintenance tool, not a
one-off — run it whenever the picker starts looking thin.

    python scripts/validate_feeds.py            # all feeds
    python scripts/validate_feeds.py --bucket curious
    python scripts/validate_feeds.py --unverified-only

Exit code is 0 only when every checked feed is usable, so it works as a
CI gate later if you want one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests

# Run as a script from the repo root, so the package isn't importable yet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    BROWSER_USER_AGENT,
    FEEDS,
    FETCH_TIMEOUT_SECONDS,
    USER_AGENT,
    Feed,
)

ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"

# Matches a <link rel=alternate type=application/rss+xml href=...> tag in
# a page <head>. Regex over HTML is fragile in general, but this is a
# throwaway diagnostic, not a parser we depend on at runtime.
FEED_LINK_TAG = re.compile(
    r"<link[^>]+application/(?:rss|atom)\+xml[^>]*>", re.IGNORECASE
)
HREF = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)


def _get(url: str, user_agent: str) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": user_agent, "Accept": ACCEPT},
        timeout=FETCH_TIMEOUT_SECONDS,
    )


def discover(feed_url: str) -> list[str]:
    """Ask the site's homepage which feeds it advertises.

    Used when a URL 404s — the feed usually still exists, just somewhere
    else. This is what an RSS reader does when you paste a bare domain.
    """
    parts = urlparse(feed_url)
    homepage = f"{parts.scheme}://{parts.netloc}/"
    try:
        r = _get(homepage, BROWSER_USER_AGENT)
        r.raise_for_status()
    except requests.RequestException:
        return []

    found = []
    for tag in FEED_LINK_TAG.findall(r.text):
        match = HREF.search(tag)
        if match:
            found.append(urljoin(homepage, match.group(1)))
    # Preserve order, drop duplicates.
    return list(dict.fromkeys(found))


def check(feed: Feed) -> bool:
    """Fetch, parse, and report. True only if the feed is usable."""
    label = f"{feed.bucket:<10} {feed.name:<22}"

    response = None
    for user_agent in (USER_AGENT, BROWSER_USER_AGENT):
        try:
            response = _get(feed.url, user_agent)
        except requests.RequestException as e:
            print(f"[FAILED ] {label} {type(e).__name__}: {e}")
            return False
        if response.status_code == 200:
            break
        # A 403 usually means bot protection reacting to our User-Agent,
        # so retrying as a browser is worth one attempt. Any other status
        # won't change based on who's asking.
        if response.status_code != 403:
            break

    if response.status_code != 200:
        print(f"[HTTP{response.status_code:4}] {label} {feed.url}")
        if response.status_code == 404:
            for candidate in discover(feed.url)[:3]:
                print(f"{'':11} └─ try: {candidate}")
        return False

    parsed = feedparser.parse(response.content)
    n = len(parsed.entries)

    if n == 0:
        print(f"[EMPTY  ] {label} parsed, no entries")
        for candidate in discover(feed.url)[:3]:
            print(f"{'':11} └─ try: {candidate}")
        return False

    # bozo means feedparser hit something malformed. Not automatically
    # fatal — plenty of real feeds are slightly broken but still usable —
    # so surface it and judge per feed.
    note = f"  bozo: {type(parsed.bozo_exception).__name__}" if parsed.bozo else ""
    title = parsed.feed.get("title", "?")
    print(f"[OK  {n:3}] {label} {title}{note}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", help="check only one bucket")
    ap.add_argument(
        "--unverified-only",
        action="store_true",
        help="skip feeds already marked verified in config",
    )
    args = ap.parse_args()

    feeds = FEEDS
    if args.bucket:
        feeds = [f for f in feeds if f.bucket == args.bucket]
    if args.unverified_only:
        feeds = [f for f in feeds if not f.verified]

    if not feeds:
        print("No feeds matched.")
        return 1

    results = {f.name: check(f) for f in feeds}
    ok = sum(results.values())
    print(f"\n{ok}/{len(results)} usable")

    broken = [name for name, good in results.items() if not good]
    if broken:
        print("Remove or replace: " + ", ".join(broken))
    return 0 if not broken else 1


if __name__ == "__main__":
    sys.exit(main())