"""Pull RSS/Atom feeds and turn entries into articles."""

from __future__ import annotations

import hashlib
import html
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import requests

from src.config import (
    BODY_EXCERPT_CHARS,
    BROWSER_USER_AGENT,
    FEED_GROUPS,
    FEEDS,
    FETCH_TIMEOUT_SECONDS,
    MAX_ARTICLE_AGE_DAYS,
    MAX_PAGE_FETCHES_PER_RUN,
    TEASER_WORD_THRESHOLD,
    USER_AGENT,
    Feed,
)
from src.db import Article
from src.readtime import estimate_minutes, word_count

log = logging.getLogger(__name__)

FEED_ACCEPT = (
    'application/rss+xml, application/atom+xml, application/xml, '
    'text/xml, */*'
)
PAGE_ACCEPT = 'text/html,application/xhtml+xml,*/*'

# Campaign parameters do not distinguish articles during deduplication.
TRACKING_PARAMS = {'ref', 'ref_src', 'source', 'fbclid', 'gclid', 'mc_cid',
                   'mc_eid', 'cmpid', 'campaign_id'}
TRACKING_PREFIXES = ('utm_',)

_TAG = re.compile(r'<[^>]+>')
_WHITESPACE = re.compile(r'\s+')
# Remove page chrome with its contents.
_NON_CONTENT = re.compile(
    r'<(script|style|nav|header|footer|aside|form|noscript|svg)\b[^>]*>'
    r'.*?</\1>',
    re.IGNORECASE | re.DOTALL,
)
_ARTICLE_BLOCK = re.compile(
    r'<article\b[^>]*>(.*?)</article>', re.IGNORECASE | re.DOTALL
)
_PARAGRAPH = re.compile(r'<p\b[^>]*>(.*?)</p>', re.IGNORECASE | re.DOTALL)

# Thin paragraph sets may be paywall stubs or div-based layouts.
_MIN_PARAGRAPH_WORDS = 100


def strip_html(raw: str) -> str:
    """Convert HTML to text, unescaping only after tags are removed."""
    if not raw:
        return ''
    text = _TAG.sub(' ', raw)
    text = html.unescape(text)
    return _WHITESPACE.sub(' ', text).strip()


def extract_body(page_html: str) -> str:
    """Extract prose, falling back to cleaned page text for thin paragraph sets."""
    if not page_html:
        return ''
    cleaned = _NON_CONTENT.sub(' ', page_html)

    match = _ARTICLE_BLOCK.search(cleaned)
    if match:
        cleaned = match.group(1)

    paragraphs = strip_html(' '.join(_PARAGRAPH.findall(cleaned)))
    if word_count(paragraphs) >= _MIN_PARAGRAPH_WORDS:
        return paragraphs

    return strip_html(cleaned)


def normalize_url(url: str) -> str:
    """Canonicalize a URL for hashing and deduplication."""
    if not url:
        return ''
    parts = urlsplit(url.strip())

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    path = parts.path
    if path.endswith('/') and len(path) > 1:
        path = path.rstrip('/')
    elif path == '/':
        path = ''

    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
        and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, ''))


def url_hash(url: str) -> str:
    """Return 128 bits of SHA-256 over the normalized URL as hex."""
    return hashlib.sha256(normalize_url(url).encode('utf-8')).hexdigest()[:32]


