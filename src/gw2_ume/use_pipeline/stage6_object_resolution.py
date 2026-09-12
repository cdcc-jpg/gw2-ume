"""Stage 6: Concept-Shaped Object Resolution.

Zero Domain Semantics in Python: Concept matching over dynamically discovered Class and Individual definitions.
Rules:
- For concept-shaped objects (categoricals, non-UUIDs):
  - Skip UUIDs and structured IDs -> remains literal.
  - String-match cascade over Class labels (>= 0.75 -> resolved URI).
  - Embedding search over Class summaries (>= 0.40 -> resolved URI).
  - Otherwise remains literal.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Set, Tuple

import numpy as np
from rdflib.namespace import XSD

from gw2_ume.use_pipeline.stage0_setup import (
    ClassInfo,
    OntologyIndex,
    normalize_string,
    tokenize_string,
)
from gw2_ume.use_pipeline.stage2_classification import is_id_shaped, is_numeric_value


@dataclass
class ObjectResolutionResult:
    """Result of object resolution for a cell value."""
    raw_value: Any
    resolved_value: str  # URI if concept, or string representation of literal
    is_concept: bool     # True if mapped to an ontology class or named individual
    confidence: float
    method: str          # Concept-StringMatch, Concept-EmbeddingMatch, Literal-Value


class ObjectResolver:
    """Stage 6 Concept Resolver."""

    def __init__(self, ontology_index: OntologyIndex):
        self.index = ontology_index

    def resolve(
        self,
        value: Any,
        column_role: str,
        target_ranges: Optional[List[str]] = None,
    ) -> ObjectResolutionResult:
        """Resolve a cell value into either a concept URI or a preserved literal value."""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value="",
                is_concept=False,
                confidence=1.0,
                method="Literal-Value",
            )

        str_val = str(value).strip()
        if not str_val:
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value="",
                is_concept=False,
                confidence=1.0,
                method="Literal-Value",
            )

        # 1. Non-concept roles remain literal
        if column_role in ("Numeric property", "Measurement value/unit pair", "Timestamp", "Entity ID", "Foreign Key", "Skip", "Text"):
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value=str_val,
                is_concept=False,
                confidence=1.0,
                method="Literal-Value",
            )

        # 2. Skip UUIDs and structured IDs even if in Categorical columns
        if is_id_shaped(str_val) or is_numeric_value(str_val):
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value=str_val,
                is_concept=False,
                confidence=1.0,
                method="Literal-Value",
            )

        # 2b. Standard datatype ranges (e.g. xsd:string, xsd:integer) must remain literals
        if target_ranges and any(r.startswith(str(XSD)) or "XMLSchema#" in r for r in target_ranges):
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value=str_val,
                is_concept=False,
                confidence=1.0,
                method="Literal-Value",
            )

        # 3. Concept matching for categoricals / text
        # Step A: String-match cascade over Class labels (>= 0.75 -> resolved)
        match_uri, match_score, match_method = self._match_class_by_string(str_val, target_ranges)
        if match_uri is not None and match_score >= 0.75:
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value=match_uri,
                is_concept=True,
                confidence=round(match_score, 4),
                method="Concept-StringMatch",
            )

        # Step B: Embedding search over Class summaries (>= 0.40 -> resolved)
        emb_uri, emb_score = self._match_class_by_embedding(str_val, target_ranges)
        if emb_uri is not None and emb_score >= 0.40:
            return ObjectResolutionResult(
                raw_value=value,
                resolved_value=emb_uri,
                is_concept=True,
                confidence=round(emb_score, 4),
                method="Concept-EmbeddingMatch",
            )

        # Step C: Fallback to Literal-Value
        return ObjectResolutionResult(
            raw_value=value,
            resolved_value=str_val,
            is_concept=False,
            confidence=1.0,
            method="Literal-Value",
        )

    def _match_class_by_string(
        self,
        query: str,
        target_ranges: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], float, str]:
        """Cascade string matching against Class labels:
        - Exact (0.98)
        - Normalised (0.95)
        - TokenSubset (0.80 - 0.90)
        - Fuzzy (ratio * 0.92)
        """
        q_clean = query.strip()
        q_norm = normalize_string(q_clean)
        q_tokens = set(tokenize_string(q_clean))

        candidate_classes = list(self.index.classes.values())
        if target_ranges:
            # If target ranges specify classes, prioritize them
            range_classes = [c for c in candidate_classes if c.uri in target_ranges]
            if range_classes:
                candidate_classes = range_classes

        # 1. Exact
        for c in candidate_classes:
            labels = [c.label] + c.alt_labels + ([c.pref_label] if c.pref_label else [])
            for l in labels:
                if q_clean.lower() == l.strip().lower():
                    return c.uri, 0.98, "Exact"

        # 2. Normalised
        for c in candidate_classes:
            labels = [c.label] + c.alt_labels + ([c.pref_label] if c.pref_label else [])
            for l in labels:
                if q_norm == normalize_string(l):
                    return c.uri, 0.95, "Normalised"

        # 3. TokenSubset
        best_subset: Optional[Tuple[str, float]] = None
        for c in candidate_classes:
            labels = [c.label] + c.alt_labels + ([c.pref_label] if c.pref_label else [])
            for l in labels:
                l_tokens = set(tokenize_string(l))
                if l_tokens and q_tokens and (l_tokens.issubset(q_tokens) or q_tokens.issubset(l_tokens)):
                    overlap = len(l_tokens.intersection(q_tokens))
                    union = len(l_tokens.union(q_tokens))
                    ratio = overlap / max(union, 1)
                    if ratio >= 0.60:
                        score = 0.75 + (0.17 * ratio)
                        if best_subset is None or score > best_subset[1]:
                            best_subset = (c.uri, score)
        if best_subset and best_subset[1] >= 0.75:
            return best_subset[0], best_subset[1], "TokenSubset"

        # 4. Fuzzy
        best_fuzzy: Optional[Tuple[str, float]] = None
        for c in candidate_classes:
            labels = [c.label] + c.alt_labels + ([c.pref_label] if c.pref_label else [])
            for l in labels:
                ratio = difflib.SequenceMatcher(None, q_norm, normalize_string(l)).ratio()
                if ratio >= 0.82:  # ratio * 0.92 >= 0.754
                    score = ratio * 0.92
                    if best_fuzzy is None or score > best_fuzzy[1]:
                        best_fuzzy = (c.uri, score)
        if best_fuzzy and best_fuzzy[1] >= 0.75:
            return best_fuzzy[0], best_fuzzy[1], "Fuzzy"

        return None, 0.0, "None"

    def _match_class_by_embedding(
        self,
        query: str,
        target_ranges: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], float]:
        """Cosine similarity search over class summaries."""
        if not self.index.class_uris or self.index.class_embeddings is None:
            return None, 0.0

        q_vec = self.index.encode_text(query)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 1e-8:
            q_vec = q_vec / q_norm

        dots = np.dot(self.index.class_embeddings, q_vec)

        best_idx = None
        best_score = -1.0
        for i, uri in enumerate(self.index.class_uris):
            score = float(dots[i])
            if target_ranges and uri not in target_ranges:
                # Still allow non-target if target not matched, but score penalty
                score *= 0.8
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is not None and best_score >= 0.40:
            return self.index.class_uris[best_idx], best_score

        return None, 0.0
