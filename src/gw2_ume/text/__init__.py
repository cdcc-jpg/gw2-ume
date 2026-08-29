"""GW2-UME Text extraction and cross-modal triangulation package."""

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
    "TextEntityRelationExtractor",
    "CrossModalTriangulator",
    "TriangulatedEntity",
    "TriangulatedTriple",
    "TriangulationResult",
    "verify_beverley_principle",
    "verify_priory_namespace_consistency",
    "triangulate_table_and_text",
]

