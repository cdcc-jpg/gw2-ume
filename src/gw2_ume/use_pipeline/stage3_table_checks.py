"""Stage 3: Whole-Table Sanity Passes.

Zero Domain Semantics in Python: Operates dynamically on RDF graph structure and column distributions.
Implements:
- 3a: Table-Domain Majority Vote:
  - Resolve every column's predicate once through Stage 5 cascade.
  - Tally rdfs:domain votes from confident matches (confidence >= 0.70).
  - Re-probe outlier columns restricted to majority domain properties.
- 3b: Sub-Entity Anchor Detection:
  - Detect non-entity columns with ID-shaped values.
  - Group by shared column name prefix (e.g. SOLUTE_ID + SOLUTE_SMILES_FORMULA, TASK_ID + TASK_NAME).
  - If sibling column maps to a confident property: activate column as an Anchor.
  - Sibling columns are routed to attach to this anchor's row value!
- 3c: Subject-Link Resolution:
  - Checks declared owl:ObjectProperty in the ontology between primary domain and anchor domains.
  - Registers subject-link property to emit per row with method Schema-Driven-SubjectLink.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from rdflib import URIRef

from gw2_ume.use_pipeline.stage0_setup import OntologyIndex, normalize_string
from gw2_ume.use_pipeline.stage2_classification import ColumnRole
from gw2_ume.use_pipeline.stage5_cascade import MatchResult, PredicateResolver


@dataclass
class AnchorInfo:
    """Activated sub-entity anchor metadata."""
    anchor_col: str
    prefix: str
    sibling_cols: List[str] = field(default_factory=list)
    anchor_domain: Optional[str] = None
    link_property_uri: Optional[str] = None
    link_property_label: Optional[str] = None


@dataclass
class TableCheckContext:
    """Results of whole-table checks used during row execution."""
    primary_entity_col: Optional[str]
    majority_domain: Optional[str]
    column_predicates: Dict[str, MatchResult]
    anchors: Dict[str, AnchorInfo]  # anchor_col -> AnchorInfo
    col_to_anchor: Dict[str, str]   # sibling_col -> anchor_col


class TableChecker:
    """Executes Stages 3a, 3b, and 3c on a table."""

    def __init__(self, ontology_index: OntologyIndex, resolver: PredicateResolver):
        self.index = ontology_index
        self.resolver = resolver

    def analyze_table(
        self,
        df: pd.DataFrame,
        column_roles: Dict[str, ColumnRole],
    ) -> TableCheckContext:
        """Runs 3a, 3b, and 3c passes over the table."""
        # 1. Initial resolution for all columns
        raw_predicates: Dict[str, MatchResult] = {}
        for col, r in column_roles.items():
            if r.role == "Skip":
                continue
            sample_vals = r.stats.sample_values
            match = self.resolver.resolve(col, r.role, sample_vals)
            raw_predicates[col] = match

        # Step 3a: Table-Domain Majority Vote
        majority_domain, column_predicates = self._stage_3a_domain_majority_vote(
            column_roles, raw_predicates
        )

        # Identify primary entity column
        primary_entity_col = None
        for col, r in column_roles.items():
            if r.role == "Entity ID":
                primary_entity_col = col
                break

        # Step 3b: Sub-Entity Anchor Detection
        anchors, col_to_anchor = self._stage_3b_anchor_detection(
            column_roles, column_predicates, primary_entity_col
        )

        # Step 3c: Subject-Link Resolution
        self._stage_3c_subject_link_resolution(majority_domain, anchors)

        return TableCheckContext(
            primary_entity_col=primary_entity_col,
            majority_domain=majority_domain,
            column_predicates=column_predicates,
            anchors=anchors,
            col_to_anchor=col_to_anchor,
        )

    def _stage_3a_domain_majority_vote(
        self,
        column_roles: Dict[str, ColumnRole],
        predicates: Dict[str, MatchResult],
    ) -> Tuple[Optional[str], Dict[str, MatchResult]]:
        """Stage 3a: Tally rdfs:domain votes from confident matches (>= 0.70)
        and re-probe outlier columns restricted to the majority domain.
        """
        domain_votes: Counter[str] = Counter()
        for col, m in predicates.items():
            if m.confidence >= 0.70 and m.domains:
                for d in m.domains:
                    domain_votes[d] += 1

        if not domain_votes:
            return None, dict(predicates)

        majority_domain, _ = domain_votes.most_common(1)[0]
        majority_set = {majority_domain}

        # Include subclasses of majority domain recursively
        majority_set = {majority_domain}
        majority_set.update(self.index.get_subclasses(majority_domain, recursive=True))

        # Re-probe outlier columns
        # Re-probe columns with domain restriction to prioritize properties of the majority domain
        adjusted_predicates = dict(predicates)
        for col, m in predicates.items():
            r = column_roles.get(col)
            if not r or r.role == "Skip":
                continue
            needs_reprobe = bool(m.domains and majority_domain not in m.domains)
            if needs_reprobe:
                reprobe_match = self.resolver.resolve(
                    col, r.role, r.stats.sample_values, domain_restriction={majority_domain}
                )
                if reprobe_match and reprobe_match.confidence >= 0.55:
                    if majority_domain in reprobe_match.domains or reprobe_match.confidence >= m.confidence:
                        adjusted_predicates[col] = reprobe_match

        return majority_domain, adjusted_predicates

    def _stage_3b_anchor_detection(
        self,
        column_roles: Dict[str, ColumnRole],
        predicates: Dict[str, MatchResult],
        primary_entity_col: Optional[str],
    ) -> Tuple[Dict[str, AnchorInfo], Dict[str, str]]:
        """Stage 3b: Sub-Entity Anchor Detection.
        - Detect non-entity columns with ID-shaped values.
        - Group by shared column name prefix.
        - If sibling column maps to a confident property: activate column as an Anchor.
        """
        # Find candidate anchor columns: ID-shaped, not primary entity ID
        candidate_anchor_cols: List[str] = []
        for col, r in column_roles.items():
            if col == primary_entity_col:
                continue
            if r.role in ("Foreign Key", "Entity ID") or r.stats.id_shape_ratio >= 0.70:
                candidate_anchor_cols.append(col)

        anchors: Dict[str, AnchorInfo] = {}
        col_to_anchor: Dict[str, str] = {}

        all_cols = list(column_roles.keys())

        for anchor_col in candidate_anchor_cols:
            # Extract common prefix (e.g. SOLUTE from SOLUTE_ID, TASK from TASK_ID)
            parts = re.split(r"[_ -]+", anchor_col)
            if not parts:
                continue

            # Candidate prefixes: first token or all tokens up to ID
            prefix_candidates = [parts[0]]
            if len(parts) > 1 and parts[-1].upper() in ("ID", "CODE", "KEY", "IDENTIFIER"):
                prefix_candidates.append("_".join(parts[:-1]))

            best_prefix = max(prefix_candidates, key=len)

            # Find sibling columns with matching prefix
            siblings: List[str] = []
            for col in all_cols:
                if col != anchor_col and col != primary_entity_col:
                    if col.upper().startswith(best_prefix.upper()):
                        siblings.append(col)

            # If at least one sibling exists and maps to a property, activate anchor
            if siblings:
                anchor_domains = set()
                for sib in siblings:
                    p_match = predicates.get(sib)
                    if p_match and p_match.domains:
                        anchor_domains.update(p_match.domains)

                anchor_dom = list(anchor_domains)[0] if anchor_domains else None
                anchor_info = AnchorInfo(
                    anchor_col=anchor_col,
                    prefix=best_prefix,
                    sibling_cols=siblings,
                    anchor_domain=anchor_dom,
                )
                anchors[anchor_col] = anchor_info
                for sib in siblings:
                    col_to_anchor[sib] = anchor_col

        return anchors, col_to_anchor

    def _stage_3c_subject_link_resolution(
        self,
        majority_domain: Optional[str],
        anchors: Dict[str, AnchorInfo],
    ) -> None:
        """Stage 3c: Subject-Link Resolution.
        Checks declared owl:ObjectProperty in the ontology between primary domain and anchor domains.
        """
        for anchor_col, info in anchors.items():
            link_prop = self._find_object_property_link(majority_domain, info.anchor_domain, info.prefix)
            if link_prop:
                info.link_property_uri = link_prop.uri
                info.link_property_label = link_prop.label
            else:
                # Dynamic fallback link based on prefix
                clean_prefix = info.prefix.strip("_ ")
                dynamic_label = f"has {clean_prefix}"
                info.link_property_uri = f"urn:priory:has_{clean_prefix.lower()}"
                info.link_property_label = dynamic_label

    def _find_object_property_link(
        self,
        source_domain: Optional[str],
        target_domain: Optional[str],
        prefix_hint: str,
    ) -> Optional[Any]:
        """Find an owl:ObjectProperty linking source domain to target domain,
        or matching the prefix hint.
        """
        prefix_norm = normalize_string(prefix_hint)

        for p in self.index.properties.values():
            if p.property_type != "ObjectProperty":
                continue

            # Check domain and range match
            if source_domain and target_domain:
                has_src = not p.domains or source_domain in p.domains
                has_tgt = not p.ranges or target_domain in p.ranges
                if has_src and has_tgt:
                    return p

            # Check label match against prefix hint
            p_norm = normalize_string(p.label)
            if prefix_norm in p_norm or f"has{prefix_norm}" in p_norm:
                return p

        return None
