"""High-performance Vector Index supporting Cosine Similarity via Faiss and Pure-NumPy."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

logger = logging.getLogger(__name__)

# Check if FAISS is available
try:
    import faiss

    HAS_FAISS = True
except (ImportError, ModuleNotFoundError):
    faiss = None
    HAS_FAISS = False


def is_faiss_available() -> bool:
    """Return True if the faiss library is installed and importable."""
    return HAS_FAISS


@dataclass
class ScoredMatch:
    """Represents a scored search result match from the vector index."""

    id: str
    iri: str
    label: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    entity_type: str = "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert ScoredMatch to dictionary."""
        return {
            "id": self.id,
            "iri": self.iri,
            "label": self.label,
            "score": self.score,
            "metadata": self.metadata,
            "entity_type": self.entity_type,
        }


class BaseVectorIndex(ABC):
    """Abstract interface for dense vector indices."""

    @abstractmethod
    def add(self, vectors: np.ndarray, payloads: List[Dict[str, Any]]) -> None:
        """Add dense vectors with associated metadata payloads."""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_type: Optional[Union[str, Sequence[str]]] = None,
    ) -> List[ScoredMatch]:
        """Search for top_k nearest neighbors using cosine similarity (inner product)."""
        pass

    @abstractmethod
    def save(self, path: Union[str, Path]) -> None:
        """Persist index and metadata to disk."""
        pass

    @classmethod
    @abstractmethod
    def load(cls, path: Union[str, Path]) -> BaseVectorIndex:
        """Load index and metadata from disk."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the total number of indexed vectors."""
        pass


