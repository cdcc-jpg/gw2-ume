"""Retrieval module for entity, class, and property vector indexing."""

from gw2_ume.retrieval.vector_index import (
    VectorIndex,
    RetrievalResult,
    DeterministicDenseEmbedder,
)

__all__ = [
    "VectorIndex",
    "RetrievalResult",
    "DeterministicDenseEmbedder",
]
