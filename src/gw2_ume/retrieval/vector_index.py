"""Vector and Lexical Index for Entity, Class, and Property Retrieval."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable
import numpy as np


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return re.findall(r"\b\w+\b", text.lower())


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    """Extract character n-grams from cleaned text."""
    s = f"^{text.lower().strip()}$"
    if len(s) < n:
        return {s}
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if s1 == s2:
        return 0
    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)

    v0 = list(range(len(s2) + 1))
    v1 = [0] * (len(s2) + 1)

    for i in range(len(s1)):
        v1[0] = i + 1
        for j in range(len(s2)):
            cost = 0 if s1[i] == s2[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        v0 = v1.copy()

    return v1[len(s2)]


def _lexical_similarity(query: str, candidate_text: str, aliases: list[str] | None = None) -> float:
    """Compute normalized lexical similarity combining token Jaccard, char n-gram Jaccard, and edit distance."""
    q_norm = query.lower().strip()
    c_norm = candidate_text.lower().strip()

    if not q_norm or not c_norm:
        return 0.0

    targets = [c_norm]
    if aliases:
        targets.extend([a.lower().strip() for a in aliases if a])

    best_score = 0.0
    for target in targets:
        if q_norm == target:
            return 1.0

        # Substring exact check
        sub_bonus = 0.0
        if q_norm in target or target in q_norm:
            sub_bonus = 0.2

        # 1. Token Jaccard
        q_tokens = set(_tokenize(q_norm))
        t_tokens = set(_tokenize(target))
        if q_tokens and t_tokens:
            token_jaccard = len(q_tokens & t_tokens) / len(q_tokens | t_tokens)
        else:
            token_jaccard = 0.0

        # 2. Char 3-gram Jaccard
        q_ngrams = _char_ngrams(q_norm, 3)
        t_ngrams = _char_ngrams(target, 3)
        ngram_jaccard = len(q_ngrams & t_ngrams) / len(q_ngrams | t_ngrams) if (q_ngrams and t_ngrams) else 0.0

        # 3. Levenshtein ratio
        dist = _levenshtein_distance(q_norm, target)
        max_len = max(len(q_norm), len(target))
        lev_ratio = 1.0 - (dist / max_len) if max_len > 0 else 0.0

        score = 0.35 * token_jaccard + 0.35 * ngram_jaccard + 0.30 * lev_ratio + sub_bonus
        score = min(1.0, score)
        if score > best_score:
            best_score = score

    return best_score


class DeterministicDenseEmbedder:
    """Fast, deterministic character and subword hash dense embedder for offline/test environments."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        """Embed text deterministically into normalized vector space."""
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text:
            return vec

        text_norm = text.lower().strip()
        tokens = _tokenize(text_norm)
        ngrams = list(_char_ngrams(text_norm, 3)) + list(_char_ngrams(text_norm, 4))

        # Hash tokens
        for token in tokens:
            h = hash(token) % self.dim
            vec[h] += 2.0

        # Hash ngrams
        for ng in ngrams:
            h = hash(ng) % self.dim
            vec[h] += 1.0

        # Positional character weight
        for idx, ch in enumerate(text_norm[:32]):
            h = (hash(ch) + idx * 31) % self.dim
            vec[h] += 0.5

        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        return vec


@dataclass
class IndexedEntity:
    iri: str
    label: str
    types: list[str]
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: np.ndarray | None = None


@dataclass
class IndexedClass:
    iri: str
    label: str
    description: str = ""
    parent_iris: list[str] = field(default_factory=list)
    embedding: np.ndarray | None = None


@dataclass
class IndexedProperty:
    iri: str
    label: str
    description: str = ""
    domain_iri: str | None = None
    range_iri: str | None = None
    embedding: np.ndarray | None = None


@dataclass
class RetrievalResult:
    iri: str
    label: str
    types: list[str]
    score: float
    dense_score: float
    lexical_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorIndex:
    """Multimodal dense + lexical retrieval index for ontology knowledge graph."""

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray] | None = None,
        embedding_dim: int = 128,
    ) -> None:
        self.embedding_dim = embedding_dim
        self._default_embedder = DeterministicDenseEmbedder(dim=embedding_dim)
        self.embed_fn = embed_fn or self._default_embedder.embed

        self.entities: dict[str, IndexedEntity] = {}
        self.classes: dict[str, IndexedClass] = {}
        self.properties: dict[str, IndexedProperty] = {}

    def add_entity(
        self,
        iri: str,
        label: str,
        types: list[str],
        description: str = "",
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index an entity with its label, types, description, and aliases."""
        alias_list = aliases or []
        meta = metadata or {}
        full_text = f"{label} {' '.join(alias_list)} {description}".strip()
        emb = self.embed_fn(full_text)
        self.entities[iri] = IndexedEntity(
            iri=iri,
            label=label,
            types=types,
            description=description,
            aliases=alias_list,
            metadata=meta,
            embedding=emb,
        )

    def add_class(
        self,
        iri: str,
        label: str,
        description: str = "",
        parent_iris: list[str] | None = None,
    ) -> None:
        """Index an ontology class."""
        full_text = f"{label} {description}".strip()
        emb = self.embed_fn(full_text)
        self.classes[iri] = IndexedClass(
            iri=iri,
            label=label,
            description=description,
            parent_iris=parent_iris or [],
            embedding=emb,
        )

    def add_property(
        self,
        iri: str,
        label: str,
        description: str = "",
        domain_iri: str | None = None,
        range_iri: str | None = None,
    ) -> None:
        """Index an ontology property."""
        full_text = f"{label} {description}".strip()
        emb = self.embed_fn(full_text)
        self.properties[iri] = IndexedProperty(
            iri=iri,
            label=label,
            description=description,
            domain_iri=domain_iri,
            range_iri=range_iri,
            embedding=emb,
        )

    def search_entities(
        self,
        query: str,
        top_k: int = 10,
        type_filter: str | None = None,
        alpha: float = 0.6,
        beta: float = 0.4,
    ) -> list[RetrievalResult]:
        """Search entity candidates combining dense cosine similarity and lexical metrics."""
        if not query.strip() or not self.entities:
            return []

        query_emb = self.embed_fn(query)
        results: list[RetrievalResult] = []

        for iri, item in self.entities.items():
            if type_filter and type_filter not in item.types:
                continue

            # Dense cosine score
            if item.embedding is not None and np.linalg.norm(query_emb) > 0 and np.linalg.norm(item.embedding) > 0:
                dense_score = float(np.dot(query_emb, item.embedding))
                dense_score = max(0.0, min(1.0, (dense_score + 1.0) / 2.0 if dense_score < 0 else dense_score))
            else:
                dense_score = 0.0

            # Lexical score
            lexical_score = _lexical_similarity(query, item.label, item.aliases)

            # Combined score
            combined_score = alpha * dense_score + beta * lexical_score
            # Boost exact matches
            if query.lower().strip() == item.label.lower().strip() or query.lower().strip() in [a.lower().strip() for a in item.aliases]:
                combined_score = max(combined_score, 0.95)

            results.append(
                RetrievalResult(
                    iri=iri,
                    label=item.label,
                    types=item.types,
                    score=float(combined_score),
                    dense_score=float(dense_score),
                    lexical_score=float(lexical_score),
                    metadata=item.metadata,
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def search_classes(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.6,
        beta: float = 0.4,
    ) -> list[RetrievalResult]:
        """Search ontology classes by query similarity."""
        if not query.strip() or not self.classes:
            return []

        query_emb = self.embed_fn(query)
        results: list[RetrievalResult] = []

        for iri, item in self.classes.items():
            if item.embedding is not None and np.linalg.norm(query_emb) > 0 and np.linalg.norm(item.embedding) > 0:
                dense_score = float(np.dot(query_emb, item.embedding))
                dense_score = max(0.0, min(1.0, dense_score))
            else:
                dense_score = 0.0

            lexical_score = _lexical_similarity(query, item.label)
            combined_score = alpha * dense_score + beta * lexical_score
            if query.lower().strip() == item.label.lower().strip():
                combined_score = max(combined_score, 0.95)

            results.append(
                RetrievalResult(
                    iri=iri,
                    label=item.label,
                    types=[iri],
                    score=float(combined_score),
                    dense_score=float(dense_score),
                    lexical_score=float(lexical_score),
                    metadata={"parent_iris": item.parent_iris},
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def search_properties(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.6,
        beta: float = 0.4,
    ) -> list[RetrievalResult]:
        """Search ontology properties by query similarity."""
        if not query.strip() or not self.properties:
            return []

        query_emb = self.embed_fn(query)
        results: list[RetrievalResult] = []

        for iri, item in self.properties.items():
            if item.embedding is not None and np.linalg.norm(query_emb) > 0 and np.linalg.norm(item.embedding) > 0:
                dense_score = float(np.dot(query_emb, item.embedding))
                dense_score = max(0.0, min(1.0, dense_score))
            else:
                dense_score = 0.0

            lexical_score = _lexical_similarity(query, item.label)
            combined_score = alpha * dense_score + beta * lexical_score
            if query.lower().strip() == item.label.lower().strip():
                combined_score = max(combined_score, 0.95)

            results.append(
                RetrievalResult(
                    iri=iri,
                    label=item.label,
                    types=[],
                    score=float(combined_score),
                    dense_score=float(dense_score),
                    lexical_score=float(lexical_score),
                    metadata={"domain_iri": item.domain_iri, "range_iri": item.range_iri},
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
