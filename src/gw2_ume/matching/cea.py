"""Cell Entity Annotation (CEA) for tabular data in Guild Wars 2."""

from __future__ import annotations

from typing import Iterable
from gw2_ume.matching.models import CellCandidate, CellCandidateList, TableGrid
from gw2_ume.matching.cleaning import clean_cell_text
from gw2_ume.retrieval.vector_index import VectorIndex, RetrievalResult
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner


class CellEntityAnnotator:
    """Cell Entity Annotator (CEA) matching table cells to ontology entities/classes."""

    def __init__(
        self,
        vector_index: VectorIndex,
        reasoner: SymbolicAxiomReasoner | None = None,
        alpha: float = 0.6,
        beta: float = 0.4,
    ) -> None:
        """Initialize CEA with vector index, optional reasoner, and scoring weights.

        Args:
            vector_index: Vector and lexical index.
            reasoner: Optional Symbolic Axiom Reasoner.
            alpha: Weight for dense cosine similarity.
            beta: Weight for lexical similarity.
        """
        self.vector_index = vector_index
        self.reasoner = reasoner
        self.alpha = alpha
        self.beta = beta

    def annotate_cell(
        self,
        raw_text: str,
        row_idx: int,
        col_idx: int,
        top_k: int = 5,
        type_filter: str | None = None,
    ) -> CellCandidateList:
        """Annotate a single cell string and return top-K ranked candidates."""
        cleaned = clean_cell_text(raw_text)

        if not cleaned:
            # Empty or non-textual cell
            return CellCandidateList(
                row_idx=row_idx,
                col_idx=col_idx,
                raw_text=raw_text,
                cleaned_text=cleaned,
                candidates=[],
            )

        # Query vector index
        raw_results: list[RetrievalResult] = self.vector_index.search_entities(
            query=cleaned,
            top_k=top_k * 2,  # retrieve extra for type filtering/re-ranking
            type_filter=type_filter,
            alpha=self.alpha,
            beta=self.beta,
        )

        candidates: list[CellCandidate] = []
        for r in raw_results:
            types = list(r.types)
            meta = dict(r.metadata)
            if self.reasoner:
                expanded_types: set[str] = set(types)
                for t in types:
                    expanded_types.update(self.reasoner.get_superclasses(t, include_self=True))
                meta["superclasses"] = list(expanded_types)

            cand = CellCandidate(
                entity_iri=r.iri,
                label=r.label,
                types=types,
                score=r.score,
                dense_score=r.dense_score,
                lexical_score=r.lexical_score,
                metadata=meta,
            )
            candidates.append(cand)

        # If no entity candidates found, try searching classes as fallback
        if not candidates:
            class_results = self.vector_index.search_classes(
                query=cleaned,
                top_k=top_k,
                alpha=self.alpha,
                beta=self.beta,
            )
            for cr in class_results:
                cand = CellCandidate(
                    entity_iri=cr.iri,
                    label=cr.label,
                    types=[cr.iri],
                    score=cr.score * 0.9,  # slight discount for class-as-entity
                    dense_score=cr.dense_score,
                    lexical_score=cr.lexical_score,
                    metadata=cr.metadata,
                )
                candidates.append(cand)

        candidates.sort(key=lambda c: c.score, reverse=True)
        top_candidates = candidates[:top_k]

        return CellCandidateList(
            row_idx=row_idx,
            col_idx=col_idx,
            raw_text=raw_text,
            cleaned_text=cleaned,
            candidates=top_candidates,
        )

    def annotate_table(
        self,
        table: TableGrid | list[list[str]],
        top_k: int = 5,
    ) -> dict[tuple[int, int], CellCandidateList]:
        """Annotate all cells in a table grid.

        Returns:
            Dictionary mapping (row_idx, col_idx) to CellCandidateList.
        """
        rows = table.rows if isinstance(table, TableGrid) else table
        results: dict[tuple[int, int], CellCandidateList] = {}

        for r_idx, row in enumerate(rows):
            for c_idx, cell_value in enumerate(row):
                cand_list = self.annotate_cell(
                    raw_text=cell_value,
                    row_idx=r_idx,
                    col_idx=c_idx,
                    top_k=top_k,
                )
                results[(r_idx, c_idx)] = cand_list

        return results