def _get(url: str, accept: str) -> Optional[bytes]:
    """GET a URL, retrying once with a browser user agent on 403."""
    response = None
    for agent in (USER_AGENT, BROWSER_USER_AGENT):
        try:
            response = requests.get(
                url,
                headers={'User-Agent': agent, 'Accept': accept},
                timeout=FETCH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            log.warning('fetch failed %s: %s', url, exc)
            return None
        if response.status_code == 200:
            return response.content
        if response.status_code != 403:
            break
    log.warning('fetch failed %s: HTTP %s', url,
                response.status_code if response is not None else '?')
    return None


def parse_feed(url: str):
    """Fetch a feed, accepting malformed parses that still contain entries."""
    raw = _get(url, FEED_ACCEPT)
    if raw is None:
        return None
    parsed = feedparser.parse(raw)
    if not parsed.entries:
        log.warning('no entries in %s', url)
        return None
    return parsed


def fetch_page_text(url: str) -> str:
    """Open an article page and return its body text, or '' on failure."""
    raw = _get(url, PAGE_ACCEPT)
    if raw is None:
        return ''
    return extract_body(raw.decode('utf-8', errors='replace'))


def entry_text(entry) -> str:
    """Return full entry content when available, otherwise its summary."""
    content = entry.get('content')
    if content:
        return strip_html(content[0].get('value', ''))
    if entry.get('summary'):
        return strip_html(entry.get('summary'))
    return ''


def entry_published(entry) -> Optional[str]:
    """Return the entry's publication time as UTC ISO text, if present."""
    for key in ('published_parsed', 'updated_parsed'):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat(
                timespec='microseconds'
            )
    return None


def is_stale(published_at: Optional[str], now: Optional[datetime] = None) -> bool:
    """Return whether a dated article exceeds the age limit; retain undated entries."""
    if not published_at:
        return False
    try:
        when = datetime.fromisoformat(published_at)
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return when < now - timedelta(days=MAX_ARTICLE_AGE_DAYS)


def feeds_for_today(
    feeds: Optional[Iterable[Feed]] = None, today: Optional[date] = None
) -> list[Feed]:
    """Return today's stateless, bucket-mixed rotation group."""
    feeds = list(FEEDS if feeds is None else feeds)
    today = today or date.today()
    group = today.toordinal() % FEED_GROUPS
    return [f for i, f in enumerate(feeds) if i % FEED_GROUPS == group]


def articles_from_feed(
    feed: Feed, page_budget: int = 0
) -> tuple[list[Article], int]:
    """Return usable entries and the number of article pages opened."""
    try:
        parsed = parse_feed(feed.url)
    except Exception as exc:  # noqa: BLE001 - one feed must not kill the run
        log.warning('feed %s blew up: %s', feed.name, exc)
        return [], 0
    if parsed is None:
        return [], 0

    articles = []
    pages_used = 0
    for entry in parsed.entries:
        link = entry.get('link')
        if not link:
            continue

        published = entry_published(entry)
        if is_stale(published):
            continue

        text = entry_text(entry)

        if (
            feed.needs_page_fetch
            and page_budget > 0
            and word_count(text) < TEASER_WORD_THRESHOLD
        ):
            page_budget -= 1
            pages_used += 1
            page_text = fetch_page_text(link)
            if word_count(page_text) > word_count(text):
                text = page_text

        articles.append(
            Article(
                url_hash=url_hash(link),
                url=link,
                title=strip_html(entry.get('title', '')) or '(untitled)',
                source=feed.name,
                bucket=feed.bucket,
                read_minutes=estimate_minutes(text),
                body_excerpt=text[:BODY_EXCERPT_CHARS],
                published_at=published,
            )
        )

    log.info('%s: %d articles, %d pages opened', feed.name,
             len(articles), pages_used)
    return articles, pages_used


def fetch_all(
    feeds: Optional[Iterable[Feed]] = None,
    today: Optional[date] = None,
    max_page_fetches: int = MAX_PAGE_FETCHES_PER_RUN,
    rotate: bool = True,
) -> list[Article]:
    """Fetch a rotation group, or all feeds, with a shared page budget."""
    todays_feeds = (
        feeds_for_today(feeds, today)
        if rotate
        else list(FEEDS if feeds is None else feeds)
    )
    log.info('fetching %d feeds', len(todays_feeds))

    budget = max_page_fetches
    seen: set[str] = set()
    articles: list[Article] = []

    for feed in todays_feeds:
        found, pages_used = articles_from_feed(feed, page_budget=budget)
        budget = max(0, budget - pages_used)
        for article in found:
            if article.url_hash in seen:
                continue
            seen.add(article.url_hash)
            articles.append(article)

    return articles
