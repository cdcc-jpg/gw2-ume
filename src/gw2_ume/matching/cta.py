"""Column Type Annotation (CTA) for tabular data in Guild Wars 2."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from gw2_ume.matching.models import (
    CellCandidateList,
    ColumnTypeCandidate,
    TableGrid,
)
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner
from gw2_ume.retrieval.vector_index import (
    VectorIndex,
    _lexical_similarity,
    get_default_vector_index,
)


class ColumnTypeAnnotator:
    """Column Type Annotator (CTA) inferring ontology classes for table columns."""

    def __init__(
        self,
        reasoner: SymbolicAxiomReasoner | None = None,
        vector_index: VectorIndex | None = None,
        voting_weight: float = 0.40,
        hierarchy_weight: float = 0.40,
        header_weight: float = 0.20,
    ) -> None:
        """Initialize CTA with reasoner, vector index, and weighting parameters."""
        self.reasoner = reasoner if reasoner is not None else SymbolicAxiomReasoner()
        self.vector_index = vector_index if vector_index is not None else get_default_vector_index()
        self.voting_weight = voting_weight
        self.hierarchy_weight = hierarchy_weight
        self.header_weight = header_weight

    def annotate_column(
        self,
        col_idx: int,
        header: str,
        cell_candidate_lists: list[CellCandidateList],
        top_k: int = 5,
    ) -> list[ColumnTypeCandidate]:
        """Annotate a single column with candidate ontology types.

        Args:
            col_idx: Index of the column.
            header: Header label string for the column (may be empty).
            cell_candidate_lists: List of CellCandidateList for each row in this column.
            top_k: Number of top candidate classes to return.
        """
        valid_cells = [c for c in cell_candidate_lists if c.cleaned_text and c.candidates]
        num_valid_cells = len(valid_cells)

        # 1. Candidate Class Voting across cells
        class_votes: dict[str, float] = defaultdict(float)
        cell_types_per_row: list[set[str]] = []

        for cell_list in valid_cells:
            row_types: set[str] = set()
            for cand in cell_list.candidates[:3]:
                for t in cand.types:
                    row_types.add(t)
                    class_votes[t] += cand.score

                    # Add superclasses with decayed vote
                    supers = self.reasoner.get_superclasses(t, include_self=False)
                    for s in supers:
                        if s not in ("http://www.w3.org/2002/07/owl#Thing", "owl:Thing"):
                            row_types.add(s)
                            class_votes[s] += cand.score * 0.6
            cell_types_per_row.append(row_types)

        # 2. Least Common Subsumer (LCS) analysis
        all_direct_leaf_types: list[str] = []
        for cell_list in valid_cells:
            if cell_list.top_candidate and cell_list.top_candidate.types:
                all_direct_leaf_types.extend(cell_list.top_candidate.types)

        lcs_class = self.reasoner.find_least_common_subsumer(all_direct_leaf_types) if all_direct_leaf_types else None
        if lcs_class:
            class_votes[lcs_class] += 3.0  # High LCS boost

        # 3. Header Similarity Match
        header_sims: dict[str, float] = defaultdict(float)
        if header.strip() and self.vector_index:
            class_retrievals = self.vector_index.search_classes(header, top_k=10)
            for cr in class_retrievals:
                header_sims[cr.iri] = cr.score
        elif header.strip():
            for cls in self.reasoner.get_all_classes():
                labels = self.reasoner.get_class_labels(cls)
                sim = max((_lexical_similarity(header, l) for l in labels), default=0.0)
                if sim > 0.1:
                    header_sims[cls] = sim

        # 4. Score Aggregation
        candidate_classes = set(class_votes.keys()).union(header_sims.keys())
        if not candidate_classes:
            candidate_classes = set(self.reasoner.get_all_classes())

        # Exclude root owl:Thing from being top class unless table has no type
        candidate_classes.discard("http://www.w3.org/2002/07/owl#Thing")
        candidate_classes.discard("owl:Thing")

        max_vote = max(class_votes.values()) if class_votes else 1.0
        max_depth = max((self.reasoner.get_class_depth(c) for c in candidate_classes), default=1)
        max_depth = max(1, max_depth)

        scored_candidates: list[ColumnTypeCandidate] = []

        for cls in candidate_classes:
            # Cell support ratio
            if num_valid_cells > 0:
                supporting_rows = sum(
                    1 for row_types in cell_types_per_row
                    if any(self.reasoner.is_subclass_of(t, cls) for t in row_types)
                )
                cell_support_ratio = supporting_rows / num_valid_cells
            else:
                cell_support_ratio = 0.0

            normalized_vote = (class_votes.get(cls, 0.0) / max_vote) if max_vote > 0 else 0.0
            header_sim = header_sims.get(cls, 0.0)
            depth = self.reasoner.get_class_depth(cls)

            # Specificity bonus: Prefer most specific classes covering all cells
            specificity = 0.5 + 0.5 * (depth / max_depth)

            confidence = (
                self.voting_weight * normalized_vote
                + self.hierarchy_weight * (cell_support_ratio * specificity)
                + self.header_weight * header_sim
            )

            # Bonus for LCS class
            if lcs_class and cls == lcs_class:
                confidence = min(1.0, confidence + 0.25)

            # Penalize classes with low cell support
            if cell_support_ratio < 0.5:
                confidence *= 0.5

            labels = self.reasoner.get_class_labels(cls)
            label = labels[0] if labels else cls.split("#")[-1].split("/")[-1]

            scored_candidates.append(
                ColumnTypeCandidate(
                    class_iri=cls,
                    class_label=label,
                    confidence=float(min(1.0, max(0.0, confidence))),
                    cell_support_ratio=float(cell_support_ratio),
                    header_similarity=float(header_sim),
                    hierarchy_depth=depth,
                    metadata={"raw_votes": class_votes.get(cls, 0.0)},
                )
            )

        scored_candidates.sort(
            key=lambda x: (x.confidence, x.cell_support_ratio, x.hierarchy_depth),
            reverse=True,
        )
        return scored_candidates[:top_k]

    def annotate_table(
        self,
        table: TableGrid,
        cell_candidates_map: dict[tuple[int, int], CellCandidateList],
        top_k: int = 5,
    ) -> dict[int, list[ColumnTypeCandidate]]:
        """Annotate all columns in the table grid.

        Returns:
            Dictionary mapping col_idx -> list of ColumnTypeCandidate.
        """
        results: dict[int, list[ColumnTypeCandidate]] = {}

        for col_idx in range(table.num_cols):
            header = table.headers[col_idx] if col_idx < len(table.headers) else ""
            col_cell_lists = [
                cell_candidates_map.get((r_idx, col_idx), CellCandidateList(r_idx, col_idx, "", ""))
                for r_idx in range(table.num_rows)
            ]
            results[col_idx] = self.annotate_column(
                col_idx=col_idx,
                header=header,
                cell_candidate_lists=col_cell_lists,
                top_k=top_k,
            )

        return results
