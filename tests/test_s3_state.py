"""Test S3-backed database storage."""

import os
import tempfile

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.db import Article, s3_backed_db, utcnow

BUCKET = 'article-app-test-state'
KEY = 'state.db'


@pytest.fixture
def s3():
    """Create an empty test bucket."""
    with mock_aws():
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket=BUCKET)
        yield client


def make_article(url_hash='h1'):
    return Article(
        url_hash=url_hash,
        url=f'https://example.com/{url_hash}',
        title=f'Article {url_hash}',
        source='Aeon',
        bucket='essays',
        read_minutes=8,
        fetched_at=utcnow(),
    )


def test_first_run_creates_the_object_when_none_exists(s3):
    """Allow the first run without state.db."""
    with s3_backed_db(bucket=BUCKET, key=KEY) as db:
        db.upsert_articles([make_article()])

    head = s3.head_object(Bucket=BUCKET, Key=KEY)
    assert head['ContentLength'] > 0


def test_state_survives_a_round_trip(s3):
    """Load data saved by an earlier run."""
    with s3_backed_db(bucket=BUCKET, key=KEY) as db:
        db.upsert_articles([make_article('first')])

    with s3_backed_db(bucket=BUCKET, key=KEY) as db:
        db.upsert_articles([make_article('second')])
        hashes = {a.url_hash for a in db.unsent_articles(['essays'], 1, 60, 30)}

    assert hashes == {'first', 'second'}


def test_sent_marks_persist_across_runs(s3):
    """Keep send times after upload."""
    with s3_backed_db(bucket=BUCKET, key=KEY) as db:
        db.upsert_articles([make_article('h1')])
        db.mark_sent('h1')

    with s3_backed_db(bucket=BUCKET, key=KEY) as db:
        assert db.last_sent_bucket() == 'essays'
        assert db.unsent_articles(['essays'], 1, 60, 30) == []


def test_failed_run_does_not_overwrite_good_history(s3):
    """Keep saved state when a run fails."""
    with s3_backed_db(bucket=BUCKET, key=KEY) as db:
        db.upsert_articles([make_article('keeper')])

    good = s3.get_object(Bucket=BUCKET, Key=KEY)['Body'].read()

    with pytest.raises(RuntimeError):
        with s3_backed_db(bucket=BUCKET, key=KEY) as db:
            db.upsert_articles([make_article('doomed')])
            raise RuntimeError('run blew up after the fetch')

    assert s3.get_object(Bucket=BUCKET, Key=KEY)['Body'].read() == good


def test_missing_bucket_raises_rather_than_starting_fresh(s3):
    """Raise errors other than a missing state file."""
    with pytest.raises(ClientError):
        with s3_backed_db(bucket='no-such-bucket-here', key=KEY):
            pass


def test_no_bucket_still_runs_purely_locally():
    """Avoid AWS when no bucket is set."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        with s3_backed_db(bucket=None, local_path=path) as db:
            db.upsert_articles([make_article()])
        assert os.path.getsize(path) > 0
    finally:
        os.remove(path)
