"""Fetcher tests with all HTTP calls stubbed."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src import fetcher
from src.config import MAX_ARTICLE_AGE_DAYS, TEASER_WORD_THRESHOLD, Feed


def test_normalize_lowercases_scheme_and_host():
    assert (
        fetcher.normalize_url('HTTPS://Example.COM/Path')
        == 'https://example.com/Path'
    )


def test_normalize_preserves_path_case():
    a = fetcher.normalize_url('https://example.com/Foo')
    b = fetcher.normalize_url('https://example.com/foo')
    assert a != b


def test_normalize_strips_fragment():
    assert (
        fetcher.normalize_url('https://example.com/a#section-2')
        == 'https://example.com/a'
    )


def test_normalize_strips_trailing_slash():
    assert (
        fetcher.normalize_url('https://example.com/a/')
        == 'https://example.com/a'
    )


def test_normalize_keeps_bare_root_consistent():
    assert fetcher.normalize_url('https://example.com/') == 'https://example.com'


def test_normalize_drops_tracking_params_keeps_real_ones():
    got = fetcher.normalize_url(
        'https://example.com/a?utm_source=twitter&id=7&ref=hn&ref_src=x'
    )
    assert got == 'https://example.com/a?id=7'


def test_same_article_shared_two_ways_hashes_the_same():
    plain = fetcher.url_hash('https://example.com/story')
    tracked = fetcher.url_hash(
        'HTTPS://Example.com/story/?utm_campaign=newsletter#top'
    )
    assert plain == tracked


def test_different_articles_hash_differently():
    assert fetcher.url_hash('https://example.com/a') != fetcher.url_hash(
        'https://example.com/b'
    )


def test_url_hash_is_32_hex_chars():
    got = fetcher.url_hash('https://example.com/a')
    assert len(got) == 32
    assert all(c in '0123456789abcdef' for c in got)


def test_strip_html_removes_tags():
    assert fetcher.strip_html('<p>hello <b>world</b></p>') == 'hello world'


def test_strip_html_unescapes_after_stripping():
    assert fetcher.strip_html('<p>use &lt;p&gt; tags</p>') == 'use <p> tags'


def test_strip_html_handles_empty():
    assert fetcher.strip_html('') == ''


def test_extract_body_drops_scripts_and_nav():
    page = """
    <html><head><style>body{color:red}</style></head>
    <body>
      <nav>Home About Contact Subscribe</nav>
      <script>var tracking = 'analytics junk';</script>
      <p>The actual article text.</p>
      <footer>Copyright notice</footer>
    </body></html>
    """
    got = fetcher.extract_body(page)
    assert 'actual article text' in got
    assert 'analytics' not in got
    assert 'Subscribe' not in got
    assert 'Copyright' not in got


def test_extract_body_prefers_article_element():
    page = """
    <body>
      <div>sidebar clutter everywhere</div>
      <article><p>The real body.</p></article>
      <div>more clutter</div>
    </body>
    """
    got = fetcher.extract_body(page)
    assert got == 'The real body.'


def test_extract_body_keeps_paragraphs_and_drops_toolbars():
    """Ignore share controls inside the article element."""
    prose = '<p>' + ('sentence about biology ' * 60) + '</p>'
    page = f"""
    <article>
      <div>Read Later Share Copied! Comments Read Later Q&amp;A</div>
      {prose}
      <div>Related stories you might enjoy</div>
    </article>
    """
    got = fetcher.extract_body(page)
    assert got.startswith('sentence about biology')
    assert 'Read Later' not in got
    assert 'Related stories' not in got


def test_extract_body_falls_back_when_paragraphs_are_thin():
    page = '<article><div>' + ('div laid out body ' * 60) + '</div></article>'
    got = fetcher.extract_body(page)
    assert 'div laid out body' in got


def _iso(days_ago: int) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat(timespec='microseconds')


def test_recent_article_is_not_stale():
    assert fetcher.is_stale(_iso(3)) is False


def test_old_article_is_stale():
    assert fetcher.is_stale(_iso(MAX_ARTICLE_AGE_DAYS + 5)) is True


def test_undated_article_is_not_stale():
    assert fetcher.is_stale(None) is False


def test_unparseable_date_is_not_stale():
    assert fetcher.is_stale('not a date') is False


def _fake_feeds(n: int) -> list[Feed]:
    return [Feed(f'F{i}', f'https://f{i}.example/feed', 'curious', True)
            for i in range(n)]


def test_rotation_returns_a_subset():
    feeds = _fake_feeds(36)
    todays = fetcher.feeds_for_today(feeds, date(2026, 8, 20))
    assert 0 < len(todays) < len(feeds)


def test_rotation_covers_every_feed_across_the_cycle():
    feeds = _fake_feeds(35)
    seen = set()
    start = date(2026, 8, 20)
    for offset in range(fetcher.FEED_GROUPS):
        for f in fetcher.feeds_for_today(feeds, start + timedelta(days=offset)):
            seen.add(f.name)
    assert seen == {f.name for f in feeds}


def test_rotation_is_stateless_and_stable_within_a_day():
    feeds = _fake_feeds(35)
    day = date(2026, 8, 20)
    first = fetcher.feeds_for_today(feeds, day)
    second = fetcher.feeds_for_today(feeds, day)
    assert [f.name for f in first] == [f.name for f in second]


def test_rotation_groups_are_disjoint():
    feeds = _fake_feeds(35)
    start = date(2026, 8, 20)
    groups = [
        {f.name for f in fetcher.feeds_for_today(feeds, start + timedelta(days=d))}
        for d in range(fetcher.FEED_GROUPS)
    ]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            assert not groups[i] & groups[j]


class _FakeParsed:
    """Stand-in for feedparser's return value."""

    def __init__(self, entries, bozo=0):
        self.entries = entries
        self.bozo = bozo


