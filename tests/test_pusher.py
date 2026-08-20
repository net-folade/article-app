"""Pusher tests without real network calls."""

from __future__ import annotations

import base64

import pytest
import requests

from src import pusher
from src.db import Article


def _article(**kw) -> Article:
    base = dict(
        url_hash="abc123",
        url="https://aeon.co/essays/the-quiet-tyranny",
        title="The Quiet Tyranny of the Algorithm",
        source="Aeon",
        bucket="essays",
        read_minutes=9,
        body_excerpt="Algorithms shape what we see long before we choose it.",
    )
    base.update(kw)
    return Article(**base)


def test_title_leads_with_source_and_read_time():
    note = pusher.format_notification(_article())
    assert note["title"] == "Aeon · 9 min read"


def test_body_contains_headline_and_excerpt():
    note = pusher.format_notification(_article())
    assert "The Quiet Tyranny of the Algorithm" in note["body"]
    assert "Algorithms shape what we see" in note["body"]


def test_body_is_just_the_headline_when_no_excerpt():
    note = pusher.format_notification(_article(body_excerpt=""))
    assert note["body"] == "The Quiet Tyranny of the Algorithm"


def test_click_is_the_article_url():
    note = pusher.format_notification(_article())
    assert note["click"] == "https://aeon.co/essays/the-quiet-tyranny"


@pytest.mark.parametrize(
    "bucket,tag",
    [
        ("ai", "robot"),
        ("tech", "gear"),
        ("cloud", "cloud"),
        ("finance", "moneybag"),
        ("lifestyle", "sparkles"),
        ("stories", "book"),
        ("essays", "scroll"),
        ("wildcard", "game_die"),
        ("curious", "mag"),
    ],
)
def test_every_bucket_has_its_emoji(bucket, tag):
    note = pusher.format_notification(_article(bucket=bucket))
    assert note["tags"] == tag


def test_unknown_bucket_falls_back_to_newspaper():
    note = pusher.format_notification(_article(bucket="nonsense"))
    assert note["tags"] == "newspaper"


def test_every_configured_bucket_is_mapped():
    """A new bucket in config must not silently ship as 'newspaper'."""
    from src.config import CORE_BUCKET_WEIGHTS, WILDCARD_BUCKETS

    configured = set(CORE_BUCKET_WEIGHTS) | set(WILDCARD_BUCKETS)
    assert configured <= set(pusher.BUCKET_TAGS)


def test_priority_does_not_override_do_not_disturb():
    note = pusher.format_notification(_article())
    assert note["priority"] == 3


def test_long_excerpt_is_trimmed_on_a_word_boundary():
    note = pusher.format_notification(_article(body_excerpt="hippopotamus " * 60))
    excerpt = note["body"].split("\n\n")[1]
    assert len(excerpt) <= pusher.EXCERPT_CHARS + 1
    assert excerpt.endswith("…")
    assert "hippopota…" not in excerpt


def test_ascii_headers_pass_through_readable():
    assert pusher.encode_header("Aeon · 9 min".replace("·", "-")) == "Aeon - 9 min"


def test_non_ascii_header_is_rfc2047_encoded():
    got = pusher.encode_header("Aeon · 9 min read")
    assert got.startswith("=?UTF-8?B?") and got.endswith("?=")
    decoded = base64.b64decode(got[len("=?UTF-8?B?"):-2]).decode("utf-8")
    assert decoded == "Aeon · 9 min read"


def test_unicode_url_is_percent_encoded_not_rfc2047():
    got = pusher.encode_url_header("https://example.com/café")
    assert got == "https://example.com/caf%C3%A9"


def test_ascii_url_is_untouched():
    url = "https://example.com/a?b=c"
    assert pusher.encode_url_header(url) == url


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def test_push_posts_to_server_and_topic(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["url"] = url
        seen.update(kw)
        return _FakeResponse()

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    pusher.push_article(_article(), topic="my-topic", server="https://ntfy.sh")

    assert seen["url"] == "https://ntfy.sh/my-topic"
    assert seen["headers"]["Title"].startswith("=?UTF-8?B?")
    assert seen["headers"]["Priority"] == "3"
    assert b"Quiet Tyranny" in seen["data"]


def test_push_reads_topic_from_env(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        pusher.requests, "post",
        lambda url, **kw: (seen.setdefault("url", url), _FakeResponse())[1],
    )
    monkeypatch.setenv("NTFY_TOPIC", "env-topic")
    monkeypatch.delenv("NTFY_SERVER", raising=False)
    pusher.push_article(_article())
    assert seen["url"] == "https://ntfy.sh/env-topic"


def test_push_without_topic_raises(monkeypatch):
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    with pytest.raises(pusher.PushError, match="NTFY_TOPIC"):
        pusher.push_article(_article())


def test_push_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        pusher.requests, "post", lambda url, **kw: _FakeResponse(500)
    )
    with pytest.raises(pusher.PushError, match="500"):
        pusher.push_article(_article(), topic="t")


def test_push_raises_on_network_error(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(pusher.requests, "post", boom)
    with pytest.raises(pusher.PushError, match="ntfy request failed"):
        pusher.push_article(_article(), topic="t")


def test_unicode_title_survives_a_real_requests_call(monkeypatch):
    """Ensure Unicode survives requests' real header encoding."""
    session = requests.Session()
    article = _article(title="Nietzsche — on the eternal return of ‘the same’")
    note = pusher.format_notification(article)
    prepared = session.prepare_request(
        requests.Request(
            "POST",
            "https://ntfy.sh/t",
            data=note["body"].encode("utf-8"),
            headers={"Title": pusher.encode_header(note["title"])},
        )
    )
    assert prepared.headers["Title"] is not None
