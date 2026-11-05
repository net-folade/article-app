"""Paragraph extraction for the reader sample export, offline."""

from __future__ import annotations

from scripts.export_samples import _is_boilerplate, extract_paragraphs

LONG = ' '.join(['word'] * 320)

PAGE = f"""
<html><head><style>p {{ color: red; }}</style></head>
<body>
<nav><p>Home About Contact Archive Search Login Menu Topics</p></nav>
<article>
  <h1>Title</h1>
  <p>The river had been <em>rising</em>, slowly and quietly, for three whole days.</p>
  <p>Too short to keep.</p>
  <p>Subscribe to our newsletter for more stories like this one every week.</p>
  <p>She said &ldquo;wait&rdquo; and the  boat
     drifted off&nbsp;into the grey morning light again.</p>
  <p>The river had been <em>rising</em>, slowly and quietly, for three whole days.</p>
  <p>{LONG}</p>
  <p class="card">A related essay teaser that sits inside the article block.</p>
  <p>Any code for this post can be found here: https://github.com/example/repo</p>
</article>
<footer><p>Copyright 2026 Example Media, every single right is reserved here.</p></footer>
</body></html>
"""


def test_extracts_clean_paragraphs_from_article():
    paragraphs = extract_paragraphs(PAGE)
    assert paragraphs == [
        'The river had been rising, slowly and quietly, for three whole days.',
        'She said “wait” and the boat drifted off into the grey morning light again.',
        LONG,
    ]


def test_falls_back_to_page_when_article_block_is_a_teaser():
    page = (
        '<article><p>A short related card with only a few words here.</p></article>'
        f'<div class="body"><p>{LONG}</p></div>'
    )
    assert extract_paragraphs(page) == [
        'A short related card with only a few words here.',
        LONG,
    ]


def test_empty_input():
    assert extract_paragraphs('') == []


def test_boilerplate_matches_whole_phrases_only():
    assert _is_boilerplate('Sign up for our weekly newsletter and never miss a story again.')
    assert _is_boilerplate('Join us in London next month, RSVP to save your seat at the event.')
    assert not _is_boilerplate('She baked a chocolate chip cookie for every child on the street.')
    assert not _is_boilerplate('Every entry in the old catalog in the basement was handwritten.')
