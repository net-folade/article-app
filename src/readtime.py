# estimate reading time from article rext. 
from __future__ import annotations 

import math
import re 

WORDS_PER_MINUTE=238 

# A token counts as a word only if it contains at least one alphanumeric
# character. [^\W_] means "word character, but not underscore" — which is
# alphanumerics across all Unicode scripts, not just ASCII.
_HAS_ALNUM = re.compile(r"[^\W_]", re.UNICODE)


def word_count(text:str | None) -> int:
    # count words in text. none and empty sting both return 0
    if not text:
        return 0
    return sum(1 for token in text.split() if _HAS_ALNUM.search(token))

def estimate_minutes(text:str | None) -> int:
    # reading time in whole mins, rounded up. 
    # floor of 1 for any real text. 
    words=word_count(text)
    if words == 0:
        return 0
    return max(1, math.ceil(words /  WORDS_PER_MINUTE))