"""Pipeline subpackage for GW2-UME.

Contains the NeuroSymbolicPingPongEngine, SymbolicAxiomReasoner, KnowledgeGraphEnricher,
and the top-level UMEEngine orchestrator.
"""

from gw2_ume.pipeline.enricher import KnowledgeGraphEnricher
from gw2_ume.pipeline.engine import UMEEngine
from gw2_ume.pipeline.pingpong import NeuroSymbolicPingPongEngine, SymbolicAxiomReasoner
from gw2_ume.pipeline.triangulator import (
    CrossModalTriangulator,
    TriangulationResult,
    FusedEntity,
    FusedTriple,
)

__all__ = [
    "NeuroSymbolicPingPongEngine",
    "SymbolicAxiomReasoner",
    "KnowledgeGraphEnricher",
    "UMEEngine",
    "CrossModalTriangulator",
    "TriangulationResult",
    "FusedEntity",
    "FusedTriple",
]
