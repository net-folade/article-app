"""Estimate reading time from article text."""

from __future__ import annotations

import math
import re

from src.config import WORDS_PER_MINUTE

# Match alphanumeric characters across all Unicode scripts, excluding underscores.
_HAS_ALNUM = re.compile(r"[^\W_]", re.UNICODE)


def word_count(text: str | None) -> int:
    """Count whitespace-delimited tokens containing an alphanumeric character."""
    if not text:
        return 0
    return sum(1 for token in text.split() if _HAS_ALNUM.search(token))

def estimate_minutes(text: str | None) -> int:
    """Return whole reading minutes, with a minimum of one for nonempty text."""
    words = word_count(text)
    if words == 0:
        return 0
    return max(1, math.ceil(words / WORDS_PER_MINUTE))
