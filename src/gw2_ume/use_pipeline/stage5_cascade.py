"""Stage 5 & 5a: Predicate Resolution Cascade & Axiom-Gated Reranker.

Zero Domain Semantics in Python: Rules, ranges, domains, and labels are dynamically discovered.
Implements:
- 6-step cascade ladder:
  1. Stage0-Exact (0.98)
  2. Stage0-Normalised (0.95)
  3. Stage0-TokenSubset (0.70 - 0.92)
  4. Stage0-Containment (0.51 - 0.85)
  5. Stage0-Fuzzy (ratio * 0.92)
  6. FAISS-Edge (embedding cosine similarity >= 0.40)
- Suffix sanity re-probes:
  - ID suffix probe (_ID, ID, _IDENTIFIER)
  - _VALUE / _UNIT suffix probe
  - _PERCENT / _PCT suffix probe
- Weak result check (FAISS-Edge or confidence in [0.40, 0.65]):
  - If weak & LLM enabled -> Stage 5a.
  - If weak & LLM disabled -> keep weak result, review_flag=True.
- Stage 5a Axiom-Gated Reranker:
  - Top-8 candidates from property embedding index, deduplicated by URI.
  - Deterministic Axiom Veto: Drop candidates whose declared rdfs:range contradicts column structural role.
  - If 0 survive -> keep previous weak result.
  - If 1 survives -> accept directly with confidence 0.66, method AxiomFilter-Unique (zero LLM call!).
  - If >= 2 survive -> prompt LLM (or fallback), map confidence (0.75 / 0.65 / 0.55), method LLM-Reranked, review_flag=True.
"""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
from rdflib.namespace import XSD

from gw2_ume.use_pipeline.stage0_setup import (
    OntologyIndex,
    PropertyInfo,
    normalize_string,
    tokenize_string,
)


@dataclass
class MatchResult:
    """Predicate resolution result."""
    uri: str
    label: str
    confidence: float
    method: str  # Stage0-Exact, Stage0-Normalised, Stage0-TokenSubset, Stage0-Containment, Stage0-Fuzzy, FAISS-Edge, AxiomFilter-Unique, LLM-Reranked, Arbiter-Reranked
    review_flag: bool
    domains: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    comment: str = ""
    property_type: str = "DatatypeProperty"
    min_inclusive: Optional[float] = None
    max_inclusive: Optional[float] = None


# Common XSD types for axiom checks
NUMERIC_RANGES = {
    str(XSD.integer),
    str(XSD.int),
    str(XSD.decimal),
    str(XSD.float),
    str(XSD.double),
    str(XSD.nonNegativeInteger),
    str(XSD.positiveInteger),
    str(XSD.nonPositiveInteger),
    str(XSD.negativeInteger),
    str(XSD.long),
    str(XSD.short),
    str(XSD.byte),
    str(XSD.unsignedInt),
    str(XSD.unsignedLong),
    str(XSD.unsignedShort),
}

TEMPORAL_RANGES = {
    str(XSD.dateTime),
    str(XSD.date),
    str(XSD.time),
    str(XSD.gYear),
    str(XSD.gYearMonth),
}

STRING_RANGES = {
    str(XSD.string),
    str(XSD.normalizedString),
    str(XSD.token),
    str(XSD.language),
}

BOOLEAN_RANGES = {
    str(XSD.boolean),
}


