"""Vector and Lexical Index for Entity, Class, and Property Retrieval."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence
import numpy as np


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return re.findall(r"\b\w+\b", text.lower())


# Alias for internal/backward compatibility
_tokenize = tokenize


def char_ngrams(text: str, n: int = 3) -> set[str]:
    """Extract character n-grams from cleaned text."""
    s = f"^{text.lower().strip()}$"
    if len(s) < n:
        return {s}
    return {s[i : i + n] for i in range(len(s) - n + 1)}


# Alias for internal/backward compatibility
_char_ngrams = char_ngrams


def levenshtein_distance(s1: str, s2: str) -> int:
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


# Alias for internal/backward compatibility
_levenshtein_distance = levenshtein_distance


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein similarity in range [0.0, 1.0]."""
    s1_norm = s1.lower().strip()
    s2_norm = s2.lower().strip()
    if s1_norm == s2_norm:
        return 1.0
    max_len = max(len(s1_norm), len(s2_norm))
    if max_len == 0:
        return 1.0
    dist = levenshtein_distance(s1_norm, s2_norm)
    return max(0.0, 1.0 - (dist / max_len))


def jaro_similarity(s1: str, s2: str) -> float:
    """Compute Jaro similarity between two strings in range [0.0, 1.0]."""
    s1_clean = s1.strip().lower()
    s2_clean = s2.strip().lower()
    if s1_clean == s2_clean:
        return 1.0
    len1, len2 = len(s1_clean), len(s2_clean)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1_clean[i] == s2_clean[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    k = 0
    transpositions = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1_clean[i] != s2_clean[k]:
            transpositions += 1
        k += 1

    t = transpositions / 2.0
    return (matches / len1 + matches / len2 + (matches - t) / matches) / 3.0


def jaro_winkler_similarity(
    s1: str,
    s2: str,
    prefix_weight: float = 0.1,
    max_prefix: int = 4,
) -> float:
    """Compute Jaro-Winkler similarity between two strings."""
    s1_clean = s1.strip().lower()
    s2_clean = s2.strip().lower()
    jaro_sim = jaro_similarity(s1_clean, s2_clean)
    if jaro_sim == 1.0 or jaro_sim == 0.0:
        return jaro_sim

    prefix_len = 0
    for c1, c2 in zip(s1_clean[:max_prefix], s2_clean[:max_prefix]):
        if c1 == c2:
            prefix_len += 1
        else:
            break

    return min(1.0, jaro_sim + prefix_len * prefix_weight * (1.0 - jaro_sim))


def token_jaccard_similarity(s1: str, s2: str) -> float:
    """Compute Jaccard similarity over word tokens."""
    t1 = set(tokenize(s1))
    t2 = set(tokenize(s2))
    if not t1 and not t2:
        return 1.0 if (not s1.strip() and not s2.strip()) else 0.0
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def char_ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Compute Jaccard similarity over character n-grams."""
    ng1 = char_ngrams(s1, n)
    ng2 = char_ngrams(s2, n)
    if not ng1 and not ng2:
        return 1.0 if (not s1.strip() and not s2.strip()) else 0.0
    if not ng1 or not ng2:
        return 0.0
    return len(ng1 & ng2) / len(ng1 | ng2)


def cosine_similarity(v1: np.ndarray | None, v2: np.ndarray | None) -> float:
    """Compute cosine similarity between two 1D numpy vectors."""
    if v1 is None or v2 is None:
        return 0.0
    a = np.asarray(v1, dtype=np.float32).reshape(-1)
    b = np.asarray(v2, dtype=np.float32).reshape(-1)
    if a.shape != b.shape:
        return 0.0
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    dot = float(np.dot(a, b))
    sim = dot / (norm_a * norm_b)
    return float(np.clip(sim, -1.0, 1.0))


def normalize_text(text: str) -> str:
    """Normalizes noisy text by stripping OCR artifacts and standardizing casing."""
    text = text.lower().strip()
    text = re.sub(r"[@#$%^&*_+=\[\]{};:<>?/\\|~]", " ", text)
    # Common OCR/leetspeak normalizations
    text = text.replace("0", "o").replace("1", "i").replace("3", "e").replace("4", "a").replace("5", "s")
    text = re.sub(r"q(?!u)", "g", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def lexical_similarity(
    query: str,
    candidate_text: str,
    aliases: list[str] | None = None,
) -> float:
    """Compute normalized lexical similarity combining token Jaccard, char n-grams, Levenshtein, and Jaro-Winkler."""
    q_norm = normalize_text(query)
    c_norm = normalize_text(candidate_text)

    if not q_norm or not c_norm:
        return 0.0

    targets = [c_norm]
    if aliases:
        targets.extend([normalize_text(a) for a in aliases if a])

    best_score = 0.0
    for target in targets:
        if q_norm == target:
            return 1.0

        # Substring exact check
        sub_bonus = 0.0
        if q_norm in target or target in q_norm:
            sub_bonus = 0.15

        # 1. Token Jaccard
        tok_sim = token_jaccard_similarity(q_norm, target)

        # 2. Char 3-gram Jaccard
        ngram_sim = char_ngram_similarity(q_norm, target, 3)

        # 3. Levenshtein ratio
        lev_sim = levenshtein_similarity(q_norm, target)

        # 4. Jaro-Winkler
        jw_sim = jaro_winkler_similarity(q_norm, target)

        score = (
            0.25 * tok_sim
            + 0.25 * ngram_sim
            + 0.25 * lev_sim
            + 0.25 * jw_sim
            + sub_bonus
        )
        score = min(1.0, score)
        if score > best_score:
            best_score = score

    return best_score


# Alias for internal/backward compatibility
_lexical_similarity = lexical_similarity


class DeterministicDenseEmbedder:
    """Fast, deterministic character and subword hash dense embedder for offline/test environments."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    @property
    def dimension(self) -> int:
        return self.dim

    def embed(self, text: str) -> np.ndarray:
        """Embed text deterministically into normalized vector space."""
        import zlib
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text or not text.strip():
            return vec

        text_norm = normalize_text(text)
        tokens = tokenize(text_norm)
        ngrams = list(char_ngrams(text_norm, 3)) + list(char_ngrams(text_norm, 4))

        def _h(s: str) -> int:
            return zlib.crc32(s.encode("utf-8")) % self.dim

        # Hash tokens & bigrams
        for token in tokens:
            vec[_h(token)] += 2.0
        for i in range(len(tokens) - 1):
            bi = f"{tokens[i]}_{tokens[i+1]}"
            vec[_h(bi)] += 1.5

        # Hash ngrams
        for ng in ngrams:
            vec[_h(ng)] += 1.0

        # Positional character weight
        for idx, ch in enumerate(text_norm[:32]):
            vec[(_h(ch) + idx * 31) % self.dim] += 0.5

        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        return vec.astype(np.float32)

    def encode(
        self,
        texts: str | Sequence[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Batch encode texts deterministically."""
        if isinstance(texts, str):
            text_list = [texts]
        else:
            text_list = list(texts)

        if not text_list:
            return np.empty((0, self.dim), dtype=np.float32)

        vectors = np.zeros((len(text_list), self.dim), dtype=np.float32)
        for i, t in enumerate(text_list):
            vectors[i] = self.embed(t)

        if normalize:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors = np.where(norms > 1e-12, vectors / norms, vectors)

        return vectors.astype(np.float32)

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Encode a single text string."""
        vec = self.embed(text)
        if normalize:
            norm = np.linalg.norm(vec)
            if norm > 1e-12:
                vec = vec / norm
        return vec.astype(np.float32)


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
    aliases: list[str] = field(default_factory=list)
    embedding: np.ndarray | None = None


@dataclass
class IndexedProperty:
    iri: str
    label: str
    description: str = ""
    domain_iri: str | None = None
    range_iri: str | None = None
    aliases: list[str] = field(default_factory=list)
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
        embedder: Any | None = None,
    ) -> None:
        self.embedding_dim = embedding_dim
        if embedder is not None:
            self._embedder = embedder
            self.embedding_dim = getattr(embedder, "dimension", embedding_dim)
            fn = getattr(embedder, "encode_single", getattr(embedder, "embed", None))
            if fn is not None:
                self.embed_fn = fn
            else:
                self.embed_fn = lambda t: embedder.encode([t])[0]
        elif embed_fn is not None:
            self.embed_fn = embed_fn
            self._embedder = None
        else:
            self._embedder = DeterministicDenseEmbedder(dim=embedding_dim)
            self.embed_fn = self._embedder.embed

        self.entities: dict[str, IndexedEntity] = {}
        self.classes: dict[str, IndexedClass] = {}
        self.properties: dict[str, IndexedProperty] = {}

    def __len__(self) -> int:
        return len(self.entities) + len(self.classes) + len(self.properties)

    def add_entity(
        self,
        iri: str,
        label: str,
        types: list[str] | str,
        description: str = "",
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index an entity with its label, types, description, and aliases."""
        alias_list = aliases or []
        meta = metadata or {}
        type_list = [types] if isinstance(types, str) else list(types)
        full_text = f"{label} {' '.join(alias_list)} {description}".strip()
        emb = self.embed_fn(full_text)
        self.entities[iri] = IndexedEntity(
            iri=iri,
            label=label,
            types=type_list,
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
        aliases: list[str] | None = None,
    ) -> None:
        """Index an ontology class."""
        alias_list = aliases or []
        full_text = f"{label} {' '.join(alias_list)} {description}".strip()
        emb = self.embed_fn(full_text)
        self.classes[iri] = IndexedClass(
            iri=iri,
            label=label,
            description=description,
            parent_iris=parent_iris or [],
            aliases=alias_list,
            embedding=emb,
        )

    def add_property(
        self,
        iri: str,
        label: str,
        description: str = "",
        domain_iri: str | None = None,
        range_iri: str | None = None,
        aliases: list[str] | None = None,
    ) -> None:
        """Index an ontology property."""
        alias_list = aliases or []
        full_text = f"{label} {' '.join(alias_list)} {description}".strip()
        emb = self.embed_fn(full_text)
        self.properties[iri] = IndexedProperty(
            iri=iri,
            label=label,
            description=description,
            domain_iri=domain_iri,
            range_iri=range_iri,
            aliases=alias_list,
            embedding=emb,
        )

    def populate_from_catalog(self, catalog: dict[str, Any] | None = None) -> None:
        """Populate entities into this vector index from an entity catalog dict."""
        if catalog is None:
            try:
                from gw2_ume.ontology.schema import ENTITY_CATALOG
                catalog = ENTITY_CATALOG
            except Exception:
                catalog = {}

        for key, item in catalog.items():
            label = item.get("label", key)
            uri = str(item.get("uri", f"https://gw2ume.org/resource/{key}"))
            type_label = item.get("type_label", "Item")
            type_iri = str(item.get("type", "https://gw2ume.org/ontology#Item"))
            aliases = list(item.get("aliases", []))
            description = item.get("description", "")
            meta = dict(item)
            meta["type_label"] = type_label
            meta["canonical_label"] = label
            self.add_entity(
                iri=uri,
                label=label,
                types=[type_label, type_iri],
                description=description,
                aliases=aliases,
                metadata=meta,
            )

    def populate_from_ontology(self, loader_or_reasoner: Any) -> None:
        """Populate classes, properties, and entities from OntologyLoader or SymbolicAxiomReasoner."""
        if loader_or_reasoner is None:
            return

        # Handle SymbolicAxiomReasoner
        if hasattr(loader_or_reasoner, "get_all_classes"):
            for cls_iri in loader_or_reasoner.get_all_classes():
                labels = loader_or_reasoner.get_class_labels(cls_iri)
                label = labels[0] if labels else cls_iri.split("#")[-1].split("/")[-1]
                parents = loader_or_reasoner.get_superclasses(cls_iri, include_self=False)
                self.add_class(iri=cls_iri, label=label, parent_iris=list(parents))

        if hasattr(loader_or_reasoner, "get_all_properties"):
            for prop_iri in loader_or_reasoner.get_all_properties():
                labels = loader_or_reasoner.get_property_labels(prop_iri)
                label = labels[0] if labels else prop_iri.split("#")[-1].split("/")[-1]
                domains = getattr(loader_or_reasoner, "get_expected_domains", lambda p: set())(prop_iri)
                ranges = getattr(loader_or_reasoner, "get_expected_ranges", lambda p: set())(prop_iri)
                dom = str(list(domains)[0]) if domains else None
                rng = str(list(ranges)[0]) if ranges else None
                self.add_property(iri=prop_iri, label=label, domain_iri=dom, range_iri=rng)

        # Handle OntologyLoader
        if hasattr(loader_or_reasoner, "list_classes"):
            for c in loader_or_reasoner.list_classes():
                iri = str(c.iri)
                label = getattr(c, "display_name", None) or getattr(c, "label", None) or iri.split("#")[-1].split("/")[-1]
                syns = getattr(c, "alt_labels", []) or []
                desc = getattr(c, "comment", "") or ""
                parents = [str(p) for p in (getattr(c, "super_classes", []) or [])]
                self.add_class(iri=iri, label=label, description=desc, parent_iris=parents, aliases=list(syns))

        if hasattr(loader_or_reasoner, "list_object_properties"):
            for p in loader_or_reasoner.list_object_properties():
                iri = str(p.iri)
                label = getattr(p, "display_name", None) or getattr(p, "label", None) or iri.split("#")[-1].split("/")[-1]
                syns = getattr(p, "alt_labels", []) or []
                desc = getattr(p, "comment", "") or ""
                dom = str(p.domain[0]) if getattr(p, "domain", None) else None
                rng = str(p.range[0]) if getattr(p, "range", None) else None
                self.add_property(iri=iri, label=label, description=desc, domain_iri=dom, range_iri=rng, aliases=list(syns))

    def populate_defaults(self) -> None:
        """Populate vector index with default GW2 ontology classes, properties, and entity catalog."""
        # 1. Populate Catalog
        self.populate_from_catalog()

        # 2. Register core ontology classes with aliases
        default_classes = [
            ("https://priory.gw2/def/Item", "Item", "Game item", ["item", "thing", "output"]),
            ("https://priory.gw2/def/PrecursorWeapon", "Precursor Weapon", "Precursor weapon for legendary crafting", ["precursor", "weapon", "precursor weapon", "precursor thing"]),
            ("https://priory.gw2/def/LegendaryWeapon", "Legendary Weapon", "Legendary weapon item", ["legendary", "legendary weapon"]),
            ("https://priory.gw2/def/ComponentItem", "Component Item", "Crafted or purchased component item", ["component", "ingredient", "material", "sub_ingredient", "subingredients"]),
            ("https://priory.gw2/def/TrophyItem", "Trophy Item", "Collection or event trophy item", ["trophy", "trophy item", "quest item"]),
            ("https://priory.gw2/def/CraftingMaterial", "Crafting Material", "Basic or refined crafting material", ["crafting material", "mat", "materials"]),
            ("https://priory.gw2/def/CollectionStep", "Collection Step", "Step or task in an achievement collection", ["step", "journey", "task", "collection step"]),
            ("https://priory.gw2/def/CollectionTier", "Collection Tier", "Tier level of a collection or precursor", ["tier", "collection tier", "tier number"]),
            ("https://priory.gw2/def/MysticForgeRecipe", "Mystic Forge Recipe", "Recipe or slot in the Mystic Forge", ["slot", "forgeslot", "forge slot", "mystic forge"]),
            ("https://priory.gw2/def/DisciplineRecipe", "Discipline Recipe", "Standard discipline crafting recipe", ["recipe", "crafting recipe"]),
            ("https://priory.gw2/def/CraftingDiscipline", "Crafting Discipline", "Crafting trade profession", ["discipline", "craft", "prof", "profession", "crafting discipline"]),
            ("https://priory.gw2/def/DisciplineRating", "Discipline Rating", "Required skill rating for crafting", ["rating", "minrating", "level", "skill", "discipline rating"]),
            ("https://priory.gw2/def/IngredientQuantity", "Ingredient Quantity", "Required count or quantity of ingredient", ["qty", "quant", "cost", "count", "amount", "quantity"]),
            ("https://priory.gw2/def/NPCVendor", "NPC Vendor", "Non-player character merchant or vendor", ["vendor", "source", "npc", "merchant", "who", "seller"]),
            ("https://priory.gw2/def/Zone", "Zone", "Geographic game zone or map area", ["zone", "loc", "place", "where", "location", "region"]),
            ("https://priory.gw2/def/CuratedCollection", "Curated Collection", "Achievement collection for items", ["collection", "achievement collection"]),
        ]

        for iri, label, desc, aliases in default_classes:
            self.add_class(iri=iri, label=label, description=desc, aliases=aliases)

        # 3. Register core ontology properties with aliases
        default_props = [
            ("https://priory.gw2/def/requiresIngredient", "requiresIngredient", "Requires sub-ingredient or component", "https://priory.gw2/def/Item", "https://priory.gw2/def/Item", ["requires ingredient", "ingredient", "material"]),
            ("https://priory.gw2/def/craftedByDiscipline", "craftedByDiscipline", "Crafted by crafting discipline", "https://priory.gw2/def/Item", "https://priory.gw2/def/CraftingDiscipline", ["crafted by discipline", "discipline", "craft"]),
            ("https://priory.gw2/def/obtainedFromVendor", "obtainedFromVendor", "Obtained from NPC vendor", "https://priory.gw2/def/Item", "https://priory.gw2/def/NPCVendor", ["obtained from vendor", "vendor", "source", "sold by"]),
            ("https://priory.gw2/def/locatedInZone", "locatedInZone", "NPC vendor located in zone", "https://priory.gw2/def/NPCVendor", "https://priory.gw2/def/Zone", ["located in zone", "zone", "location", "in zone"]),
            ("https://priory.gw2/def/ingredientQuantity", "ingredientQuantity", "Quantity of required ingredient", "https://priory.gw2/def/Item", "https://priory.gw2/def/IngredientQuantity", ["ingredient quantity", "quantity", "qty", "count"]),
            ("https://priory.gw2/def/requiresDisciplineRating", "requiresDisciplineRating", "Requires crafting discipline skill rating", "https://priory.gw2/def/Item", "https://priory.gw2/def/DisciplineRating", ["requires discipline rating", "rating", "min rating"]),
            ("https://priory.gw2/def/tierNumber", "tierNumber", "Collection tier number", "https://priory.gw2/def/Item", "https://priory.gw2/def/CollectionTier", ["tier number", "tier"]),
            ("https://priory.gw2/def/hasPrecursor", "hasPrecursor", "Legendary weapon has precursor weapon", "https://priory.gw2/def/LegendaryWeapon", "https://priory.gw2/def/PrecursorWeapon", ["has precursor", "precursor"]),
            ("https://priory.gw2/def/partOfCollection", "partOfCollection", "Item is part of curated collection", "https://priory.gw2/def/Item", "https://priory.gw2/def/CuratedCollection", ["part of collection", "collection"]),
            ("https://priory.gw2/def/forgeSlot", "forgeSlot", "Mystic Forge recipe slot ingredient", "https://priory.gw2/def/MysticForgeRecipe", "https://priory.gw2/def/Item", ["forge slot", "slot"]),
        ]

        for iri, label, desc, dom, rng, aliases in default_props:
            self.add_property(iri=iri, label=label, description=desc, domain_iri=dom, range_iri=rng, aliases=aliases)

    @classmethod
    def from_defaults(cls, embedding_dim: int = 128) -> VectorIndex:
        """Construct a new VectorIndex pre-populated with default catalog & ontology definitions."""
        idx = cls(embedding_dim=embedding_dim)
        idx.populate_defaults()
        return idx

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
            if type_filter:
                match_type = any(
                    type_filter.lower() == t.lower() or type_filter.lower() in t.lower()
                    for t in item.types
                )
                if not match_type:
                    continue

            # Dense cosine score
            dense_sim = cosine_similarity(query_emb, item.embedding)
            # Map [-1, 1] to [0, 1]
            dense_score = max(0.0, min(1.0, (dense_sim + 1.0) / 2.0 if dense_sim < 0 else dense_sim))

            # Lexical score
            lexical_score = lexical_similarity(query, item.label, item.aliases)

            # Combined score
            combined_score = alpha * dense_score + beta * lexical_score

            # Boost exact matches
            q_clean = normalize_text(query)
            cand_clean = normalize_text(item.label)
            alias_cleans = [normalize_text(a) for a in item.aliases]
            if q_clean == cand_clean or q_clean in alias_cleans:
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
            dense_sim = cosine_similarity(query_emb, item.embedding)
            dense_score = max(0.0, min(1.0, (dense_sim + 1.0) / 2.0 if dense_sim < 0 else dense_sim))

            lexical_score = lexical_similarity(query, item.label, item.aliases)
            combined_score = alpha * dense_score + beta * lexical_score

            q_clean = normalize_text(query)
            cand_clean = normalize_text(item.label)
            alias_cleans = [normalize_text(a) for a in item.aliases]
            if q_clean == cand_clean or q_clean in alias_cleans:
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
            dense_sim = cosine_similarity(query_emb, item.embedding)
            dense_score = max(0.0, min(1.0, (dense_sim + 1.0) / 2.0 if dense_sim < 0 else dense_sim))

            lexical_score = lexical_similarity(query, item.label, item.aliases)
            combined_score = alpha * dense_score + beta * lexical_score

            q_clean = normalize_text(query)
            cand_clean = normalize_text(item.label)
            alias_cleans = [normalize_text(a) for a in item.aliases]
            if q_clean == cand_clean or q_clean in alias_cleans:
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

    def search(
        self,
        query: str,
        top_k: int = 10,
        type_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """Unified search across indexed entities."""
        return self.search_entities(query, top_k=top_k, type_filter=type_filter)


_DEFAULT_INDEX: VectorIndex | None = None


def get_default_vector_index() -> VectorIndex:
    """Retrieve or lazily initialize the singleton default VectorIndex."""
    global _DEFAULT_INDEX
    if _DEFAULT_INDEX is None:
        _DEFAULT_INDEX = VectorIndex.from_defaults()
    return _DEFAULT_INDEX


__all__ = [
    "tokenize",
    "char_ngrams",
    "levenshtein_distance",
    "levenshtein_similarity",
    "jaro_similarity",
    "jaro_winkler_similarity",
    "token_jaccard_similarity",
    "char_ngram_similarity",
    "cosine_similarity",
    "normalize_text",
    "lexical_similarity",
    "_tokenize",
    "_char_ngrams",
    "_levenshtein_distance",
    "_lexical_similarity",
    "DeterministicDenseEmbedder",
    "IndexedEntity",
    "IndexedClass",
    "IndexedProperty",
    "RetrievalResult",
    "VectorIndex",
    "get_default_vector_index",
]
