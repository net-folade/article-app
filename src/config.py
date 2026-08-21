"""Picker, fetcher, and feed configuration."""

from dataclasses import dataclass

WORDS_PER_MINUTE = 238

WILDCARD_PROBABILITY = 0.30

# Core weights exclude the separately weighted wildcard pool and are validated below.
CORE_BUCKET_WEIGHTS = {
    "ai": 0.10,
    "tech": 0.10,
    "cloud": 0.10,
    "finance": 0.20,
    "lifestyle": 0.10,
    "stories": 0.40,
}

# This is one combined candidate pool; labels do not assign weights.
WILDCARD_BUCKETS = ["essays", "wildcard", "curious"]

MIN_READ_MINUTES = 5
MAX_READ_MINUTES = 15

FRESHNESS_DAYS = 7
FALLBACK_FRESHNESS_DAYS = 14

PER_SOURCE_MONTHLY_CAP = 3
SOURCE_CAP_WINDOW_DAYS = 30

FETCH_TIMEOUT_SECONDS = 10

USER_AGENT = "daily-article-surprise/1.0 (personal RSS reader)"

# Used only as a fallback for publishers that reject non-browser agents.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Date-based rotation polls each feed roughly every FEED_GROUPS days.
FEED_GROUPS = 3

# Short entries from teaser feeds trigger an article-page fetch.
TEASER_WORD_THRESHOLD = 200

# Bound page opens so a run degrades gracefully instead of timing out.
MAX_PAGE_FETCHES_PER_RUN = 25

# This backlog guard retains slow-publishing evergreen feeds while excluding dormant ones.
MAX_ARTICLE_AGE_DAYS = 45

# Store only enough body text for a notification preview.
BODY_EXCERPT_CHARS = 400


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    bucket: str
    verified: bool = False
    # True when read time must be calculated from the article page.
    needs_page_fetch: bool = False


# Verified and measured with `make inspect-feeds` on 2026-08-20.
FEEDS = [
    Feed("Quanta", "https://www.quantamagazine.org/feed/", "curious", True, needs_page_fetch=True),
    Feed("Psyche", "https://psyche.co/feed", "curious", True, needs_page_fetch=True),
    Feed("Strong Towns", "https://www.strongtowns.org/journal?format=rss", "curious", True, needs_page_fetch=True),
    Feed("Atlas Obscura", "https://www.atlasobscura.com/feeds/latest", "curious", True, needs_page_fetch=True),
    Feed("Nautilus", "https://nautil.us/feed/", "curious", True, needs_page_fetch=True),
    Feed("Undark", "https://undark.org/feed/", "curious", True, needs_page_fetch=True),
    Feed("JSTOR Daily", "https://daily.jstor.org/feed/", "curious", True),
    Feed("Common Edge", "https://commonedge.org/feed/", "curious", True),
    Feed("Comment Magazine", "https://comment.org/feed/", "curious", True, needs_page_fetch=True),

    Feed("Aeon", "https://aeon.co/feed.rss", "essays", True, needs_page_fetch=True),
    Feed("Paris Review", "https://www.theparisreview.org/blog/feed/", "essays", True),
    Feed("LRB", "https://www.lrb.co.uk/feeds/rss", "essays", True, needs_page_fetch=True),
    Feed("The New Yorker", "https://www.newyorker.com/feed/everything", "essays", True, needs_page_fetch=True),
    Feed("Public Books", "https://www.publicbooks.org/feed/", "essays", True, needs_page_fetch=True),

    Feed("Damn Interesting", "https://www.damninteresting.com/feed/", "wildcard", True, needs_page_fetch=True),
    Feed("Eater", "https://www.eater.com/rss/index.xml", "wildcard", True),
    Feed("Defector", "https://defector.com/feed", "wildcard", True, needs_page_fetch=True),

    Feed("The Atlantic", "https://www.theatlantic.com/feed/all/", "stories", True),
    Feed("Narratively", "https://narratively.com/feed/", "stories", True),
    Feed("ProPublica", "https://www.propublica.org/feeds/propublica/main", "stories", True),

    Feed("Import AI", "https://importai.substack.com/feed", "ai", True),
    Feed("One Useful Thing", "https://www.oneusefulthing.org/feed", "ai", True),
    Feed("Simon Willison", "https://simonwillison.net/atom/everything/", "ai", True, needs_page_fetch=True),

    Feed("Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed", "tech", True),
    Feed("Julia Evans", "https://jvns.ca/atom.xml", "tech", True),

    Feed("AWS Architecture", "https://aws.amazon.com/blogs/architecture/feed/", "cloud", True),
    Feed("The New Stack", "https://thenewstack.io/feed/", "cloud", True),
    Feed("CNCF", "https://www.cncf.io/feed/", "cloud", True),

    Feed("Of Dollars And Data", "https://ofdollarsanddata.com/feed/", "finance", True),
    Feed("Noahpinion", "https://www.noahpinion.blog/feed", "finance", True),
    Feed("Construction Physics", "https://www.construction-physics.com/feed", "finance", True),

    Feed("Outside", "https://www.outsideonline.com/feed/", "lifestyle", True),
    Feed("GQ", "https://www.gq.com/feed/rss", "lifestyle", True, needs_page_fetch=True),
]


def _validate() -> None:
    total = sum(CORE_BUCKET_WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"CORE_BUCKET_WEIGHTS must sum to 1.0, got {total}")
    if not 0.0 <= WILDCARD_PROBABILITY <= 1.0:
        raise ValueError("WILDCARD_PROBABILITY must be between 0 and 1")
    if MIN_READ_MINUTES > MAX_READ_MINUTES:
        raise ValueError("MIN_READ_MINUTES cannot exceed MAX_READ_MINUTES")

    overlap = set(CORE_BUCKET_WEIGHTS) & set(WILDCARD_BUCKETS)
    if overlap:
        raise ValueError(f"Buckets cannot be both core and wildcard: {overlap}")

    known = set(CORE_BUCKET_WEIGHTS) | set(WILDCARD_BUCKETS)
    unknown = {f.bucket for f in FEEDS} - known
    if unknown:
        raise ValueError(f"FEEDS reference unknown buckets: {unknown}")

    urls = [f.url for f in FEEDS]
    if len(urls) != len(set(urls)):
        raise ValueError("Duplicate feed URLs in FEEDS")


_validate()
