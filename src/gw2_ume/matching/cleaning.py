"""Cell text cleaning utilities for Guild Wars 2 tables."""

from __future__ import annotations

import re
import html


# Regular expressions for cleaning table cell strings
RE_HTML_TAGS = re.compile(r"<[^>]+>")
RE_WIKI_PIPE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")  # [[Target|Display]] -> Display
RE_WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")
RE_TIER = re.compile(r"\(?\b(?:Tier|T)\s*[0-9]+\b\)?", re.IGNORECASE)
RE_QUANTITY_PREFIX = re.compile(r"^(?:[0-9]+[xX]|[xX]\s*[0-9]+|[0-9]+(?:\s*(?:ea|count|pieces?|stacks?|qty:?))\b)\s*", re.IGNORECASE)
RE_QUANTITY_SUFFIX = re.compile(r"\s*(?:[xX]\s*[0-9]+|[0-9]+[xX]|\([0-9]+\)|\[[0-9]+\]|\b[0-9]+\s*(?:ea|count|pieces?|stacks?)\b)$", re.IGNORECASE)
RE_GW2_CURRENCY = re.compile(
    r"(?:\b[0-9]+\s*(?:g|s|c|gold|silver|copper|karma|badges?|laurels?|unbound magic|volatile magic)\b|[0-9]+\s*🪙)",
    re.IGNORECASE,
)
RE_STANDALONE_NUMBER = re.compile(r"^\s*[0-9]+(?:\.[0-9]+)?\s*$")
RE_EXTRA_PUNCTUATION = re.compile(r"^[\s\-_,:;/•\(\)]+|[\s\-_,:;/•\(\)]+$")
RE_WHITESPACE = re.compile(r"\s+")


def clean_cell_text(raw_text: str) -> str:
    """Clean table cell strings removing HTML, wiki markup, quantity, tier, and currency notation.

    Examples:
        - "[[Spiritwood Plank]] x10" -> "Spiritwood Plank"
        - "100g 50s [[Mystic Clover]]" -> "Mystic Clover"
        - "The Raven (Tier 1)" -> "The Raven"
        - "10x [[Elonian Leather Square]]" -> "Elonian Leather Square"
        - "<span>Superior Rune of the Monk</span> (5)" -> "Superior Rune of the Monk"
    """
    if not raw_text:
        return ""

    # Unescape HTML entities
    text = html.unescape(raw_text)

    # Remove HTML tags
    text = RE_HTML_TAGS.sub(" ", text)

    # Normalize wiki links
    text = RE_WIKI_PIPE.sub(r"\1", text)
    text = RE_WIKI_LINK.sub(r"\1", text)

    # Remove Tiers e.g. (Tier 1), T4
    text = RE_TIER.sub(" ", text)

    # Remove currency notations
    text = RE_GW2_CURRENCY.sub(" ", text)

    # Remove quantity prefixes and suffixes
    text = RE_QUANTITY_PREFIX.sub("", text)
    text = RE_QUANTITY_SUFFIX.sub("", text)

    # Trim punctuation and normalize whitespaces
    text = RE_WHITESPACE.sub(" ", text).strip()
    text = RE_EXTRA_PUNCTUATION.sub("", text).strip()

    # Recheck for trailing/leading numbers after stripping
    text = RE_QUANTITY_PREFIX.sub("", text)
    text = RE_QUANTITY_SUFFIX.sub("", text)
    text = RE_EXTRA_PUNCTUATION.sub("", text).strip()

    return text
