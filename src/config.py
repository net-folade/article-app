"""All tunable constants for the picker live here.

The whole selection algorithm is re-tunable by editing this one file, and
the statistical tests import the same weights the runtime uses.

FEEDS lives here too, so `scripts/validate_feeds.py` and `fetcher.py`
read from one list rather than drifting apart.
"""

from dataclasses import dataclass

# --- Reading time -------------------------------------------------------

WORDS_PER_MINUTE = 238

# --- Picker behaviour ---------------------------------------------------

WILDCARD_PROBABILITY = 0.30

# Must sum to 1.0. Asserted below so a bad edit fails at import time
# rather than silently skewing the distribution for weeks.
#
# These are the CORE path only — the 70% of picks not routed to the
# wildcard pool. "wildcard" must never appear here: it already gets its
# share via WILDCARD_PROBABILITY, and listing it in both tables would
# give it 0.30 + 0.70 * w of all picks.
#
# A weight is a request, not a guarantee. A bucket can only supply
# 3 * (live feeds) picks per 30 days before PER_SOURCE_MONTHLY_CAP
# starves it; past that the picker falls through to another bucket and
# the realised share drifts below the number here. tech is the tight one
# right now — one live feed, so it tops out near 0.14.
CORE_BUCKET_WEIGHTS = {
    "ai": 0.10,
    "tech": 0.10,
    "cloud": 0.10,
    "finance": 0.20,
    "lifestyle": 0.10,
    "stories": 0.40,
}

# Queried as one combined pool, so a bucket's share of wildcard picks is
# proportional to how many candidates it has, not to how many buckets
# there are. The labels exist for tagging and stats, not for weighting.
WILDCARD_BUCKETS = ["essays", "wildcard", "curious"]

# --- Filters ------------------------------------------------------------

MIN_READ_MINUTES = 5
MAX_READ_MINUTES = 15

FRESHNESS_DAYS = 7
FALLBACK_FRESHNESS_DAYS = 14

PER_SOURCE_MONTHLY_CAP = 3
SOURCE_CAP_WINDOW_DAYS = 30

# --- Fetching -----------------------------------------------------------

FETCH_TIMEOUT_SECONDS = 10

USER_AGENT = "daily-article-surprise/1.0 (personal RSS reader)"

# Some publishers 403 anything that isn't a browser. Fallback only.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    bucket: str
    # False until `make validate-feeds` has returned OK for it.
    verified: bool = False
    # True when the feed ships a teaser instead of the article body. Those
    # entries word-count to ~1 minute, get rejected by the read-time
    # filter, and sit in the DB forever without ever being picked. The
    # fetcher has to open the article page to get a real read_minutes.
    needs_page_fetch: bool = False


# All feeds verified and measured by `make inspect-feeds` on 2026-08-20.
# Fifteen were dropped in that pass because they can never produce an
# article inside the 5-15 minute window:
#
#   genuinely short posts  Public Domain Review, Colossal, Hyperallergic,
#                          Language Log, Longreads, Marginal Revolution,
#                          3 Quarks Daily, Vittles
#   link aggregators       Hacker News Best — entries are stubs (~10 words)
#                          and the article lives on a third-party domain
#   empty content field    ArchDaily, Google Cloud Blog,
#                          The Marshall Project, The Diff (paywalled)
#   always too long        Admiral Cloudberg (~13.7k words median),
#                          The Atavist (~10.8k)
#
# Opening the article page would not rescue any of them: the short group
# really is that short, the long two really are that long, and an
# aggregator's text was never on its own domain to begin with.
FEEDS = [
    # --- curious ----------------------------------------------------
    Feed("Quanta", "https://www.quantamagazine.org/feed/", "curious", True, needs_page_fetch=True),
    Feed("Psyche", "https://psyche.co/feed", "curious", True, needs_page_fetch=True),
    Feed("Strong Towns", "https://www.strongtowns.org/journal?format=rss", "curious", True, needs_page_fetch=True),
    Feed("Atlas Obscura", "https://www.atlasobscura.com/feeds/latest", "curious", True, needs_page_fetch=True),
    Feed("Nautilus", "https://nautil.us/feed/", "curious", True, needs_page_fetch=True),
    Feed("Undark", "https://undark.org/feed/", "curious", True, needs_page_fetch=True),
    Feed("Sapiens", "https://www.sapiens.org/feed/", "curious", True),
    Feed("JSTOR Daily", "https://daily.jstor.org/feed/", "curious", True),
    Feed("Common Edge", "https://commonedge.org/feed/", "curious", True),
    Feed("Comment Magazine", "https://comment.org/feed/", "curious", True, needs_page_fetch=True),

    # --- essays -----------------------------------------------------
    # Four of these five ship teasers only. Without the page fetch this
    # bucket is Paris Review alone.
    Feed("Aeon", "https://aeon.co/feed.rss", "essays", True, needs_page_fetch=True),
    Feed("Paris Review", "https://www.theparisreview.org/blog/feed/", "essays", True),
    Feed("LRB", "https://www.lrb.co.uk/feeds/rss", "essays", True, needs_page_fetch=True),
    Feed("The New Yorker", "https://www.newyorker.com/feed/everything", "essays", True, needs_page_fetch=True),
    Feed("Public Books", "https://www.publicbooks.org/feed/", "essays", True, needs_page_fetch=True),

    # --- wildcard ---------------------------------------------------
    Feed("Damn Interesting", "https://www.damninteresting.com/feed/", "wildcard", True, needs_page_fetch=True),
    Feed("Eater", "https://www.eater.com/rss/index.xml", "wildcard", True),
    Feed("Defector", "https://defector.com/feed", "wildcard", True, needs_page_fetch=True),

    # --- stories ----------------------------------------------------
    Feed("The Atlantic", "https://www.theatlantic.com/feed/all/", "stories", True),
    Feed("Narratively", "https://narratively.com/feed/", "stories", True),
    Feed("ProPublica", "https://www.propublica.org/feeds/propublica/main", "stories", True),

    # --- ai ---------------------------------------------------------
    Feed("Import AI", "https://importai.substack.com/feed", "ai", True),
    Feed("One Useful Thing", "https://www.oneusefulthing.org/feed", "ai", True),
    Feed("The Gradient", "https://thegradient.pub/rss/", "ai", True),
    Feed("Simon Willison", "https://simonwillison.net/atom/everything/", "ai", True, needs_page_fetch=True),

    # --- tech -------------------------------------------------------
    Feed("Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed", "tech", True),

    # --- cloud ------------------------------------------------------
    Feed("AWS Architecture", "https://aws.amazon.com/blogs/architecture/feed/", "cloud", True),
    Feed("The New Stack", "https://thenewstack.io/feed/", "cloud", True),
    Feed("Last Week in AWS", "https://www.lastweekinaws.com/feed/", "cloud", True),
    Feed("CNCF", "https://www.cncf.io/feed/", "cloud", True),

    # --- finance ----------------------------------------------------
    Feed("Of Dollars And Data", "https://ofdollarsanddata.com/feed/", "finance", True),
    Feed("Noahpinion", "https://www.noahpinion.blog/feed", "finance", True),
    Feed("Construction Physics", "https://www.construction-physics.com/feed", "finance", True),

    # --- lifestyle --------------------------------------------------
    Feed("Outside", "https://www.outsideonline.com/feed/", "lifestyle", True),
    Feed("GQ", "https://www.gq.com/feed/rss", "lifestyle", True, needs_page_fetch=True),
]


def _validate() -> None:
    total = sum(CORE_BUCKET_WEIGHTS.values())
    # Floating point: these won't land exactly on 1.0.
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