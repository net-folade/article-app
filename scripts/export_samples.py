"""Export a handful of real articles as paragraphs for the iPhone reader."""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import FEEDS, MAX_READ_MINUTES, MIN_READ_MINUTES, Feed  # noqa: E402
from src.fetcher import (  # noqa: E402
    PAGE_ACCEPT,
    _ARTICLE_BLOCK,
    _NON_CONTENT,
    _get,
    entry_published,
    is_stale,
    parse_feed,
    strip_html,
    url_hash,
)
from src.readtime import estimate_minutes, word_count  # noqa: E402

log = logging.getLogger(__name__)

MIN_PARAGRAPH_WORDS = 8
# Longer paragraphs that mention these are probably prose, not page chrome.
BOILERPLATE_MAX_WORDS = 40
BOILERPLATE = (
    'subscribe', 'sign up', 'advertisement', 'newsletter', 'all rights reserved',
    'cookie policy', 'accept cookies', 'use cookies', 'click here', 'follow us',
    'share this', 'support our', 'donate', 'log in', 'read more:', 'related:',
    'listen and watch', 'rsvp', 'register here', 'registration required',
)
# Whole words only, so 'log in' does not match 'catalog in'.
_BOILERPLATE = re.compile(
    r'\b(?:' + '|'.join(re.escape(phrase) for phrase in BOILERPLATE) + r')(?!\w)'
)
# Below this a set of paragraphs is probably a teaser card or page chrome.
MIN_BODY_WORDS = 300
ENTRIES_PER_FEED = 4

_PARAGRAPH = re.compile(r'<p\b([^>]*)>(.*?)</p>', re.IGNORECASE | re.DOTALL)
_URL = re.compile(r'https?://')
_BREAK = re.compile(r'<br\s*/?>', re.IGNORECASE)
_TAG = re.compile(r'<[^>]+>')
_WHITESPACE = re.compile(r'\s+')


def _clean_paragraph(raw: str) -> str:
    """Drop inline tags without adding spaces, so 'word</em>,' stays 'word,'."""
    text = _TAG.sub('', _BREAK.sub(' ', raw))
    return _WHITESPACE.sub(' ', html.unescape(text)).strip()


def _is_boilerplate(text: str) -> bool:
    return word_count(text) < BOILERPLATE_MAX_WORDS and bool(
        _BOILERPLATE.search(text.lower())
    )


def _paragraphs_in(fragment: str, bare_only: bool) -> list[str]:
    """Collect readable <p> text; bare_only skips <p class=...> cards and chrome."""
    paragraphs: list[str] = []
    for attrs, raw in _PARAGRAPH.findall(fragment):
        if bare_only and 'class' in attrs.lower():
            continue
        text = _clean_paragraph(raw)
        if (
            word_count(text) < MIN_PARAGRAPH_WORDS
            or _is_boilerplate(text)
            or _URL.search(text)
            or text.startswith('\u2022')
            or text in paragraphs
        ):
            continue
        paragraphs.append(text)
    return paragraphs


def extract_paragraphs(page_html: str) -> list[str]:
    """Return the readable <p> paragraphs of an article page or feed body.

    Article bodies tend to use plain <p> tags while related cards, newsletter
    boxes and modals use classed ones, so plain paragraphs win when they hold
    enough text. The <article> block is tried before the whole page.
    """
    if not page_html:
        return []
    cleaned = _NON_CONTENT.sub(' ', page_html)

    scopes = [cleaned]
    match = _ARTICLE_BLOCK.search(cleaned)
    if match:
        scopes.insert(0, match.group(1))

    for scope in scopes:
        for bare_only in (True, False):
            paragraphs = _paragraphs_in(scope, bare_only)
            if word_count(' '.join(paragraphs)) >= MIN_BODY_WORDS:
                return paragraphs

    return _paragraphs_in(cleaned, bare_only=False)


def _fits(paragraphs: list[str]) -> bool:
    minutes = estimate_minutes(' '.join(paragraphs))
    return MIN_READ_MINUTES <= minutes <= MAX_READ_MINUTES


def _entry_paragraphs(entry) -> list[str]:
    """Prefer full feed content; open the page when the feed is only a teaser."""
    content = entry.get('content')
    if content:
        paragraphs = extract_paragraphs(content[0].get('value', ''))
        if _fits(paragraphs):
            return paragraphs

    raw = _get(entry['link'], PAGE_ACCEPT)
    if raw is None:
        return []
    return extract_paragraphs(raw.decode('utf-8', errors='replace'))


def article_from_feed(feed: Feed) -> Optional[dict]:
    """Return the first recent entry of a feed that reads in 5-15 minutes."""
    try:
        parsed = parse_feed(feed.url)
    except Exception as exc:  # noqa: BLE001 - one feed must not kill the run
        log.warning('feed %s blew up: %s', feed.name, exc)
        return None
    if parsed is None:
        return None

    tried = 0
    for entry in parsed.entries:
        if tried >= ENTRIES_PER_FEED:
            break
        link = entry.get('link')
        published = entry_published(entry)
        if not link or is_stale(published):
            continue
        tried += 1

        paragraphs = _entry_paragraphs(entry)
        if not _fits(paragraphs):
            continue
        return {
            'id': url_hash(link),
            'title': strip_html(entry.get('title', '')) or '(untitled)',
            'source': feed.name,
            'bucket': feed.bucket,
            'url': link,
            'read_minutes': estimate_minutes(' '.join(paragraphs)),
            'published_at': published,
            'paragraphs': paragraphs,
        }
    return None


def pick_articles(limit: int) -> list[dict]:
    """Take at most one article per source, cycling through buckets."""
    by_bucket: dict[str, list[Feed]] = {}
    for feed in FEEDS:
        by_bucket.setdefault(feed.bucket, []).append(feed)

    articles: list[dict] = []
    while len(articles) < limit and any(by_bucket.values()):
        for feeds in by_bucket.values():
            # Try this bucket's feeds until one yields an article.
            while feeds and len(articles) < limit:
                feed = feeds.pop(0)
                article = article_from_feed(feed)
                print(f"{feed.bucket:10} {feed.name:22} "
                      f"{'ok' if article else '-'}", file=sys.stderr)
                if article:
                    articles.append(article)
                    break
    return articles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'app/src/data/samples.json'))
    ap.add_argument('--limit', type=int, default=8)
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING,
                        format='%(levelname)s %(name)s: %(message)s')

    articles = pick_articles(args.limit)
    if not articles:
        print('no articles found; leaving output unchanged', file=sys.stderr)
        return 1

    data = {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'articles': articles,
    }
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(f'wrote {len(articles)} articles to {args.out}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
