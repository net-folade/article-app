import pytest

from src.readtime import estimate_minutes, word_count


def test_empty_and_none_return_zero():
    assert word_count("") == 0
    assert word_count(None) == 0
    assert estimate_minutes("") == 0
    assert estimate_minutes(None) == 0


def test_single_word_is_one_minute():
    assert word_count("hello") == 1
    assert estimate_minutes("hello") == 1


def test_exactly_238_words_is_one_minute():
    text = " ".join(["word"] * 238)
    assert word_count(text) == 238
    assert estimate_minutes(text) == 1


def test_239_words_rounds_up_to_two():
    text = " ".join(["word"] * 239)
    assert estimate_minutes(text) == 2


def test_unicode_words_are_counted():
    assert word_count("café naïve résumé") == 3
    assert word_count("東京 大阪") == 2
    assert word_count("Ελλάδα") == 1


def test_punctuation_does_not_inflate_count():
    assert word_count("Hello, world!") == 2
    assert word_count("one — two") == 2
    assert word_count("...") == 0
    assert word_count("  spaced   out  ") == 2


def test_long_article_is_eight_minutes():
    text = " ".join(["word"] * 1900)
    assert estimate_minutes(text) == 8


@pytest.mark.parametrize(
    "count,expected",
    [(1, 1), (238, 1), (239, 2), (476, 2), (477, 3)],
)
def test_minute_boundaries(count, expected):
    assert estimate_minutes(" ".join(["word"] * count)) == expected