class NumpyVectorIndex(BaseVectorIndex):
    """Fast, pure-NumPy vectorized inner product / cosine similarity vector index."""

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension
        self._vectors: np.ndarray = np.empty((0, dimension), dtype=np.float32)
        self._payloads: List[Dict[str, Any]] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def vectors(self) -> np.ndarray:
        return self._vectors

    @property
    def payloads(self) -> List[Dict[str, Any]]:
        return self._payloads

    def __len__(self) -> int:
        return len(self._payloads)

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        """L2-normalize array rows."""
        if arr.ndim == 1:
            norm = np.linalg.norm(arr)
            return (arr / norm).astype(np.float32) if norm > 1e-12 else arr.astype(np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return np.where(norms > 1e-12, arr / norms, arr).astype(np.float32)

    def add(self, vectors: np.ndarray, payloads: List[Dict[str, Any]]) -> None:
        """Add vectors with metadata payloads."""
        if len(vectors) != len(payloads):
            raise ValueError(
                f"Mismatch: {len(vectors)} vectors provided for {len(payloads)} payloads."
            )

        if len(vectors) == 0:
            return

        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        if arr.shape[1] != self._dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self._dimension}, got {arr.shape[1]}"
            )

        normed = self._normalize(arr)

        if self._vectors.shape[0] == 0:
            self._vectors = normed
        else:
            self._vectors = np.vstack([self._vectors, normed])

        self._payloads.extend(payloads)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_type: Optional[Union[str, Sequence[str]]] = None,
    ) -> List[ScoredMatch]:
        """Search top_k nearest vectors using cosine similarity with optional entity_type filtering."""
        if len(self._payloads) == 0 or top_k <= 0:
            return []

        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 2:
            q = q.reshape(-1)

        if q.shape[0] != self._dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self._dimension}, got {q.shape[0]}"
            )

        q_norm = self._normalize(q)

        # Prepare candidate subset based on filter_type
        if filter_type is not None:
            if isinstance(filter_type, str):
                allowed = {filter_type.lower()}
            else:
                allowed = {t.lower() for t in filter_type}

            candidate_indices = [
                i
                for i, p in enumerate(self._payloads)
                if p.get("entity_type", "").lower() in allowed
            ]

            if not candidate_indices:
                return []

            cand_vecs = self._vectors[candidate_indices]
            scores = cand_vecs @ q_norm
            num_results = min(top_k, len(candidate_indices))

            if len(scores) <= top_k:
                sorted_local_indices = np.argsort(-scores)
            else:
                # Fast top-K partition followed by sort
                partitioned_indices = np.argpartition(-scores, num_results - 1)[:num_results]
                sorted_local_indices = partitioned_indices[np.argsort(-scores[partitioned_indices])]

            results: List[ScoredMatch] = []
            for local_idx in sorted_local_indices:
                global_idx = candidate_indices[local_idx]
                score = float(scores[local_idx])
                payload = self._payloads[global_idx]
                results.append(
                    ScoredMatch(
                        id=payload.get("id", str(global_idx)),
                        iri=payload.get("iri", ""),
                        label=payload.get("label", ""),
                        score=score,
                        metadata=payload.get("metadata", payload),
                        entity_type=payload.get("entity_type", "Unknown"),
                    )
                )
            return results

        # No filter: full matrix multiplication
        scores = self._vectors @ q_norm
        num_results = min(top_k, len(self._payloads))

        if len(scores) <= top_k:
            sorted_indices = np.argsort(-scores)
        else:
            partitioned = np.argpartition(-scores, num_results - 1)[:num_results]
            sorted_indices = partitioned[np.argsort(-scores[partitioned])]

        results = []
        for idx in sorted_indices:
            score = float(scores[idx])
            payload = self._payloads[idx]
            results.append(
                ScoredMatch(
                    id=payload.get("id", str(idx)),
                    iri=payload.get("iri", ""),
                    label=payload.get("label", ""),
                    score=score,
                    metadata=payload.get("metadata", payload),
                    entity_type=payload.get("entity_type", "Unknown"),
                )
            )
        return results

    def save(self, path: Union[str, Path]) -> None:
        """Persist index to .npz file or directory."""
        target_path = Path(path)
        if target_path.suffix != ".npz":
            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            file_path = target_path.with_suffix(".npz")
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            file_path = target_path

        payloads_json = json.dumps(self._payloads, ensure_ascii=False)
        np.savez_compressed(
            str(file_path),
            vectors=self._vectors,
            dimension=np.array([self._dimension], dtype=np.int32),
            payloads_json=np.array([payloads_json], dtype=object),
        )
        logger.info("Saved NumpyVectorIndex (%d vectors) to %s", len(self), file_path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> NumpyVectorIndex:
        """Load index from .npz file."""
        target_path = Path(path)
        if not target_path.exists() and target_path.with_suffix(".npz").exists():
            target_path = target_path.with_suffix(".npz")

        if not target_path.exists():
            raise FileNotFoundError(f"Index file not found: {target_path}")

        data = np.load(str(target_path), allow_pickle=True)
        dimension = int(data["dimension"][0])
        vectors = data["vectors"].astype(np.float32)
        payloads_json = str(data["payloads_json"][0])
        payloads = json.loads(payloads_json)

        index = cls(dimension=dimension)
        index._vectors = vectors
        index._payloads = payloads
        logger.info("Loaded NumpyVectorIndex (%d vectors) from %s", len(index), target_path)
        return index


class FaissVectorIndex(BaseVectorIndex):
    """High-performance vector index using FAISS IndexFlatIP (Cosine Similarity)."""

    def __init__(self, dimension: int) -> None:
        if not HAS_FAISS:
            raise ImportError(
                "faiss is not installed. Please install faiss-cpu or use NumpyVectorIndex."
            )
        self._dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._payloads: List[Dict[str, Any]] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def payloads(self) -> List[Dict[str, Any]]:
        return self._payloads

    def __len__(self) -> int:
        return len(self._payloads)

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        if arr.ndim == 1:
            norm = np.linalg.norm(arr)
            return (arr / norm).astype(np.float32) if norm > 1e-12 else arr.astype(np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return np.where(norms > 1e-12, arr / norms, arr).astype(np.float32)

    def add(self, vectors: np.ndarray, payloads: List[Dict[str, Any]]) -> None:
        """Add vectors to FAISS index with payloads."""
        if len(vectors) != len(payloads):
            raise ValueError(
                f"Mismatch: {len(vectors)} vectors provided for {len(payloads)} payloads."
            )

        if len(vectors) == 0:
            return

        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        if arr.shape[1] != self._dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self._dimension}, got {arr.shape[1]}"
            )

        normed = self._normalize(arr)
        self._index.add(normed)
        self._payloads.extend(payloads)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_type: Optional[Union[str, Sequence[str]]] = None,
    ) -> List[ScoredMatch]:
        """Search FAISS index with optional entity_type filtering."""
        if len(self._payloads) == 0 or top_k <= 0:
            return []

        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        if q.shape[1] != self._dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self._dimension}, got {q.shape[1]}"
            )

        q_norm = self._normalize(q)

        if filter_type is not None:
            if isinstance(filter_type, str):
                allowed = {filter_type.lower()}
            else:
                allowed = {t.lower() for t in filter_type}

            candidate_indices = [
                i
                for i, p in enumerate(self._payloads)
                if p.get("entity_type", "").lower() in allowed
            ]

            if not candidate_indices:
                return []

            # Reconstruct candidate vectors from index or compute scores
            # IndexFlatIP allows reconstructing vectors
            cand_vecs = np.zeros((len(candidate_indices), self._dimension), dtype=np.float32)
            for i, idx in enumerate(candidate_indices):
                cand_vecs[i] = self._index.reconstruct(idx)

            scores = cand_vecs @ q_norm[0]
            num_results = min(top_k, len(candidate_indices))

            if len(scores) <= top_k:
                sorted_local = np.argsort(-scores)
            else:
                part = np.argpartition(-scores, num_results - 1)[:num_results]
                sorted_local = part[np.argsort(-scores[part])]

            results: List[ScoredMatch] = []
            for local_idx in sorted_local:
                global_idx = candidate_indices[local_idx]
                score = float(scores[local_idx])
                payload = self._payloads[global_idx]
                results.append(
                    ScoredMatch(
                        id=payload.get("id", str(global_idx)),
                        iri=payload.get("iri", ""),
                        label=payload.get("label", ""),
                        score=score,
                        metadata=payload.get("metadata", payload),
                        entity_type=payload.get("entity_type", "Unknown"),
                    )
                )
            return results

        # Unfiltered direct FAISS search
        k = min(top_k, len(self._payloads))
        scores, indices = self._index.search(q_norm, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._payloads):
                continue
            payload = self._payloads[idx]
            results.append(
                ScoredMatch(
                    id=payload.get("id", str(idx)),
                    iri=payload.get("iri", ""),
                    label=payload.get("label", ""),
                    score=float(score),
                    metadata=payload.get("metadata", payload),
                    entity_type=payload.get("entity_type", "Unknown"),
                )
            )
        return results

    def save(self, path: Union[str, Path]) -> None:
        """Save FAISS index and metadata to disk."""
        target_path = Path(path)
        base_path = target_path.with_suffix("") if target_path.suffix else target_path
        base_path.parent.mkdir(parents=True, exist_ok=True)

        faiss_file = str(base_path.with_suffix(".faiss"))
        meta_file = str(base_path.with_suffix(".meta.json"))

        faiss.write_index(self._index, faiss_file)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "dimension": self._dimension,
                    "count": len(self._payloads),
                    "payloads": self._payloads,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info("Saved FaissVectorIndex (%d vectors) to %s", len(self), base_path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> FaissVectorIndex:
        """Load FAISS index and metadata from disk."""
        if not HAS_FAISS:
            raise ImportError("faiss is required to load FaissVectorIndex.")

        target_path = Path(path)
        base_path = target_path.with_suffix("") if target_path.suffix in [".faiss", ".json", ""] else target_path

        faiss_file = base_path.with_suffix(".faiss")
        meta_file = base_path.with_suffix(".meta.json")

        if not faiss_file.exists() or not meta_file.exists():
            raise FileNotFoundError(f"Faiss index files not found at: {base_path}")

        index_obj = faiss.read_index(str(faiss_file))
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        dimension = int(meta["dimension"])
        payloads = meta["payloads"]

        res = cls(dimension=dimension)
        res._index = index_obj
        res._payloads = payloads
        logger.info("Loaded FaissVectorIndex (%d vectors) from %s", len(res), base_path)
        return res


class VectorIndex(BaseVectorIndex):
    """Unified Vector Index wrapper providing identical semantics across Faiss and Pure-NumPy."""

    def __init__(self, dimension: int, prefer_faiss: bool = True) -> None:
        self._dimension = dimension
        self._prefer_faiss = prefer_faiss and HAS_FAISS

        if self._prefer_faiss:
            self._backend: BaseVectorIndex = FaissVectorIndex(dimension=dimension)
        else:
            self._backend = NumpyVectorIndex(dimension=dimension)

    @property
    def is_faiss(self) -> bool:
        """Whether the index is backed by native FAISS."""
        return isinstance(self._backend, FaissVectorIndex)

    @property
    def backend(self) -> BaseVectorIndex:
        """Underlying index implementation."""
        return self._backend

    @property
    def dimension(self) -> int:
        return self._backend.dimension

    @property
    def payloads(self) -> List[Dict[str, Any]]:
        return getattr(self._backend, "payloads", [])

    def __len__(self) -> int:
        return len(self._backend)

    def add(self, vectors: np.ndarray, payloads: List[Dict[str, Any]]) -> None:
        self._backend.add(vectors, payloads)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_type: Optional[Union[str, Sequence[str]]] = None,
    ) -> List[ScoredMatch]:
        return self._backend.search(query_vector, top_k=top_k, filter_type=filter_type)

    def save(self, path: Union[str, Path]) -> None:
        self._backend.save(path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> BaseVectorIndex:
        """Load vector index, automatically detecting format (.npz for Numpy, .faiss for FAISS)."""
        target = Path(path)
        if target.suffix == ".npz" or target.with_suffix(".npz").exists():
            return NumpyVectorIndex.load(target)
        if HAS_FAISS and (target.suffix == ".faiss" or target.with_suffix(".faiss").exists()):
            return FaissVectorIndex.load(target)
        # Fallback to Numpy
        if target.with_suffix(".npz").exists():
            return NumpyVectorIndex.load(target)
        raise FileNotFoundError(f"Could not identify vector index at {path}")

    @classmethod
    def create(cls, dimension: int, prefer_faiss: bool = True) -> BaseVectorIndex:
        """Factory method to construct optimal index backend."""
        if prefer_faiss and HAS_FAISS:
            return FaissVectorIndex(dimension=dimension)
        return NumpyVectorIndex(dimension=dimension)