def _entry(**kw):
    """A feedparser entry is dict-like with .get()."""
    base = {
        'link': 'https://example.com/a',
        'title': 'A Title',
        'summary': 'word ' * 1500,
        'published_parsed': (datetime.now(timezone.utc)).timetuple(),
    }
    base.update(kw)
    return base


def test_bozo_feed_still_yields_entries(monkeypatch):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([_entry()], bozo=1),
    )
    feed = Feed('LRB', 'https://lrb.example/feed', 'essays', True)
    articles, _ = fetcher.articles_from_feed(feed)
    assert len(articles) == 1


def test_empty_feed_returns_nothing(monkeypatch):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse', lambda raw: _FakeParsed([])
    )
    feed = Feed('Dead', 'https://dead.example/feed', 'curious', True)
    articles, _ = fetcher.articles_from_feed(feed)
    assert articles == []


def test_broken_feed_does_not_crash_the_run(monkeypatch):
    def explode(*a, **k):
        raise RuntimeError('feed is on fire')

    monkeypatch.setattr(fetcher, 'parse_feed', explode)
    feed = Feed('Broken', 'https://broken.example/feed', 'curious', True)
    articles, pages = fetcher.articles_from_feed(feed)
    assert articles == [] and pages == 0


def test_stale_entries_dropped_at_insert(monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(days=MAX_ARTICLE_AGE_DAYS + 10)
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([
            _entry(link='https://example.com/old',
                   published_parsed=old.timetuple()),
            _entry(link='https://example.com/new'),
        ]),
    )
    feed = Feed('Mixed', 'https://mixed.example/feed', 'curious', True)
    articles, _ = fetcher.articles_from_feed(feed)
    assert [a.url for a in articles] == ['https://example.com/new']


def test_entry_without_link_is_skipped(monkeypatch):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([_entry(link=None)]),
    )
    feed = Feed('NoLink', 'https://nolink.example/feed', 'curious', True)
    articles, _ = fetcher.articles_from_feed(feed)
    assert articles == []


def test_content_preferred_over_summary():
    entry = {
        'content': [{'value': '<p>the full body</p>'}],
        'summary': 'the teaser',
    }
    assert fetcher.entry_text(entry) == 'the full body'


def _teaser_feed_setup(monkeypatch, page_text: str):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([
            _entry(link='https://example.com/teased', summary='a short blurb'),
        ]),
    )
    monkeypatch.setattr(fetcher, 'fetch_page_text', lambda url: page_text)


def test_teaser_feed_opens_the_page_for_real_body(monkeypatch):
    _teaser_feed_setup(monkeypatch, 'word ' * 2000)
    feed = Feed('Aeon', 'https://aeon.example/feed', 'essays', True,
                needs_page_fetch=True)
    articles, pages = fetcher.articles_from_feed(feed, page_budget=5)
    assert pages == 1
    assert articles[0].read_minutes >= 5


