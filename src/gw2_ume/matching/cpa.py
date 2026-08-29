"""Column Property Annotation (CPA) for tabular data in Guild Wars 2."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from gw2_ume.matching.models import (
    CellCandidateList,
    ColumnTypeCandidate,
    ColumnPropertyCandidate,
    TableGrid,
)
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner
from gw2_ume.retrieval.vector_index import VectorIndex, _lexical_similarity


class ColumnPropertyAnnotator:
    """Column Property Annotator (CPA) determining ObjectProperties linking column pairs."""

    def __init__(
        self,
        reasoner: SymbolicAxiomReasoner,
        vector_index: VectorIndex | None = None,
        domain_range_weight: float = 0.35,
        triple_support_weight: float = 0.45,
        header_weight: float = 0.20,
    ) -> None:
        """Initialize CPA with reasoner, vector index, and scoring weights."""
        self.reasoner = reasoner
        self.vector_index = vector_index
        self.domain_range_weight = domain_range_weight
        self.triple_support_weight = triple_support_weight
        self.header_weight = header_weight

    def annotate_column_pair(
        self,
        col_i: int,
        col_j: int,
        col_i_types: list[ColumnTypeCandidate],
        col_j_types: list[ColumnTypeCandidate],
        table_candidates: dict[tuple[int, int], CellCandidateList],
        num_rows: int,
        header_i: str = "",
        header_j: str = "",
        top_k: int = 5,
    ) -> list[ColumnPropertyCandidate]:
        """Annotate directed column pair (col_i -> col_j) with candidate object properties."""
        if col_i == col_j:
            return []

        top_type_i = col_i_types[0].class_iri if col_i_types else None
        top_type_j = col_j_types[0].class_iri if col_j_types else None

        all_properties = self.reasoner.get_all_properties()
        if not all_properties:
            return []

        # 1. Header similarity with property labels
        header_sims: dict[str, float] = defaultdict(float)
        query_text = f"{header_i} {header_j}".strip() or header_j.strip()
        if query_text and self.vector_index:
            prop_retrievals = self.vector_index.search_properties(query_text, top_k=10)
            for pr in prop_retrievals:
                header_sims[pr.iri] = pr.score
        elif query_text:
            for p in all_properties:
                labels = self.reasoner.get_property_labels(p)
                sim = max((_lexical_similarity(query_text, l) for l in labels), default=0.0)
                if sim > 0.1:
                    header_sims[p] = sim

        candidates: list[ColumnPropertyCandidate] = []

        for prop_iri in all_properties:
            domains = self.reasoner.get_expected_domains(prop_iri) if hasattr(self.reasoner, "get_expected_domains") else set()
            ranges = self.reasoner.get_expected_ranges(prop_iri) if hasattr(self.reasoner, "get_expected_ranges") else set()

            domain_iris = {str(d) for d in domains}
            range_iris = {str(r) for r in ranges}

            # 2. Domain & Range compatibility score
            domain_compat = True
            range_compat = True

            if domain_iris and top_type_i:
                domain_compat = any(self.reasoner.is_subclass_of(top_type_i, d) for d in domain_iris)
            if range_iris and top_type_j:
                range_compat = any(self.reasoner.is_subclass_of(top_type_j, r) for r in range_iris)

            if not domain_compat and not range_compat:
                dr_score = 0.0
            elif not domain_compat or not range_compat:
                dr_score = 0.3
            else:
                dr_score = 1.0

            # 3. Row-level factual triples support
            row_support_count = 0
            valid_rows = 0

            for r_idx in range(num_rows):
                cell_i = table_candidates.get((r_idx, col_i))
                cell_j = table_candidates.get((r_idx, col_j))

                if not cell_i or not cell_j or not cell_i.candidates or not cell_j.candidates:
                    continue

                valid_rows += 1
                has_support = False
                for ci in cell_i.candidates[:3]:
                    for cj in cell_j.candidates[:3]:
                        if self.reasoner.has_triple(ci.entity_iri, prop_iri, cj.entity_iri):
                            has_support = True
                            break
                        # Check connecting paths
                        paths = self.reasoner.find_connecting_paths(ci.entity_iri, cj.entity_iri, max_hops=2, directed=True)
                        if any(any(step[1] == self.reasoner.loader.resolve_iri(prop_iri) for step in p) for p in paths):
                            has_support = True
                            break
                    if has_support:
                        break

                if has_support:
                    row_support_count += 1

            row_support_ratio = (row_support_count / valid_rows) if valid_rows > 0 else 0.0

            # Header similarity score
            header_sim = header_sims.get(prop_iri, 0.0)

            # Combined confidence score
            confidence = (
                self.domain_range_weight * dr_score
                + self.triple_support_weight * row_support_ratio
                + self.header_weight * header_sim
            )

            # Boost if there is positive row support
            if row_support_ratio > 0.0:
                confidence = min(1.0, confidence + 0.3 * row_support_ratio)

            # Strict penalty if disjoint with domain or range
            if top_type_i and domain_iris and any(self.reasoner.are_disjoint(top_type_i, d) for d in domain_iris):
                confidence = 0.0
            if top_type_j and range_iris and any(self.reasoner.are_disjoint(top_type_j, r) for r in range_iris):
                confidence = 0.0

            labels = self.reasoner.get_property_labels(prop_iri)
            label = labels[0] if labels else prop_iri.split("#")[-1].split("/")[-1]
            dom_str = list(domain_iris)[0] if domain_iris else None
            rng_str = list(range_iris)[0] if range_iris else None

            candidates.append(
                ColumnPropertyCandidate(
                    property_iri=prop_iri,
                    property_label=label,
                    confidence=float(min(1.0, max(0.0, confidence))),
                    row_support_count=row_support_count,
                    row_support_ratio=float(row_support_ratio),
                    domain_iri=dom_str,
                    range_iri=rng_str,
                    header_similarity=float(header_sim),
                    metadata={"dr_score": dr_score},
                )
            )

        candidates.sort(
            key=lambda x: (x.confidence, x.row_support_ratio, x.row_support_count),
            reverse=True,
        )
        return candidates[:top_k]

    def annotate_table(
        self,
        table: TableGrid,
        column_types: dict[int, list[ColumnTypeCandidate]],
        table_candidates: dict[tuple[int, int], CellCandidateList],
        top_k: int = 5,
    ) -> dict[tuple[int, int], list[ColumnPropertyCandidate]]:
        """Annotate all pairs of columns in the table.

        Returns:
            Dictionary mapping (col_i, col_j) -> list of ColumnPropertyCandidate.
        """
        results: dict[tuple[int, int], list[ColumnPropertyCandidate]] = {}
        num_cols = table.num_cols

        for i in range(num_cols):
            for j in range(num_cols):
                if i == j:
                    continue
                header_i = table.headers[i] if i < len(table.headers) else ""
                header_j = table.headers[j] if j < len(table.headers) else ""

                types_i = column_types.get(i, [])
                types_j = column_types.get(j, [])

                results[(i, j)] = self.annotate_column_pair(
                    col_i=i,
                    col_j=j,
                    col_i_types=types_i,
                    col_j_types=types_j,
                    table_candidates=table_candidates,
                    num_rows=table.num_rows,
                    header_i=header_i,
                    header_j=header_j,
                    top_k=top_k,
                )

        return results
