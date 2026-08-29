"""GW2-UME: Universal Matrix Extraction & Neuro-Symbolic Graph Layer for Guild Wars 2."""

__version__ = "0.1.0"

from gw2_ume.mesh.models import RelationalMesh, CellAnnotation, ColumnAnnotation, ColumnPropertyAnnotation
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.pipeline.engine import UMEEngine
from gw2_ume.pipeline.pingpong import NeuroSymbolicPingPongEngine, SymbolicAxiomReasoner
from gw2_ume.pipeline.enricher import KnowledgeGraphEnricher
from gw2_ume.normalization.text_cleaner import (
    TableGrid,
    TextCleaner,
    normalize_text,
    extract_entity_spans,
    parse_table,
)
from gw2_ume.normalization.llm_normalizer import (
    LLMNormalizer,
    HeuristicNormalizer,
    LocalGemmaNormalizer,
    APILLMNormalizer,
    get_normalizer,
)
from gw2_ume.models import (
    EntitySpan,
    CellMention,
    TableColumnInterpretation,
    RowRelation,
    DiagnosticConflict,
    CandidateTableInterpretation,
    RefinedProposal,
    TableInterpretationMesh,
    TextInterpretationResult,
    PingPongStep,
    PingPongResult,
    CandidateOntologyAxiom,
)

__all__ = [
    "__version__",
    "UMEEngine",
    "TableGrid",
    "TextCleaner",
    "normalize_text",
    "extract_entity_spans",
    "parse_table",
    "LLMNormalizer",
    "HeuristicNormalizer",
    "LocalGemmaNormalizer",
    "APILLMNormalizer",
    "get_normalizer",
    "NeuroSymbolicPingPongEngine",
    "SymbolicAxiomReasoner",
    "KnowledgeGraphEnricher",
    "EntitySpan",
    "CellMention",
    "TableColumnInterpretation",
    "RowRelation",
    "DiagnosticConflict",
    "CandidateTableInterpretation",
    "RefinedProposal",
    "TableInterpretationMesh",
    "TextInterpretationResult",
    "PingPongStep",
    "PingPongResult",
    "CandidateOntologyAxiom",
    "RelationalMesh",
    "CellAnnotation",
    "ColumnAnnotation",
    "ColumnPropertyAnnotation",
    "build_relational_mesh",
]