class PredicateResolver:
    """Stage 5 & 5a Predicate Cascade and Axiom-Gated Reranker."""

    def __init__(
        self,
        ontology_index: OntologyIndex,
        enable_llm: bool = False,
        llm_client: Optional[Callable[[str], str]] = None,
    ):
        self.index = ontology_index
        self.enable_llm = enable_llm
        self.llm_client = llm_client

    def _extract_numeric_summary(
        self,
        sample_values: Optional[Sequence[Any]],
    ) -> Tuple[Optional[float], Optional[float]]:
        """Extract min and max numeric values from sample values."""
        if not sample_values:
            return None, None
        nums: List[float] = []
        for v in sample_values:
            if v is None:
                continue
            if isinstance(v, (int, float)):
                if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                    nums.append(float(v))
            elif isinstance(v, str):
                v_clean = v.strip().replace(",", "")
                try:
                    nums.append(float(v_clean))
                except ValueError:
                    m = re.match(r"^([+-]?\d+(?:\.\d+)?)", v_clean)
                    if m:
                        try:
                            nums.append(float(m.group(1)))
                        except ValueError:
                            pass
        if not nums:
            return None, None
        return min(nums), max(nums)

    def _violates_bounds(
        self,
        prop: PropertyInfo,
        min_val: Optional[float],
        max_val: Optional[float],
    ) -> bool:
        """Returns True if observed numerical values violate the property's declared bounds."""
        if min_val is not None and prop.min_inclusive is not None:
            if min_val < prop.min_inclusive:
                return True
        if max_val is not None and prop.max_inclusive is not None:
            if max_val > prop.max_inclusive:
                return True
        return False

    def _are_ranges_compatible(self, p1: PropertyInfo, p2: PropertyInfo) -> bool:
        """Returns True if two properties have overlapping, compatible, or open ranges."""
        r1 = set(p1.ranges)
        r2 = set(p2.ranges)
        if not r1 or not r2:
            return True
        if bool(r1 & r2):
            return True
        if bool(r1 & NUMERIC_RANGES) and bool(r2 & NUMERIC_RANGES):
            return True
        if bool(r1 & STRING_RANGES) and bool(r2 & STRING_RANGES):
            return True
        if bool(r1 & TEMPORAL_RANGES) and bool(r2 & TEMPORAL_RANGES):
            return True
        if bool(r1 & BOOLEAN_RANGES) and bool(r2 & BOOLEAN_RANGES):
            return True
        return False

    def _score_property_against_query(
        self,
        prop: PropertyInfo,
        query: str,
    ) -> Tuple[float, str]:
        """Compute the highest cascade score and method for a property against query string."""
        q_clean = query.strip()
        q_norm = normalize_string(q_clean)
        q_tokens = set(tokenize_string(q_clean))

        labels = [prop.label] + prop.alt_labels + ([prop.pref_label] if prop.pref_label else [])

        # 1. Exact
        for l in labels:
            if q_clean == l or q_clean.lower() == l.lower():
                return 0.98, "Stage0-Exact"

        # 2. Normalised
        for l in labels:
            if q_norm == normalize_string(l):
                return 0.95, "Stage0-Normalised"

        # Suffix-stripped probe check
        raw_upper = q_clean.upper()
        for sfx in ("_VALUE", "_VAL", "_UNIT", "_UNITS", "_PERCENT", "_PCT", "_PERCENTAGE", "_ID", "_IDENTIFIER", "_CODE", "_UUID"):
            if raw_upper.endswith(sfx):
                base = q_clean[:len(q_clean) - len(sfx)].strip("_ ")
                base_norm = normalize_string(base)
                for l in labels:
                    if base.lower() == l.lower():
                        return 0.98, "SuffixProbe-Exact"
                    if base_norm == normalize_string(l):
                        return 0.95, "SuffixProbe-Normalised"
                break

        # 3. TokenSubset (0.70 - 0.92)
        best_subset = 0.0
        for l in labels:
            l_tokens = set(tokenize_string(l))
            if not l_tokens or not q_tokens:
                continue
            if l_tokens.issubset(q_tokens) or q_tokens.issubset(l_tokens):
                overlap = len(l_tokens.intersection(q_tokens))
                union = len(l_tokens.union(q_tokens))
                ratio = overlap / max(union, 1)
                score = (0.70 + 0.22 * ratio) if ratio >= 0.50 else (0.50 + 0.25 * ratio)
                if score > best_subset:
                    best_subset = score
        if best_subset > 0.0:
            return round(best_subset, 4), "Stage0-TokenSubset"

        # 4. Containment (0.51 - 0.85)
        best_contain = 0.0
        for l in labels:
            l_norm = normalize_string(l)
            if not l_norm or not q_norm:
                continue
            if l_norm in q_norm or q_norm in l_norm:
                min_len = min(len(l_norm), len(q_norm))
                max_len = max(len(l_norm), len(q_norm))
                ratio = min_len / max_len if max_len > 0 else 0
                score = 0.51 + (0.34 * ratio)
                if score > best_contain:
                    best_contain = score
        if best_contain > 0.0:
            return round(best_contain, 4), "Stage0-Containment"

        # 5. Fuzzy (ratio * 0.92)
        best_fuzzy = 0.0
        for l in labels:
            ratio = difflib.SequenceMatcher(None, q_norm, normalize_string(l)).ratio()
            if ratio >= 0.65:
                score = ratio * 0.92
                if score > best_fuzzy:
                    best_fuzzy = score
        if best_fuzzy > 0.0:
            return round(best_fuzzy, 4), "Stage0-Fuzzy"

        # 6. FAISS-Edge embedding match
        if self.index.property_uris and self.index.property_embeddings is not None and prop.uri in self.index.property_uris:
            idx = self.index.property_uris.index(prop.uri)
            q_vec = self.index.encode_text(query)
            q_norm_val = np.linalg.norm(q_vec)
            if q_norm_val > 1e-8:
                q_vec = q_vec / q_norm_val
                score = float(np.dot(self.index.property_embeddings[idx], q_vec))
                if score >= 0.40:
                    return round(score, 4), "FAISS-Edge"

        return 0.0, "None"

    def resolve(
        self,
        column_name: str,
        column_role: str,
        sample_values: Optional[List[Any]] = None,
        domain_restriction: Optional[Set[str]] = None,
    ) -> MatchResult:
        """Resolve a column name to an ontology property through the 6-step cascade ladder,
        suffix re-probes, SHACL bounds check, same-range competitor detection, and Stage 5a Arbiter.
        """
        # Numeric summary bounds from sample_values
        min_val, max_val = self._extract_numeric_summary(sample_values)

        # Step 1: Run 6-step cascade ladder on raw column name with axiom filtering
        cand = self._run_ladder(column_name, domain_restriction, column_role=column_role)

        # Step 2: Suffix sanity re-probes
        reprobe_cand = self._run_suffix_reprobes(column_name, domain_restriction, column_role=column_role)
        if reprobe_cand is not None and (cand is None or reprobe_cand.confidence > cand.confidence):
            reprobe_p = self.index.properties.get(reprobe_cand.uri)
            if (
                reprobe_p
                and not self._violates_axiom(reprobe_p, column_role)
                and not self._violates_bounds(reprobe_p, min_val, max_val)
            ):
                cand = reprobe_cand
            elif cand is None:
                cand = reprobe_cand

        # Step 3: Value distribution & SHACL bounds check on cand
        if cand is not None:
            cand_p = self.index.properties.get(cand.uri)
            if cand_p and self._violates_bounds(cand_p, min_val, max_val):
                cand = None  # Pruned due to bounds violation!

        # If still no candidate found, try embedding search directly
        if cand is None:
            cand = self._search_faiss_edge(column_name, domain_restriction, column_role=column_role)
            if cand is not None:
                cand_p = self.index.properties.get(cand.uri)
                if cand_p and self._violates_bounds(cand_p, min_val, max_val):
                    cand = None

        # Step 4: Same-Range Competitor & Near-Tie Detection
        trigger_arbiter = False
        competitor_props: List[PropertyInfo] = []

        viable_candidates: List[Tuple[PropertyInfo, float]] = []
        candidate_props = list(self.index.properties.values())
        if domain_restriction:
            filtered = [p for p in candidate_props if not p.domains or any(d in domain_restriction for d in p.domains)]
            if filtered:
                candidate_props = filtered

        for p in candidate_props:
            if self._violates_axiom(p, column_role):
                continue

            if cand is not None and p.uri == cand.uri:
                score = cand.confidence
            else:
                score, _ = self._score_property_against_query(p, column_name)

            if score >= 0.40:
                viable_candidates.append((p, score))

        if viable_candidates:
            viable_candidates.sort(key=lambda x: x[1], reverse=True)
            top_p, top_score = viable_candidates[0]
            same_range = [c for c in viable_candidates if self._are_ranges_compatible(c[0], top_p)]
            if len(same_range) >= 2:
                runner_up_p, runner_up_score = same_range[1]
                # Condition: runner-up within 0.15 of top, OR top_score < 0.90 with >= 2 viable same-range candidates
                if (runner_up_score >= top_score - 0.15) or (top_score < 0.90):
                    trigger_arbiter = True
                    competitor_props = [c[0] for c in same_range]

        # Step 5: Weak result check (FAISS-Edge or confidence in [0.40, 0.65]) or Competitor collision
        is_weak = cand is None or cand.method == "FAISS-Edge" or (0.40 <= cand.confidence <= 0.65)

        if is_weak or trigger_arbiter:
            if cand is None:
                # Create a placeholder weak candidate if totally unmapped
                cand = MatchResult(
                    uri="urn:priory:unmapped_property",
                    label=column_name,
                    confidence=0.30,
                    method="Unmapped",
                    review_flag=True,
                )

            # Invoke Stage 5a Axiom Veto & Arbiter
            stage5a_result = self._stage_5a_axiom_rerank(
                column_name=column_name,
                column_role=column_role,
                sample_values=sample_values or [],
                weak_candidate=cand,
                domain_restriction=domain_restriction,
                competitor_candidates=competitor_props if trigger_arbiter else None,
            )
            return stage5a_result

        return cand

    def _run_ladder(
        self,
        query: str,
        domain_restriction: Optional[Set[str]] = None,
        column_role: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """Runs the 6-step cascade ladder:
        1. Exact (0.98)
        2. Normalised (0.95)
        3. TokenSubset (0.70 - 0.92)
        4. Containment (0.51 - 0.85)
        5. Fuzzy (ratio * 0.92)
        6. FAISS-Edge (cosine similarity >= 0.40)
        """
        q_clean = query.strip()
        q_norm = normalize_string(q_clean)
        q_tokens = set(tokenize_string(q_clean))

        # Filter properties if domain restriction provided
        candidate_props = list(self.index.properties.values())
        if domain_restriction:
            filtered = []
            for p in candidate_props:
                # Keep if property domains intersect or property has no domain specified (open domain)
                if not p.domains or any(d in domain_restriction for d in p.domains):
                    filtered.append(p)
            if filtered:
                candidate_props = filtered

        # Filter out properties violating column role axioms
        if column_role:
            candidate_props = [p for p in candidate_props if not self._violates_axiom(p, column_role)]

        # 1. Exact Match (0.98)
        for p in candidate_props:
            labels = [p.label] + p.alt_labels + ([p.pref_label] if p.pref_label else [])
            for l in labels:
                if q_clean == l or q_clean.lower() == l.lower():
                    return self._create_result(p, 0.98, "Stage0-Exact", review_flag=False)

        # 2. Normalised Match (0.95)
        for p in candidate_props:
            labels = [p.label] + p.alt_labels + ([p.pref_label] if p.pref_label else [])
            for l in labels:
                if q_norm == normalize_string(l):
                    return self._create_result(p, 0.95, "Stage0-Normalised", review_flag=False)

        # 3. TokenSubset Match (0.70 - 0.92)
        best_subset: Optional[Tuple[PropertyInfo, float]] = None
        for p in candidate_props:
            labels = [p.label] + p.alt_labels + ([p.pref_label] if p.pref_label else [])
            for l in labels:
                l_tokens = set(tokenize_string(l))
                if not l_tokens or not q_tokens:
                    continue
                # If label tokens are subset of query or query tokens are subset of label
                if l_tokens.issubset(q_tokens) or q_tokens.issubset(l_tokens):
                    overlap = len(l_tokens.intersection(q_tokens))
                    union = len(l_tokens.union(q_tokens))
                    ratio = overlap / max(union, 1)
                    if ratio >= 0.50:
                        score = 0.70 + (0.22 * ratio)
                    else:
                        score = 0.50 + (0.25 * ratio)
                    if best_subset is None or score > best_subset[1]:
                        best_subset = (p, score)
        if best_subset:
            review_flag = (best_subset[1] < 0.70)
            return self._create_result(best_subset[0], round(best_subset[1], 4), "Stage0-TokenSubset", review_flag=review_flag)

        # 4. Containment Match (0.51 - 0.85)
        best_contain: Optional[Tuple[PropertyInfo, float]] = None
        for p in candidate_props:
            labels = [p.label] + p.alt_labels + ([p.pref_label] if p.pref_label else [])
            for l in labels:
                l_norm = normalize_string(l)
                if not l_norm or not q_norm:
                    continue
                if l_norm in q_norm or q_norm in l_norm:
                    min_len = min(len(l_norm), len(q_norm))
                    max_len = max(len(l_norm), len(q_norm))
                    ratio = min_len / max_len if max_len > 0 else 0
                    score = 0.51 + (0.34 * ratio)
                    if best_contain is None or score > best_contain[1]:
                        best_contain = (p, score)
        if best_contain:
            return self._create_result(best_contain[0], round(best_contain[1], 4), "Stage0-Containment", review_flag=False)

        # 5. Fuzzy Match (ratio * 0.92)
        best_fuzzy: Optional[Tuple[PropertyInfo, float]] = None
        for p in candidate_props:
            labels = [p.label] + p.alt_labels + ([p.pref_label] if p.pref_label else [])
            for l in labels:
                ratio = difflib.SequenceMatcher(None, q_norm, normalize_string(l)).ratio()
                if ratio >= 0.65:
                    score = ratio * 0.92
                    if best_fuzzy is None or score > best_fuzzy[1]:
                        best_fuzzy = (p, score)
        if best_fuzzy:
            return self._create_result(best_fuzzy[0], round(best_fuzzy[1], 4), "Stage0-Fuzzy", review_flag=(best_fuzzy[1] < 0.70))

        # 6. FAISS-Edge Embedding Cosine Match
        return self._search_faiss_edge(query, domain_restriction, column_role=column_role)

    def _search_faiss_edge(
        self,
        query: str,
        domain_restriction: Optional[Set[str]] = None,
        column_role: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """FAISS-Edge semantic search over property summaries."""
        if not self.index.property_uris or self.index.property_embeddings is None:
            return None

        q_vec = self.index.encode_text(query)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 1e-8:
            q_vec = q_vec / q_norm

        dots = np.dot(self.index.property_embeddings, q_vec)

        # Filter by domain restriction and column role if supplied
        best_idx = None
        best_score = -1.0
        for i, uri in enumerate(self.index.property_uris):
            score = float(dots[i])
            p = self.index.properties[uri]
            if domain_restriction:
                if p.domains and not any(d in domain_restriction for d in p.domains):
                    continue
            if column_role and self._violates_axiom(p, column_role):
                continue
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is not None and best_score >= 0.40:
            uri = self.index.property_uris[best_idx]
            p = self.index.properties[uri]
            return self._create_result(p, round(best_score, 4), "FAISS-Edge", review_flag=True)

        return None

    def _run_suffix_reprobes(
        self,
        column_name: str,
        domain_restriction: Optional[Set[str]] = None,
        column_role: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """Probe variations based on recognized structural suffixes:
        - ID suffix (_id, id, _identifier, _code)
        - Value/Unit suffix (_value, _val, _unit)
        - Percent suffix (_percent, _pct)
        """
        raw_upper = column_name.upper().strip()
        reprobes = []

        # ID suffix probe
        for sfx in ("_ID", "_IDENTIFIER", "_CODE", "_UUID"):
            if raw_upper.endswith(sfx):
                base = column_name[:len(column_name) - len(sfx)].strip("_ ")
                reprobes.extend([
                    f"{base} identifier",
                    f"{base} id",
                    f"has {base} identifier",
                    base,
                ])
                break

        # Value/Unit suffix probe
        for sfx in ("_VALUE", "_VAL"):
            if raw_upper.endswith(sfx):
                base = column_name[:len(column_name) - len(sfx)].strip("_ ")
                reprobes.extend([
                    base,
                    f"{base} value",
                    f"has {base}",
                ])
                break

        for sfx in ("_UNIT", "_UNITS"):
            if raw_upper.endswith(sfx):
                base = column_name[:len(column_name) - len(sfx)].strip("_ ")
                reprobes.extend([
                    f"{base} unit",
                    base,
                ])
                break

        # Percent suffix probe
        for sfx in ("_PERCENT", "_PCT", "_PERCENTAGE"):
            if raw_upper.endswith(sfx):
                base = column_name[:len(column_name) - len(sfx)].strip("_ ")
                reprobes.extend([
                    f"{base} percentage",
                    f"{base} ratio",
                    base,
                ])
                break

        best_cand: Optional[MatchResult] = None
        for probe in reprobes:
            cand = self._run_ladder(probe, domain_restriction, column_role=column_role)
            if cand is not None:
                if best_cand is None or cand.confidence > best_cand.confidence:
                    best_cand = cand
                    if cand.confidence >= 0.95:
                        break

        return best_cand

    def _stage_5a_axiom_rerank(
        self,
        column_name: str,
        column_role: str,
        sample_values: List[Any],
        weak_candidate: MatchResult,
        domain_restriction: Optional[Set[str]] = None,
        competitor_candidates: Optional[List[PropertyInfo]] = None,
    ) -> MatchResult:
        """Stage 5a: Axiom-Gated Reranker and Full-Context Arbiter.
        1. Retrieve candidates from competitor pool and property embedding index.
        2. Deduplicate by URI.
        3. Deterministic Axiom Veto & SHACL Bounds Check.
        4. If 0 survive -> retain weak result (review_flag=True).
        5. If 1 survives -> accept directly with confidence 0.66, method AxiomFilter-Unique (zero LLM call!).
        6. If >= 2 survive -> prompt LLM (if enabled) or run deterministic Fallback Arbiter,
           returning method LLM-Reranked or Arbiter-Reranked.
        """
        min_val, max_val = self._extract_numeric_summary(sample_values)

        seen_uris: Set[str] = set()
        top_candidates: List[Tuple[PropertyInfo, float]] = []

        # Start with competitor candidates if provided
        if competitor_candidates:
            for p in competitor_candidates:
                if p.uri not in seen_uris:
                    seen_uris.add(p.uri)
                    score, _ = self._score_property_against_query(p, column_name)
                    top_candidates.append((p, score))

        # Retrieve candidates from property embedding index
        if self.index.property_uris and self.index.property_embeddings is not None:
            q_vec = self.index.encode_text(column_name)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 1e-8:
                q_vec = q_vec / q_norm

            dots = np.dot(self.index.property_embeddings, q_vec)
            top_indices = np.argsort(dots)[::-1][:16]  # take extra for filtering

            top_score = float(dots[top_indices[0]]) if len(top_indices) > 0 else 0.0
            min_threshold = max(0.18, top_score * 0.40)

            for idx in top_indices:
                score = float(dots[idx])
                if score < min_threshold:
                    continue
                uri = self.index.property_uris[idx]
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)
                p = self.index.properties[uri]

                # Check domain restriction if provided
                if domain_restriction and p.domains:
                    if not any(d in domain_restriction for d in p.domains):
                        continue

                top_candidates.append((p, score))
                if len(top_candidates) >= 8:
                    break

        if not top_candidates and weak_candidate.uri in self.index.properties:
            top_candidates.append((self.index.properties[weak_candidate.uri], weak_candidate.confidence))

        # 2. Deterministic Axiom Veto & SHACL Bounds Check
        surviving_candidates: List[Tuple[PropertyInfo, float]] = []
        for p, score in top_candidates:
            if self._violates_axiom(p, column_role):
                continue
            if self._violates_bounds(p, min_val, max_val):
                continue
            surviving_candidates.append((p, score))

        # 3. Handle outcomes:
        # Case A: 0 survive -> retain weak result
        if len(surviving_candidates) == 0:
            weak_candidate.review_flag = True
            return weak_candidate

        # Case B: Exactly 1 survives -> AxiomFilter-Unique (Zero LLM!)
        if len(surviving_candidates) == 1:
            p, orig_score = surviving_candidates[0]
            return MatchResult(
                uri=p.uri,
                label=p.label,
                confidence=0.66,
                method="AxiomFilter-Unique",
                review_flag=False,
                domains=p.domains,
                ranges=p.ranges,
                comment=p.comment,
                property_type=p.property_type,
                min_inclusive=p.min_inclusive,
                max_inclusive=p.max_inclusive,
            )

        # Case C: >= 2 survive -> Prompt LLM or Deterministic Fallback Arbiter
        if self.enable_llm and self.llm_client is not None:
            chosen = self._call_llm_reranker(column_name, column_role, sample_values, surviving_candidates)
            if chosen is not None:
                return chosen

        # Robust Deterministic Fallback Arbiter when LLM is offline/disabled or failed
        scored_survivors: List[Tuple[PropertyInfo, float]] = []
        for p, base_score in surviving_candidates:
            arb_score = self._deterministic_arbiter_score(
                prop=p,
                base_score=base_score,
                column_name=column_name,
                domain_restriction=domain_restriction,
                min_val=min_val,
                max_val=max_val,
            )
            scored_survivors.append((p, arb_score))

        scored_survivors.sort(key=lambda x: x[1], reverse=True)
        best_p, best_arb_score = scored_survivors[0]
        conf = min(0.85, max(0.65, round(best_arb_score, 2)))
        return MatchResult(
            uri=best_p.uri,
            label=best_p.label,
            confidence=conf,
            method="Arbiter-Reranked",
            review_flag=True,
            domains=best_p.domains,
            ranges=best_p.ranges,
            comment=best_p.comment,
            property_type=best_p.property_type,
            min_inclusive=best_p.min_inclusive,
            max_inclusive=best_p.max_inclusive,
        )

    def _deterministic_arbiter_score(
        self,
        prop: PropertyInfo,
        base_score: float,
        column_name: str,
        domain_restriction: Optional[Set[str]],
        min_val: Optional[float],
        max_val: Optional[float],
    ) -> float:
        """Deterministic Fallback Arbiter scoring surviving candidates based on:
        - Base match score
        - Domain match
        - Value bounds fit
        - Comment and alt_label token overlap
        """
        score = base_score

        # 1. Domain match bonus
        if domain_restriction and prop.domains:
            if any(d in domain_restriction for d in prop.domains):
                score += 0.20
        elif not prop.domains:
            score += 0.05

        # 2. Value bounds fit bonus
        if min_val is not None or max_val is not None:
            if prop.min_inclusive is not None or prop.max_inclusive is not None:
                # Survived _violates_bounds, so within declared bounds
                score += 0.20
                if (
                    min_val is not None
                    and prop.min_inclusive is not None
                    and max_val is not None
                    and prop.max_inclusive is not None
                ):
                    prop_span = prop.max_inclusive - prop.min_inclusive
                    data_span = max_val - min_val
                    if prop_span > 0 and 0 <= data_span <= prop_span:
                        tightness = data_span / prop_span
                        score += min(0.10, 0.10 * tightness)

        # 3. Comment and alt_label token overlap
        q_tokens = set(tokenize_string(column_name))
        if q_tokens:
            # Alt labels overlap
            alt_tokens: Set[str] = set()
            for alt in prop.alt_labels:
                alt_tokens.update(tokenize_string(alt))
            if alt_tokens:
                alt_overlap = len(q_tokens & alt_tokens) / len(q_tokens)
                score += 0.20 * alt_overlap

            # Comment overlap
            if prop.comment:
                c_tokens = set(tokenize_string(prop.comment))
                c_overlap = len(q_tokens & c_tokens) / len(q_tokens)
                score += 0.15 * c_overlap

        return score

    def _violates_axiom(self, prop: PropertyInfo, column_role: str) -> bool:
        """Deterministic Axiom Veto check.
        Returns True if the property's declared rdfs:range contradicts the column's role.
        """
        ranges = set(prop.ranges)
        if not ranges:
            # Open range: does not contradict
            return False

        # Role 1: Numeric property or Measurement
        if column_role in ("Numeric property", "Measurement value/unit pair"):
            # If property is an ObjectProperty without numeric datatype range -> veto
            if prop.property_type == "ObjectProperty":
                return True
            # If all declared ranges are strictly strings -> veto
            if all(r in STRING_RANGES for r in ranges):
                return True
            # If declared ranges are strictly temporal -> veto
            if all(r in TEMPORAL_RANGES for r in ranges):
                return True
            # If declared ranges are strictly boolean -> veto
            if all(r in BOOLEAN_RANGES for r in ranges):
                return True

        # Role 2: Categorical or Text
        elif column_role in ("Categorical", "Text"):
            # If all declared ranges are strictly numeric -> veto
            if all(r in NUMERIC_RANGES for r in ranges):
                return True
            # If all declared ranges are strictly temporal -> veto
            if all(r in TEMPORAL_RANGES for r in ranges):
                return True

        # Role 3: Timestamp
        elif column_role == "Timestamp":
            # If ranges declared, at least one should be temporal, or not strictly numeric/string
            if all(r in NUMERIC_RANGES for r in ranges):
                return True
            if all(r in BOOLEAN_RANGES for r in ranges):
                return True

        return False

    def _call_llm_reranker(
        self,
        column_name: str,
        column_role: str,
        sample_values: List[Any],
        candidates: List[Tuple[PropertyInfo, float]],
    ) -> Optional[MatchResult]:
        """Prompt LLM to choose among surviving candidates with full semantic context."""
        min_val, max_val = self._extract_numeric_summary(sample_values)
        samples_str = ", ".join([str(s) for s in sample_values[:5]])
        stats_parts = [f"Samples: [{samples_str}]"]
        if min_val is not None:
            stats_parts.append(f"Min: {min_val}")
        if max_val is not None:
            stats_parts.append(f"Max: {max_val}")
        stats_str = ", ".join(stats_parts)

        prompt = (
            f"Select the best ontology property for table column '{column_name}' (Role: {column_role}, {stats_str}).\n"
            "Candidates:\n"
        )
        for i, (p, score) in enumerate(candidates):
            domain_s = ", ".join(p.domains) if p.domains else "Any"
            range_s = ", ".join(p.ranges) if p.ranges else "Any"
            alts_s = ", ".join(p.alt_labels) if p.alt_labels else "None"
            bounds_s = (
                f"[{p.min_inclusive}, {p.max_inclusive}]"
                if (p.min_inclusive is not None or p.max_inclusive is not None)
                else "None"
            )
            comment_s = p.comment if p.comment else p.label
            prompt += (
                f"{i+1}. URI: {p.uri}\n"
                f"   Label: {p.label} (Synonyms: {alts_s})\n"
                f"   Domain: {domain_s} | Range: {range_s} | Bounds: {bounds_s}\n"
                f"   Comment: {comment_s}\n"
            )
        prompt += (
            "\nReply with the index number (1 to N) of the best property, followed by your confidence rating (HIGH, MEDIUM, or LOW).\n"
            "Format: <index> <rating>\n"
        )

        try:
            resp = self.llm_client(prompt).strip()
            # Extract index and confidence rating
            parts = resp.split()
            idx = int(parts[0]) - 1
            rating = parts[1].upper() if len(parts) > 1 else "MEDIUM"
            if 0 <= idx < len(candidates):
                p, _ = candidates[idx]
                conf_map = {"HIGH": 0.75, "MEDIUM": 0.65, "LOW": 0.55}
                conf = conf_map.get(rating, 0.65)
                return MatchResult(
                    uri=p.uri,
                    label=p.label,
                    confidence=conf,
                    method="LLM-Reranked",
                    review_flag=True,
                    domains=p.domains,
                    ranges=p.ranges,
                    comment=p.comment,
                    property_type=p.property_type,
                    min_inclusive=p.min_inclusive,
                    max_inclusive=p.max_inclusive,
                )
        except Exception:
            pass

        return None

    def _create_result(
        self,
        prop: PropertyInfo,
        confidence: float,
        method: str,
        review_flag: bool,
    ) -> MatchResult:
        return MatchResult(
            uri=prop.uri,
            label=prop.label,
            confidence=confidence,
            method=method,
            review_flag=review_flag,
            domains=prop.domains,
            ranges=prop.ranges,
            comment=prop.comment,
            property_type=prop.property_type,
            min_inclusive=prop.min_inclusive,
            max_inclusive=prop.max_inclusive,
        )
