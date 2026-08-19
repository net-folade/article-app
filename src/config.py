"""All tunable constants for the picker live here.

Nothing in this file depends on anything else in the app. That makes the
whole selection algorithm re-tunable by editing one file, and keeps the
statistical tests honest — they import the same weights the runtime uses.
"""

# --- Reading time -------------------------------------------------------

WORDS_PER_MINUTE = 238

# --- Picker behaviour ---------------------------------------------------

WILDCARD_PROBABILITY = 0.30

# Must sum to 1.0. Asserted below so a bad edit fails at import time
# rather than silently skewing the distribution.
CORE_BUCKET_WEIGHTS = {
    "ai": 0.21,
    "tech": 0.21,
    "cloud": 0.14,
    "finance": 0.21,
    "lifestyle": 0.14,
    "stories": 0.09,
}

WILDCARD_BUCKETS = ["essays", "wildcard"]

# --- Filters ------------------------------------------------------------

MIN_READ_MINUTES = 5
MAX_READ_MINUTES = 15

FRESHNESS_DAYS = 7
FALLBACK_FRESHNESS_DAYS = 14

PER_SOURCE_MONTHLY_CAP = 3
SOURCE_CAP_WINDOW_DAYS = 30


def _validate() -> None:
    total = sum(CORE_BUCKET_WEIGHTS.values())
    # Floating point: 0.21 + 0.21 + ... won't land exactly on 1.0.
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"CORE_BUCKET_WEIGHTS must sum to 1.0, got {total}")
    if not 0.0 <= WILDCARD_PROBABILITY <= 1.0:
        raise ValueError("WILDCARD_PROBABILITY must be between 0 and 1")
    if MIN_READ_MINUTES > MAX_READ_MINUTES:
        raise ValueError("MIN_READ_MINUTES cannot exceed MAX_READ_MINUTES")
    overlap = set(CORE_BUCKET_WEIGHTS) & set(WILDCARD_BUCKETS)
    if overlap:
        raise ValueError(f"Buckets cannot be both core and wildcard: {overlap}")


_validate()