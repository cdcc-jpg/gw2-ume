"""Data models for Table Annotations (CEA, CTA, CPA) and Relational Mesh."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class CellAnnotation:
    """Cell Entity Annotation (CEA)."""
    row_idx: int
    col_idx: int
    raw_value: str
    entity_uri: str
    label: str
    entity_type: str
    confidence: float
    provenance: str = "neural_symbolic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_idx": self.row_idx,
            "col_idx": self.col_idx,
            "raw_value": self.raw_value,
            "entity_uri": self.entity_uri,
            "label": self.label,
            "entity_type": self.entity_type,
            "confidence": round(self.confidence, 4),
            "provenance": self.provenance,
        }


@dataclass
class ColumnAnnotation:
    """Column Type Annotation (CTA)."""
    col_idx: int
    col_name: str
    type_uri: str
    type_label: str
    confidence: float
    sample_values: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "col_idx": self.col_idx,
            "col_name": self.col_name,
            "type_uri": self.type_uri,
            "type_label": self.type_label,
            "confidence": round(self.confidence, 4),
            "sample_values": self.sample_values,
        }


@dataclass
class ColumnPropertyAnnotation:
    """Column Property Annotation (CPA)."""
    source_col_idx: int
    target_col_idx: int
    source_col: str
    target_col: str
    property_uri: str
    property_label: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_col_idx": self.source_col_idx,
            "target_col_idx": self.target_col_idx,
            "source_col": self.source_col,
            "target_col": self.target_col,
            "property_uri": self.property_uri,
            "property_label": self.property_label,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class MeshNode:
    """A semantic node in the relational mesh."""
    id: str
    label: str
    node_type: str
    uri: str
    properties: Dict[str, Any] = field(default_factory=dict)
    row_idx: Optional[int] = None
    col_idx: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "uri": self.uri,
            "properties": self.properties,
            "row_idx": self.row_idx,
            "col_idx": self.col_idx,
        }


@dataclass
class MeshEdge:
    """A semantic directed edge in the relational mesh."""
    source_id: str
    target_id: str
    property_uri: str
    property_label: str
    confidence: float = 1.0
    provenance: str = "relational_mesh"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "property_uri": self.property_uri,
            "property_label": self.property_label,
            "confidence": round(self.confidence, 4),
            "provenance": self.provenance,
        }


@dataclass
class RelationalMesh:
    """Unified Relational Mesh representing the annotated table and its semantic graph."""
    table_name: str
    headers: List[str]
    rows: List[List[str]]
    cta: List[ColumnAnnotation] = field(default_factory=list)
    cea: List[CellAnnotation] = field(default_factory=list)
    cpa: List[ColumnPropertyAnnotation] = field(default_factory=list)
    nodes: List[MeshNode] = field(default_factory=list)
    edges: List[MeshEdge] = field(default_factory=list)
    turtle: str = ""
    json_ld: Dict[str, Any] = field(default_factory=dict)
    validation_status: str = "CONFORMING"
    validation_violations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "headers": self.headers,
            "row_count": len(self.rows),
            "cta": [c.to_dict() for c in self.cta],
            "cea_count": len(self.cea),
            "cpa": [p.to_dict() for p in self.cpa],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "validation_status": self.validation_status,
            "violations_count": len(self.validation_violations),
        }
