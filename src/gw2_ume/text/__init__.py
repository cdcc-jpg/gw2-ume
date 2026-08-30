"""GW2-UME Text extraction, modality parsing, dynamic table synthesis, and cross-modal triangulation package."""

from gw2_ume.text.modality_parser import (
    ModalityParser,
    ModalityType,
    DynamicSemanticFrame,
    SemanticSlot,
    DiscourseClause,
    ModalityParseResult,
)
from gw2_ume.text.table_synthesizer import (
    TableSynthesizer,
    SyntheticTableGrid,
)
from gw2_ume.text.extractor import (
    TextEntityRelationExtractor,
    CrossModalTriangulator,
    TriangulatedEntity,
    TriangulatedTriple,
    TriangulationResult,
    verify_beverley_principle,
    verify_priory_namespace_consistency,
    triangulate_table_and_text,
)

__all__ = [
    "ModalityParser",
    "ModalityType",
    "DynamicSemanticFrame",
    "SemanticSlot",
    "DiscourseClause",
    "ModalityParseResult",
    "TableSynthesizer",
    "SyntheticTableGrid",
    "TextEntityRelationExtractor",
    "CrossModalTriangulator",
    "TriangulatedEntity",
    "TriangulatedTriple",
    "TriangulationResult",
    "verify_beverley_principle",
    "verify_priory_namespace_consistency",
    "triangulate_table_and_text",
]
