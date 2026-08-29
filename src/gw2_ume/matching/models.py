"""Data models for Semantic Table Interpretation and Relational Mesh Matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CellCandidate:
    """A candidate entity or class binding for a table cell."""

    entity_iri: str
    label: str
    types: list[str] = field(default_factory=list)
    score: float = 0.0
    dense_score: float = 0.0
    lexical_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CellCandidateList:
    """Set of candidate entities for a table cell at (row_idx, col_idx)."""

    row_idx: int
    col_idx: int
    raw_text: str
    cleaned_text: str
    candidates: list[CellCandidate] = field(default_factory=list)

    @property
    def top_candidate(self) -> CellCandidate | None:
        return self.candidates[0] if self.candidates else None


@dataclass
class ColumnTypeCandidate:
    """Candidate ontology class type for a table column."""

    class_iri: str
    class_label: str
    confidence: float
    cell_support_ratio: float
    header_similarity: float = 0.0
    hierarchy_depth: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ColumnPropertyCandidate:
    """Candidate ontology object property connecting a pair of columns (col_i -> col_j)."""

    property_iri: str
    property_label: str
    confidence: float
    row_support_count: int
    row_support_ratio: float = 0.0
    domain_iri: str | None = None
    range_iri: str | None = None
    header_similarity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeshTriple:
    """Extracted knowledge graph triple from the relational mesh."""

    subject_iri: str
    subject_label: str
    predicate_iri: str
    predicate_label: str
    object_iri: str
    object_label: str
    row_idx: int
    subject_col: int
    object_col: int
    confidence: float = 1.0
    triple_origin: str = "direct_ontology"


@dataclass
class TableGrid:
    """Tabular structure with optional headers and rectangular row matrix."""

    headers: list[str]
    rows: list[list[str]]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        if self.headers:
            return len(self.headers)
        if self.rows and len(self.rows) > 0:
            return len(self.rows[0])
        return 0

    def get_cell(self, row_idx: int, col_idx: int) -> str:
        if 0 <= row_idx < len(self.rows) and 0 <= col_idx < len(self.rows[row_idx]):
            return self.rows[row_idx][col_idx]
        return ""


@dataclass
class TableInterpretationMesh:
    """Final solved semantic table interpretation mesh."""

    table: TableGrid
    cell_annotations: dict[tuple[int, int], CellCandidate] = field(default_factory=dict)
    column_types: dict[int, ColumnTypeCandidate] = field(default_factory=dict)
    column_relations: dict[tuple[int, int], ColumnPropertyCandidate] = field(default_factory=dict)
    row_triples: list[MeshTriple] = field(default_factory=list)
    overall_confidence: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    solver_log: list[str] = field(default_factory=list)
