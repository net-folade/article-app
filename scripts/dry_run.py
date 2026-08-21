"""Run the local pipeline with temporary state and a printed notification."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import FEEDS  # noqa: E402
from src.db import s3_backed_db  # noqa: E402
from src.fetcher import fetch_all, feeds_for_today  # noqa: E402
from src.picker import pick_article  # noqa: E402
from src.pusher import format_notification  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--all-feeds', action='store_true',
                    help="fetch every feed, not just today's rotation group")
    ap.add_argument('--verbose', action='store_true',
                    help='show fetcher logging')
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(levelname)s %(name)s: %(message)s',
    )

    todays = FEEDS if args.all_feeds else feeds_for_today()
    print(f'Fetching {len(todays)} feeds'
          f"{'' if args.all_feeds else f' (rotation group, of {len(FEEDS)})'}…\n")

    with s3_backed_db(bucket=None) as db:
        articles = fetch_all(
            rotate=not args.all_feeds,
            max_page_fetches=120 if args.all_feeds else 25,
        )
        db.upsert_articles(articles)

        print(f'{len(articles)} articles fetched\n')

        in_window = [a for a in articles if 5 <= a.read_minutes <= 15]
        print(f'{len(in_window)} inside the 5-15 minute window\n')

        per_bucket = Counter(a.bucket for a in in_window)
        print('Usable articles per bucket:')
        for bucket, n in sorted(per_bucket.items(), key=lambda x: -x[1]):
            print(f'  {bucket:<10} {n:>3}')
        empty = {a.bucket for a in articles} - set(per_bucket)
        if empty:
            print(f"  (nothing usable from: {', '.join(sorted(empty))})")

        chosen = pick_article(db)
        print(f"\n{'=' * 70}")
        if chosen is None:
            print('Picker returned None — nothing would be sent today.')
            print("That's a valid outcome: anti-repetition and the filters")
            print('agreed there was nothing worth sending.')
            return 0

        note = format_notification(chosen)
        print('WOULD SEND:\n')
        print(f"  Title    {note['title']}")
        print(f"  Tags     {note['tags']}")
        print(f"  Priority {note['priority']}")
        print(f"  Click    {note['click']}")
        print(f'\n  Body:\n')
        for line in note['body'].splitlines():
            print(f'    {line}')
        print(f"\n{'=' * 70}")
        print(f'(bucket={chosen.bucket}, {chosen.read_minutes} min, '
              f'not marked sent — this is a dry run)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
