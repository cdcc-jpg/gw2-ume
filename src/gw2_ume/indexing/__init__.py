"""Dense retrieval, vector indexing, and ontology embedding package for GW2-UME."""

from gw2_ume.indexing.builder import OntologyIndexBuilder
from gw2_ume.indexing.embedder import (
    BaseEmbedder,
    LightweightFallbackEmbedder,
    TextEmbedder,
    detect_optimal_device,
)
from gw2_ume.indexing.faiss_index import (
    BaseVectorIndex,
    FaissVectorIndex,
    NumpyVectorIndex,
    ScoredMatch,
    VectorIndex,
    is_faiss_available,
)

__all__ = [
    "BaseEmbedder",
    "LightweightFallbackEmbedder",
    "TextEmbedder",
    "detect_optimal_device",
    "BaseVectorIndex",
    "NumpyVectorIndex",
    "FaissVectorIndex",
    "VectorIndex",
    "ScoredMatch",
    "is_faiss_available",
    "OntologyIndexBuilder",
]
