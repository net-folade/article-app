"""Report picker results from state.db in S3 without changing it."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (  # noqa: E402
    CORE_BUCKET_WEIGHTS,
    PER_SOURCE_MONTHLY_CAP,
    WILDCARD_BUCKETS,
    WILDCARD_PROBABILITY,
)


def download(bucket: str, key: str) -> str:
    """Download state.db to a temporary file."""
    import boto3

    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    boto3.client('s3').download_file(bucket, key, path)
    return path


def iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec='microseconds'
    )


def bar(fraction: float, width: int = 24) -> str:
    filled = int(round(fraction * width))
    return '#' * filled + '.' * (width - filled)


def report(path: str, window_days: int) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cutoff = iso_days_ago(window_days)

    total = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
    sent_total = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE status = 'sent'"
    ).fetchone()[0]
    print(f'\n{total} articles stored, {sent_total} sent all time\n')

    sent = conn.execute(
        'SELECT bucket, source, title, read_minutes, sent_at FROM articles '
        "WHERE status = 'sent' AND sent_at >= ? ORDER BY sent_at DESC",
        (cutoff,),
    ).fetchall()

    if not sent:
        print(f'Nothing sent in the last {window_days} days.')
        return

    n = len(sent)
    print(f'Last {window_days} days: {n} sends\n')

    # Compare the wildcard rate with its 30% target.
    wild = sum(1 for r in sent if r['bucket'] in WILDCARD_BUCKETS)
    print(
        f'  wildcard rate   {wild / n:5.0%}  '
        f'(target {WILDCARD_PROBABILITY:.0%}, {wild}/{n})\n'
    )

    print('  bucket           actual  target')
    counts = Counter(r['bucket'] for r in sent)
    for bucket in list(CORE_BUCKET_WEIGHTS) + list(WILDCARD_BUCKETS):
        actual = counts.get(bucket, 0) / n
        target = CORE_BUCKET_WEIGHTS.get(bucket)
        # Wildcard buckets have no individual targets.
        target_text = f'{target:6.0%}' if target is not None else '     -'
        print(f'  {bucket:<15} {actual:6.0%}  {target_text}  {bar(actual)}')

    print(f'\n  source                       sends (cap {PER_SOURCE_MONTHLY_CAP})')
    for source, count in Counter(r['source'] for r in sent).most_common():
        flag = '  AT CAP' if count >= PER_SOURCE_MONTHLY_CAP else ''
        print(f'  {source:<28} {count:>5}{flag}')

    minutes = [r['read_minutes'] for r in sent]
    minutes.sort()
    median = minutes[len(minutes) // 2]
    print(
        f'\n  read time       min {minutes[0]}  median {median}  max {minutes[-1]}'
    )

    print('\n  most recent')
    for row in sent[:10]:
        day = row['sent_at'][:10]
        title = row['title'][:52]
        print(f"  {day}  {row['bucket']:<10} {row['read_minutes']:>2}m  {title}")

    unsent = conn.execute(
        'SELECT bucket, COUNT(*) AS n FROM articles '
        "WHERE status != 'sent' GROUP BY bucket ORDER BY n DESC"
    ).fetchall()
    print('\n  unsent pool')
    for row in unsent:
        print(f"  {row['bucket']:<15} {row['n']:>5}")

    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--bucket',
        default=os.environ.get('S3_BUCKET'),
        help='State bucket name; defaults to $S3_BUCKET',
    )
    parser.add_argument('--key', default='state.db')
    parser.add_argument(
        '--days', type=int, default=30, help='Reporting window (default 30)'
    )
    parser.add_argument(
        '--local', help='Read a local .db instead of downloading from S3'
    )
    args = parser.parse_args()

    if args.local:
        report(args.local, args.days)
        return 0

    if not args.bucket:
        parser.error('--bucket is required (or set S3_BUCKET)')

    path = download(args.bucket, args.key)
    try:
        report(path, args.days)
    finally:
        os.remove(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
