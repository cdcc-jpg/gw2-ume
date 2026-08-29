"""Core data models for GW2-UME (Universal Match Engine).

Defines structured representations for tables, entity mentions, candidate
interpretations, diagnostic conflicts, interpretation meshes, and RDF triples.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class TableGrid:
    """Structured 2D grid representation of a table."""

    headers: List[str]
    rows: List[List[str]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> Tuple[int, int]:
        """Return (number of rows, number of columns)."""
        num_rows = len(self.rows)
        num_cols = len(self.headers) if self.headers else (len(self.rows[0]) if num_rows > 0 else 0)
        return num_rows, num_cols

    def cell(self, row_idx: int, col_idx: int) -> str:
        """Get cell string at (row_idx, col_idx) safely."""
        if 0 <= row_idx < len(self.rows):
            row = self.rows[row_idx]
            if 0 <= col_idx < len(row):
                return row[col_idx]
        return ""

    def get_column(self, col_identifier: Union[int, str]) -> List[str]:
        """Retrieve all values in a column by index or header name."""
        if isinstance(col_identifier, str):
            if col_identifier in self.headers:
                col_idx = self.headers.index(col_identifier)
            else:
                col_idx = -1
        else:
            col_idx = col_identifier

        if col_idx < 0:
            return []

        col_values = []
        for row in self.rows:
            if 0 <= col_idx < len(row):
                col_values.append(row[col_idx])
            else:
                col_values.append("")
        return col_values

    def to_dict(self) -> Dict[str, Any]:
        """Serialize TableGrid to dictionary."""
        return {
            "headers": self.headers,
            "rows": self.rows,
            "shape": list(self.shape),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TableGrid:
        """Instantiate TableGrid from dictionary."""
        headers = list(data.get("headers", []))
        rows = [list(r) for r in data.get("rows", [])]
        metadata = dict(data.get("metadata", {}))
        return cls(headers=headers, rows=rows, metadata=metadata)

    def to_markdown(self) -> str:
        """Convert table grid back into standard markdown table syntax."""
        if not self.headers and not self.rows:
            return ""
        
        headers = self.headers if self.headers else [f"Col_{i+1}" for i in range(self.shape[1])]
        col_widths = [len(h) for h in headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
                else:
                    col_widths.append(len(str(cell)))

        # Header row
        header_cells = [f" {h.ljust(col_widths[i])} " for i, h in enumerate(headers)]
        header_line = "|" + "|".join(header_cells) + "|"

        # Divider line
        div_cells = [f":{'-' * max(3, col_widths[i])}:" for i in range(len(headers))]
        div_line = "|" + "|".join(div_cells) + "|"

        # Rows
        row_lines = []
        for row in self.rows:
            padded_row = list(row) + [""] * (len(headers) - len(row))
            row_cells = [f" {str(padded_row[i]).ljust(col_widths[i])} " for i in range(len(headers))]
            row_lines.append("|" + "|".join(row_cells) + "|")

        return "\n".join([header_line, div_line] + row_lines)

    def to_csv(self, delimiter: str = ",") -> str:
        """Convert table to CSV string."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        if self.headers:
            writer.writerow(self.headers)
        for row in self.rows:
            writer.writerow(row)
        return output.getvalue()


@dataclass
class EntitySpan:
    """An extracted entity mention span from unstructured text."""

    text: str
    start_char: int
    end_char: int
    sentence_idx: int = 0
    normalized_text: str = ""
    entity_id: Optional[str] = None
    candidate_types: List[str] = field(default_factory=list)
    quantity: Optional[Union[float, int]] = None
    unit: Optional[str] = None
    confidence: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CellMention:
    """Entity mention located inside a specific table cell."""

    row_idx: int
    col_idx: int
    raw_text: str
    normalized_text: str
    entity_id: Optional[str] = None
    entity_type: str = "Unknown"
    quantity: Optional[Union[float, int]] = None
    unit: Optional[str] = None
    confidence: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableColumnInterpretation:
    """Predicted schema interpretation for a table column."""

    column_index: int
    column_name: str
    predicted_type: str  # e.g., 'CraftingMaterial', 'Weapon', 'Currency', 'Quantity'
    role: str = "attribute"  # 'subject', 'predicate', 'object', 'quantity', 'cost', 'ingredient', 'reward'
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RowRelation:
    """Extracted relationship between table cells in a row or from text."""

    row_idx: int
    subject: str
    predicate: str
    object: str
    quantity: Optional[Union[float, int]] = None
    unit: Optional[str] = None
    confidence: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosticConflict:
    """A symbolic conflict or axiom violation flagged during reasoning."""

    conflict_type: str  # 'DOMAIN_VIOLATION', 'RANGE_VIOLATION', 'TYPE_INCOMPATIBILITY', 'UNGROUNDED_ENTITY', etc.
    message: str
    severity: str = "ERROR"  # 'ERROR', 'WARNING', 'INFO'
    target_col: Optional[int] = None
    target_row: Optional[int] = None
    offending_value: Any = None
    suggested_fix: Optional[str] = None
    rule_or_axiom: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def format_diagnostic(self) -> str:
        """Format conflict into readable diagnostic string for LLM feedback."""
        parts = [f"[{self.severity}:{self.conflict_type}] {self.message}"]
        if self.target_col is not None:
            parts.append(f"Target Column: {self.target_col}")
        if self.target_row is not None:
            parts.append(f"Target Row: {self.target_row}")
        if self.offending_value is not None:
            parts.append(f"Offending Value: '{self.offending_value}'")
        if self.rule_or_axiom:
            parts.append(f"Axiom: {self.rule_or_axiom}")
        if self.suggested_fix:
            parts.append(f"Suggested Fix: {self.suggested_fix}")
        return " | ".join(parts)