def test_non_teaser_feed_never_opens_a_page(monkeypatch):
    _teaser_feed_setup(monkeypatch, 'word ' * 2000)
    feed = Feed('Sapiens', 'https://sapiens.example/feed', 'curious', True,
                needs_page_fetch=False)
    articles, pages = fetcher.articles_from_feed(feed, page_budget=5)
    assert pages == 0
    assert articles[0].read_minutes == 1


def test_page_fetch_budget_of_zero_skips_the_page(monkeypatch):
    _teaser_feed_setup(monkeypatch, 'word ' * 2000)
    feed = Feed('Aeon', 'https://aeon.example/feed', 'essays', True,
                needs_page_fetch=True)
    articles, pages = fetcher.articles_from_feed(feed, page_budget=0)
    assert pages == 0
    assert articles[0].read_minutes == 1


def test_long_feed_text_skips_the_page_fetch(monkeypatch):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([
            _entry(summary='word ' * (TEASER_WORD_THRESHOLD + 50)),
        ]),
    )
    monkeypatch.setattr(fetcher, 'fetch_page_text',
                        lambda url: pytest.fail('should not fetch page'))
    feed = Feed('Aeon', 'https://aeon.example/feed', 'essays', True,
                needs_page_fetch=True)
    articles, pages = fetcher.articles_from_feed(feed, page_budget=5)
    assert pages == 0


def test_failed_page_fetch_keeps_the_feed_text(monkeypatch):
    _teaser_feed_setup(monkeypatch, '')
    feed = Feed('Aeon', 'https://aeon.example/feed', 'essays', True,
                needs_page_fetch=True)
    articles, _ = fetcher.articles_from_feed(feed, page_budget=5)
    assert articles[0].body_excerpt == 'a short blurb'


def test_fetch_all_dedupes_across_feeds(monkeypatch):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([_entry(link='https://shared.example/story')]),
    )
    feeds = [
        Feed('A', 'https://a.example/feed', 'curious', True),
        Feed('B', 'https://b.example/feed', 'curious', True),
        Feed('C', 'https://c.example/feed', 'curious', True),
    ]
    articles = fetcher.fetch_all(feeds=feeds, rotate=False)
    assert len(articles) == 1


def test_fetch_all_rotates_by_default(monkeypatch):
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([_entry()]),
    )
    feeds = _fake_feeds(9)
    polled = []
    real = fetcher.articles_from_feed
    monkeypatch.setattr(
        fetcher, 'articles_from_feed',
        lambda f, page_budget=0: (polled.append(f.name), real(f, page_budget))[1],
    )
    fetcher.fetch_all(feeds=feeds, today=date(2026, 8, 20))
    assert len(polled) == 3


def test_rotate_false_polls_every_feed(monkeypatch):
    """Disabling rotation must poll every supplied feed."""
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([_entry()]),
    )
    feeds = _fake_feeds(9)
    polled = []
    real = fetcher.articles_from_feed
    monkeypatch.setattr(
        fetcher, 'articles_from_feed',
        lambda f, page_budget=0: (polled.append(f.name), real(f, page_budget))[1],
    )
    fetcher.fetch_all(feeds=feeds, rotate=False)
    assert len(polled) == 9


def test_fetch_all_budget_is_shared_across_feeds(monkeypatch):
    """Share the page cap across the entire run."""
    monkeypatch.setattr(fetcher, '_get', lambda *a, **k: b'<rss/>')
    monkeypatch.setattr(
        fetcher.feedparser, 'parse',
        lambda raw: _FakeParsed([
            _entry(link=f'https://x.example/{i}', summary='blurb')
            for i in range(10)
        ]),
    )
    calls = []
    monkeypatch.setattr(
        fetcher, 'fetch_page_text',
        lambda url: (calls.append(url), 'word ' * 2000)[1],
    )
    feeds = [
        Feed(f'T{i}', f'https://t{i}.example/feed', 'essays', True,
             needs_page_fetch=True)
        for i in range(3)
    ]
    fetcher.fetch_all(feeds=feeds, max_page_fetches=12, rotate=False)
    assert len(calls) == 12
