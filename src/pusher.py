"""Format and send the daily notification through ntfy."""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from src.config import FETCH_TIMEOUT_SECONDS, USER_AGENT
from src.db import Article

log = logging.getLogger(__name__)

DEFAULT_SERVER = 'https://ntfy.sh'

# ntfy renders bucket tags as emoji.
BUCKET_TAGS = {
    'ai': 'robot',
    'tech': 'gear',
    'cloud': 'cloud',
    'finance': 'moneybag',
    'lifestyle': 'sparkles',
    'stories': 'book',
    'essays': 'scroll',
    'wildcard': 'game_die',
    'curious': 'mag',
}
UNKNOWN_TAG = 'newspaper'

# Default priority avoids overriding Do Not Disturb.
DEFAULT_PRIORITY = 3

EXCERPT_CHARS = 200


class PushError(RuntimeError):
    """Raised when the notification could not be delivered."""


def encode_header(value: str) -> str:
    """Encode non-ASCII header values with RFC 2047 for requests and ntfy."""
    if value.isascii():
        return value
    encoded = base64.b64encode(value.encode('utf-8')).decode('ascii')
    return f'=?UTF-8?B?{encoded}?='


def encode_url_header(url: str) -> str:
    """Percent-encode a URL while preserving it as an ntfy Click link."""
    if url.isascii():
        return url
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        parts.netloc.encode('idna').decode('ascii')
        if not parts.netloc.isascii() else parts.netloc,
        quote(parts.path, safe='/%'),
        quote(parts.query, safe='=&%'),
        quote(parts.fragment, safe='%'),
    ))


def _excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Trim to `limit` chars on a word boundary, with an ellipsis."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(' ', 1)[0].rstrip(' ,.;:—-')
    return f'{clipped}…'


def format_notification(article: Article) -> dict:
    """Format an article as an ntfy payload."""
    tag = BUCKET_TAGS.get(article.bucket, UNKNOWN_TAG)
    excerpt = _excerpt(article.body_excerpt)

    body = article.title
    if excerpt:
        body = f'{article.title}\n\n{excerpt}'

    return {
        'title': f'{article.source} · {article.read_minutes} min read',
        'body': body,
        'tags': tag,
        'click': article.url,
        'priority': DEFAULT_PRIORITY,
    }


def push_article(article: Article, topic: Optional[str] = None,
                 server: Optional[str] = None) -> dict:
    """Post to ntfy and return the formatted payload."""
    topic = topic or os.environ.get('NTFY_TOPIC')
    server = (server or os.environ.get('NTFY_SERVER') or DEFAULT_SERVER).rstrip('/')

    if not topic:
        raise PushError('NTFY_TOPIC is not set')

    payload = format_notification(article)

    try:
        response = requests.post(
            f'{server}/{topic}',
            data=payload['body'].encode('utf-8'),
            headers={
                'Title': encode_header(payload['title']),
                'Tags': encode_header(payload['tags']),
                'Click': encode_url_header(payload['click']),
                'Priority': str(payload['priority']),
                'User-Agent': USER_AGENT,
            },
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PushError(f'ntfy request failed: {exc}') from exc

    if response.status_code != 200:
        raise PushError(f'ntfy returned HTTP {response.status_code}')

    log.info('pushed %s (%s)', article.title, article.url_hash)
    return payload
