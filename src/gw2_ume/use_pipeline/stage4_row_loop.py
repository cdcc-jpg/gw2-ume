"""Stage 4: Row Execution Loop.

Zero Domain Semantics in Python: Dynamic subject resolution, anchor swapping, and domain conflict checking.
Implements:
- For each row:
  - Primary subject is entity ID column value (or Row-N if none).
  - If column routed to sub-entity anchor -> swap subject to anchor's row value!
  - Build role-shaped triples using Stage 5 (predicate), Stage 6 (object), Stage 7 (trust score).
  - Check row's resolved domains for contradictions -> flag Row_Type_Conflict.
  - Emit Stage 3c subject-link triples: primary/anchor subject <-> anchor subject,
    method Schema-Driven-SubjectLink.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from gw2_ume.use_pipeline.stage0_setup import OntologyIndex
from gw2_ume.use_pipeline.stage2_classification import ColumnRole
from gw2_ume.use_pipeline.stage3_table_checks import TableCheckContext
from gw2_ume.use_pipeline.stage5_cascade import MatchResult, PredicateResolver
from gw2_ume.use_pipeline.stage6_object_resolution import ObjectResolver
from gw2_ume.use_pipeline.stage7_trust_scoring import TrustScorer


@dataclass
class Triple:
    """Emitted RDF triple with confidence, derivation method, review flag, and module action."""
    subject: str
    predicate: str
    object: str
    confidence: float
    method: str
    review_flag: bool
    module_action: str
    row_idx: int
    column_name: str


class RowLoopExecutor:
    """Stage 4 Row Loop Executor."""

    def __init__(
        self,
        ontology_index: OntologyIndex,
        predicate_resolver: PredicateResolver,
        object_resolver: Optional[ObjectResolver] = None,
        trust_scorer: Optional[TrustScorer] = None,
    ):
        self.index = ontology_index
        self.resolver = predicate_resolver
        self.object_resolver = object_resolver or ObjectResolver(ontology_index)
        self.trust_scorer = trust_scorer or TrustScorer()

    def execute_table(
        self,
        df: pd.DataFrame,
        column_roles: Dict[str, ColumnRole],
        table_context: TableCheckContext,
    ) -> List[Triple]:
        """Iterates over each row of the table, generating triples, routing anchors,
        detecting domain conflicts, and emitting Schema-Driven-SubjectLink triples.
        """
        triples: List[Triple] = []
        primary_id_col = table_context.primary_entity_col

        for row_idx, row in df.iterrows():
            # 1. Determine primary subject for this row
            if primary_id_col and pd.notna(row[primary_id_col]) and str(row[primary_id_col]).strip():
                primary_subject = str(row[primary_id_col]).strip()
            else:
                primary_subject = f"Row-{row_idx + 1}"

            row_primary_domains: List[Tuple[str, str]] = []  # (column_name, domain_uri)
            row_triples: List[Triple] = []

            # 2. Iterate over columns to build role-shaped triples
            for col in df.columns:
                col_role = column_roles.get(col)
                if not col_role or col_role.role == "Skip":
                    continue

                cell_val = row[col]
                if pd.isna(cell_val) or cell_val is None:
                    continue
                val_str = str(cell_val).strip()
                if not val_str or val_str.lower() in ("nan", "none", "null"):
                    continue

                # Check if this column is routed to a sub-entity anchor
                anchor_col = table_context.col_to_anchor.get(col)
                if anchor_col is not None and anchor_col in df.columns:
                    # SWAP SUBJECT to anchor's row value!
                    anchor_val = row[anchor_col]
                    if pd.notna(anchor_val) and str(anchor_val).strip():
                        current_subject = str(anchor_val).strip()
                    else:
                        current_subject = primary_subject
                    is_anchored = True
                else:
                    current_subject = primary_subject
                    is_anchored = False

                # Predicate resolution (from Stage 3 cached context or fresh cascade)
                pred_match = table_context.column_predicates.get(col)
                if pred_match is None:
                    pred_match = self.resolver.resolve(
                        col, col_role.role, col_role.stats.sample_values
                    )

                # Track domains for primary subject to check for contradictions
                if not is_anchored and pred_match.domains:
                    for d in pred_match.domains:
                        row_primary_domains.append((col, d))

                # Object resolution (Stage 6)
                obj_result = self.object_resolver.resolve(
                    cell_val, col_role.role, target_ranges=pred_match.ranges
                )

                # Trust scoring (Stage 7)
                trust_score = self.trust_scorer.score_triple(pred_match, obj_result)

                # Determine derivation method
                derivation_method = pred_match.method
                if obj_result.is_concept:
                    derivation_method = f"{pred_match.method}+{obj_result.method}"

                triple = Triple(
                    subject=current_subject,
                    predicate=pred_match.uri,
                    object=obj_result.resolved_value,
                    confidence=trust_score.confidence,
                    method=derivation_method,
                    review_flag=trust_score.review_flag,
                    module_action=trust_score.module_action,
                    row_idx=int(row_idx),
                    column_name=col,
                )
                row_triples.append(triple)

            # 3. Check row's resolved domains for contradictions -> flag Row_Type_Conflict
            self._check_and_flag_domain_conflicts(row_primary_domains, row_triples)

            # 4. Emit Stage 3c subject-link triples: primary <-> anchor
            link_triples = self._emit_subject_link_triples(
                row=row,
                primary_subject=primary_subject,
                row_idx=int(row_idx),
                table_context=table_context,
            )
            row_triples.extend(link_triples)

            triples.extend(row_triples)

        return triples

    def _check_and_flag_domain_conflicts(
        self,
        domain_assignments: List[Tuple[str, str]],
        triples: List[Triple],
    ) -> None:
        """Checks for pairwise disjoint domain contradictions on the primary subject.
        If a contradiction is discovered dynamically in the ontology, flags Row_Type_Conflict.
        """
        conflicting_cols: Set[str] = set()
        n = len(domain_assignments)
        for i in range(n):
            col_i, dom_i = domain_assignments[i]
            for j in range(i + 1, n):
                col_j, dom_j = domain_assignments[j]
                if self.index.are_classes_disjoint(dom_i, dom_j):
                    conflicting_cols.add(col_i)
                    conflicting_cols.add(col_j)

        if conflicting_cols:
            for t in triples:
                if t.column_name in conflicting_cols:
                    t.review_flag = True
                    t.method = f"{t.method}+Row_Type_Conflict"
                    t.module_action = "HITL Validation"

    def _emit_subject_link_triples(
        self,
        row: pd.Series,
        primary_subject: str,
        row_idx: int,
        table_context: TableCheckContext,
    ) -> List[Triple]:
        """Emits Stage 3c Schema-Driven-SubjectLink triples connecting primary subject to anchors."""
        link_triples = []
        for anchor_col, anchor_info in table_context.anchors.items():
            if anchor_col not in row:
                continue
            anchor_val = row[anchor_col]
            if pd.isna(anchor_val) or not str(anchor_val).strip():
                continue

            anchor_subj = str(anchor_val).strip()
            if anchor_subj == primary_subject:
                # Do not emit self-links
                continue

            link_prop_uri = anchor_info.link_property_uri or f"urn:priory:has_{anchor_info.prefix.lower()}"

            link_triple = Triple(
                subject=primary_subject,
                predicate=link_prop_uri,
                object=anchor_subj,
                confidence=0.95,
                method="Schema-Driven-SubjectLink",
                review_flag=False,
                module_action="Deterministic Mapped",
                row_idx=row_idx,
                column_name=f"{primary_subject}->{anchor_col}",
            )
            link_triples.append(link_triple)

        return link_triples
