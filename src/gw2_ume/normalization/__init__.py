"""Normalization subpackage for GW2-UME.

Provides text cleaning, typo normalization, span extraction, table parsing,
and pluggable LLM-based normalizers.
"""

from gw2_ume.normalization.llm_normalizer import (
    APILLMNormalizer,
    HeuristicNormalizer,
    LLMNormalizer,
    LocalGemmaNormalizer,
    get_normalizer,
)
from gw2_ume.normalization.text_cleaner import (
    CSVTableParser,
    HTMLTableParser,
    JSONTableParser,
    MarkdownTableParser,
    TSVTableParser,
    TextCleaner,
    extract_entity_spans,
    normalize_text,
    parse_table,
)

__all__ = [
    "TextCleaner",
    "normalize_text",
    "extract_entity_spans",
    "parse_table",
    "MarkdownTableParser",
    "CSVTableParser",
    "TSVTableParser",
    "HTMLTableParser",
    "JSONTableParser",
    "LLMNormalizer",
    "HeuristicNormalizer",
    "LocalGemmaNormalizer",
    "APILLMNormalizer",
    "get_normalizer",
]
