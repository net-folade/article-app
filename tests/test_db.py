import os
import tempfile

import pytest

from src.db import (
    Article,
    ArticleDB,
    _download_state,
    days_ago,
    s3_backed_db,
    utcnow,
)


@pytest.fixture
def db():
    """Yield the same file-backed SQLite mechanism used at runtime."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    database = ArticleDB(path)
    yield database
    database.close()
    os.remove(path)


def make_article(url_hash='h1', source='Aeon', bucket='essays',
                 read_minutes=8, fetched_at=None, **kw):
    return Article(
        url_hash=url_hash,
        url=f'https://example.com/{url_hash}',
        title=f'Article {url_hash}',
        source=source,
        bucket=bucket,
        read_minutes=read_minutes,
        fetched_at=fetched_at or utcnow(),
        **kw,
    )


def test_upsert_inserts_new_articles(db):
    assert db.upsert_articles([make_article('a'), make_article('b')]) == 2


def test_upsert_dedupes_by_url_hash(db):
    db.upsert_articles([make_article('a')])
    assert db.upsert_articles([make_article('a')]) == 0


def test_upsert_does_not_resurrect_sent_articles(db):
    db.upsert_articles([make_article('a')])
    db.mark_sent('a')
    db.upsert_articles([make_article('a')])
    assert db.unsent_articles(['essays'], 5, 15, 7) == []


def test_upsert_empty_list_is_noop(db):
    assert db.upsert_articles([]) == 0


def test_unsent_filters_by_bucket(db):
    db.upsert_articles([
        make_article('a', bucket='ai'),
        make_article('b', bucket='finance'),
    ])
    found = db.unsent_articles(['ai'], 5, 15, 7)
    assert [a.url_hash for a in found] == ['a']


def test_unsent_filters_by_read_time(db):
    db.upsert_articles([
        make_article('short', read_minutes=2),
        make_article('good', read_minutes=8),
        make_article('long', read_minutes=40),
    ])
    found = db.unsent_articles(['essays'], 5, 15, 7)
    assert [a.url_hash for a in found] == ['good']


def test_unsent_filters_by_freshness(db):
    db.upsert_articles([
        make_article('fresh', fetched_at=days_ago(2)),
        make_article('stale', fetched_at=days_ago(20)),
    ])
    found = db.unsent_articles(['essays'], 5, 15, 7)
    assert [a.url_hash for a in found] == ['fresh']


def test_unsent_with_no_buckets_returns_empty(db):
    db.upsert_articles([make_article('a')])
    assert db.unsent_articles([], 5, 15, 7) == []


def test_mark_sent_sets_status_and_timestamp(db):
    db.upsert_articles([make_article('a')])
    db.mark_sent('a')
    row = db.conn.execute(
        "SELECT status, sent_at FROM articles WHERE url_hash = 'a'"
    ).fetchone()
    assert row['status'] == 'sent'
    assert row['sent_at'] is not None


def test_last_sent_bucket_returns_none_when_nothing_sent(db):
    db.upsert_articles([make_article('a')])
    assert db.last_sent_bucket() is None


def test_last_sent_bucket_returns_most_recent(db):
    """Microsecond timestamps must order sends made within one second."""
    db.upsert_articles([
        make_article('a', bucket='ai'),
        make_article('b', bucket='finance'),
        make_article('c', bucket='cloud'),
    ])
    db.mark_sent('a')
    db.mark_sent('b')
    db.mark_sent('c')
    assert db.last_sent_bucket() == 'cloud'


def test_source_picks_counts_only_sent(db):
    db.upsert_articles([
        make_article('a', source='Aeon'),
        make_article('b', source='Aeon'),
        make_article('c', source='LRB'),
    ])
    db.mark_sent('a')
    db.mark_sent('b')
    assert db.source_picks_last_30_days() == {'Aeon': 2}


def test_sources_at_cap_identifies_over_limit(db):
    for i in range(3):
        db.upsert_articles([make_article(f'aeon{i}', source='Aeon')])
        db.mark_sent(f'aeon{i}')
    db.upsert_articles([make_article('lrb0', source='LRB')])
    db.mark_sent('lrb0')
    assert db.sources_at_cap() == {'Aeon'}


def test_s3_backed_db_yields_working_db_when_bucket_is_none():
    with s3_backed_db(bucket=None) as database:
        assert database.upsert_articles([make_article('a')]) == 1


class _MissingObjectClient:
    """Stand-in S3 client that fails every download with one error code."""

    def __init__(self, code: str):
        self.code = code

    def download_file(self, bucket, key, local_path):
        from botocore.exceptions import ClientError

        raise ClientError({'Error': {'Code': self.code}}, 'HeadObject')


def test_download_state_returns_false_when_object_missing(tmp_path):
    client = _MissingObjectClient('404')
    assert _download_state(client, 'b', 'state.db', str(tmp_path / 's.db')) is False


def test_download_state_treats_403_as_missing_state(tmp_path):
    # No s3:ListBucket means S3 reports a missing key as 403, not 404.
    client = _MissingObjectClient('403')
    assert _download_state(client, 'b', 'state.db', str(tmp_path / 's.db')) is False


def test_download_state_raises_on_other_errors(tmp_path):
    from botocore.exceptions import ClientError

    client = _MissingObjectClient('InternalError')
    with pytest.raises(ClientError):
        _download_state(client, 'b', 'state.db', str(tmp_path / 's.db'))