@dataclass
class CandidateTableInterpretation:
    """Neural proposal for table structure and row semantics."""

    columns: List[TableColumnInterpretation]
    table_type: str = "Unknown"  # 'CraftingRecipe', 'MysticForgeRecipe', 'VendorCost', 'DropTable', etc.
    subject_entity: Optional[str] = None
    subject_column_idx: Optional[int] = None
    row_relations: List[RowRelation] = field(default_factory=list)
    cell_mentions: List[CellMention] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "columns": [c.to_dict() for c in self.columns],
            "table_type": self.table_type,
            "subject_entity": self.subject_entity,
            "subject_column_idx": self.subject_column_idx,
            "row_relations": [r.to_dict() for r in self.row_relations],
            "cell_mentions": [m.to_dict() for m in self.cell_mentions],
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class RefinedProposal:
    """Refined proposal produced after incorporating symbolic feedback."""

    interpretation: CandidateTableInterpretation
    adjustments_made: List[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interpretation": self.interpretation.to_dict(),
            "adjustments_made": self.adjustments_made,
            "rationale": self.rationale,
        }


@dataclass
class TableInterpretationMesh:
    """Fully resolved and grounded knowledge mesh for a table."""

    table_id: str
    table_type: str
    subject_entity: Optional[str]
    columns: List[TableColumnInterpretation]
    row_relations: List[RowRelation]
    cell_mentions: List[CellMention]
    triples: List[Tuple[str, str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "table_type": self.table_type,
            "subject_entity": self.subject_entity,
            "columns": [c.to_dict() for c in self.columns],
            "row_relations": [r.to_dict() for r in self.row_relations],
            "cell_mentions": [m.to_dict() for m in self.cell_mentions],
            "triples": self.triples,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class TextInterpretationResult:
    """Extraction and resolution result for unstructured text."""

    text: str
    spans: List[EntitySpan] = field(default_factory=list)
    relations: List[RowRelation] = field(default_factory=list)
    triples: List[Tuple[str, str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "spans": [s.to_dict() for s in self.spans],
            "relations": [r.to_dict() for r in self.relations],
            "triples": self.triples,
            "summary": self.summary,
        }


@dataclass
class PingPongStep:
    """A single step in the neuro-symbolic dialogue loop."""

    step_number: int
    proposal: CandidateTableInterpretation
    conflicts: List[DiagnosticConflict] = field(default_factory=list)
    feedback_message: str = ""
    adjustments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "proposal": self.proposal.to_dict(),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "feedback_message": self.feedback_message,
            "adjustments": self.adjustments,
        }


@dataclass
class PingPongResult:
    """The complete result of running the NeuroSymbolicPingPongEngine."""

    success: bool
    converged: bool
    iterations: int
    history: List[PingPongStep]
    mesh: TableInterpretationMesh
    remaining_conflicts: List[DiagnosticConflict] = field(default_factory=list)
    diagnostic_logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "converged": self.converged,
            "iterations": self.iterations,
            "history": [s.to_dict() for s in self.history],
            "mesh": self.mesh.to_dict(),
            "remaining_conflicts": [c.to_dict() for c in self.remaining_conflicts],
            "diagnostic_logs": self.diagnostic_logs,
        }


@dataclass
class CandidateOntologyAxiom:
    """A proposed ontology extension discovered during extraction."""

    axiom_type: str  # 'NewClass', 'NewProperty', 'DomainRangeExtension', 'InstanceDeclaration'
    subject: str
    predicate: str
    object: str
    confidence: float = 0.8
    evidence: str = ""
    proposed_turtle: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
