"""Concept and Axiom Index Builder for Guild Wars 2 Ontologies."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import rdflib
from rdflib import OWL, RDF, RDFS, SKOS, URIRef

from gw2_ume.indexing.embedder import BaseEmbedder, TextEmbedder
from gw2_ume.indexing.faiss_index import (
    BaseVectorIndex,
    NumpyVectorIndex,
    ScoredMatch,
    VectorIndex,
)
from gw2_ume.ontology.loader import OntologyLoader

logger = logging.getLogger(__name__)


def _extract_local_name(iri: str) -> str:
    """Extract fragment or trailing slug from IRI."""
    if "#" in iri:
        return iri.split("#")[-1]
    if "/" in iri:
        return iri.rstrip("/").split("/")[-1]
    return iri


def _format_entity_for_embedding(payload: Dict[str, Any]) -> str:
    """Format rich semantic textual representation for dense bi-encoder indexing."""
    entity_type = payload.get("entity_type", "Concept")
    label = payload.get("label", "").strip()
    entity_id = payload.get("id", "").strip()
    description = payload.get("description", "").strip()
    synonyms = payload.get("synonyms", [])
    domains = payload.get("domain", [])
    ranges = payload.get("range", [])
    superclasses = payload.get("superclasses", [])
    types = payload.get("types", [])

    parts = [f"[{entity_type}] {label}"]
    if entity_id and entity_id.lower() != label.lower():
        parts[0] += f" ({entity_id})"

    if description:
        parts.append(f"Description: {description}")

    if synonyms:
        syn_str = ", ".join(synonyms[:10])
        parts.append(f"Synonyms: {syn_str}")

    if superclasses:
        sc_labels = [_extract_local_name(s) for s in superclasses]
        parts.append(f"Subclass of: {', '.join(sc_labels)}")

    if types:
        t_labels = [_extract_local_name(t) for t in types]
        parts.append(f"Type: {', '.join(t_labels)}")

    if domains:
        d_labels = [_extract_local_name(d) for d in domains]
        parts.append(f"Domain: {', '.join(d_labels)}")

    if ranges:
        r_labels = [_extract_local_name(r) for r in ranges]
        parts.append(f"Range: {', '.join(r_labels)}")

    return ". ".join(parts) + "."


class OntologyIndexBuilder:
    """Ingests OWL/RDFS ontologies, extracts concepts & axioms, embeds them, and builds a vector index."""

    def __init__(
        self,
        loader: Optional[OntologyLoader] = None,
        graph: Optional[rdflib.Graph] = None,
        embedder: Optional[BaseEmbedder] = None,
        index: Optional[BaseVectorIndex] = None,
        prefer_faiss: bool = True,
        auto_build: bool = False,
    ) -> None:
        if loader is not None:
            self.loader = loader
        elif graph is not None:
            self.loader = OntologyLoader(graph=graph)
        else:
            self.loader = OntologyLoader(auto_load_defaults=True)

        self.embedder: BaseEmbedder = (
            embedder if embedder is not None else TextEmbedder()
        )

        dim = self.embedder.dimension
        self.index: BaseVectorIndex = (
            index if index is not None else VectorIndex(dimension=dim, prefer_faiss=prefer_faiss)
        )

        self._entities: Dict[str, Dict[str, Any]] = {}

        if auto_build:
            self.build_index()

    @property
    def entities(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of indexed entity payloads mapped by IRI."""
        return self._entities

    def _extract_from_loader_lists(self) -> List[Dict[str, Any]]:
        """Extract entity payloads using OntologyLoader list_* methods."""
        payloads: List[Dict[str, Any]] = []

        # 1. Classes
        if hasattr(self.loader, "list_classes"):
            for c in self.loader.list_classes():
                iri = str(c.iri)
                label = getattr(c, "display_name", None) or getattr(c, "label", None) or _extract_local_name(iri)
                syns = getattr(c, "alt_labels", []) or []
                pref = getattr(c, "pref_label", None)
                if pref and pref != label and pref not in syns:
                    syns = [pref] + list(syns)
                desc = getattr(c, "comment", "") or ""
                supers = getattr(c, "super_classes", []) or getattr(c, "superclasses", []) or []

                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": label,
                    "entity_type": "Class",
                    "description": desc,
                    "synonyms": list(syns),
                    "superclasses": list(supers),
                    "metadata": {
                        "superclasses": list(supers),
                        "synonyms": list(syns),
                    },
                })

        # 2. Object Properties
        if hasattr(self.loader, "list_object_properties"):
            for p in self.loader.list_object_properties():
                iri = str(p.iri)
                label = getattr(p, "display_name", None) or getattr(p, "label", None) or _extract_local_name(iri)
                syns = getattr(p, "alt_labels", []) or []
                pref = getattr(p, "pref_label", None)
                if pref and pref != label and pref not in syns:
                    syns = [pref] + list(syns)
                desc = getattr(p, "comment", "") or ""
                domains = getattr(p, "domains", []) or getattr(p, "domain", []) or []
                ranges = getattr(p, "ranges", []) or getattr(p, "range", []) or []

                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": label,
                    "entity_type": "ObjectProperty",
                    "description": desc,
                    "synonyms": list(syns),
                    "domain": list(domains),
                    "range": list(ranges),
                    "metadata": {
                        "domain": list(domains),
                        "range": list(ranges),
                    },
                })

        # 3. Datatype Properties
        if hasattr(self.loader, "list_datatype_properties"):
            for dp in self.loader.list_datatype_properties():
                iri = str(dp.iri)
                label = getattr(dp, "display_name", None) or getattr(dp, "label", None) or _extract_local_name(iri)
                syns = getattr(dp, "alt_labels", []) or []
                pref = getattr(dp, "pref_label", None)
                if pref and pref != label and pref not in syns:
                    syns = [pref] + list(syns)
                desc = getattr(dp, "comment", "") or ""
                domains = getattr(dp, "domains", []) or getattr(dp, "domain", []) or []
                ranges = getattr(dp, "ranges", []) or getattr(dp, "range", []) or []

                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": label,
                    "entity_type": "DatatypeProperty",
                    "description": desc,
                    "synonyms": list(syns),
                    "domain": list(domains),
                    "range": list(ranges),
                    "metadata": {
                        "domain": list(domains),
                        "range": list(ranges),
                    },
                })

        # 4. Individuals
        if hasattr(self.loader, "list_individuals"):
            for ind in self.loader.list_individuals():
                iri = str(ind.iri)
                label = getattr(ind, "display_name", None) or getattr(ind, "label", None) or _extract_local_name(iri)
                syns = getattr(ind, "alt_labels", []) or []
                pref = getattr(ind, "pref_label", None)
                if pref and pref != label and pref not in syns:
                    syns = [pref] + list(syns)
                desc = getattr(ind, "comment", "") or ""
                types = getattr(ind, "types", []) or []

                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": label,
                    "entity_type": "Individual",
                    "description": desc,
                    "synonyms": list(syns),
                    "types": list(types),
                    "metadata": {
                        "types": list(types),
                    },
                })

        return payloads

    def _extract_from_graph_fallback(self) -> List[Dict[str, Any]]:
        """Direct RDF graph extraction fallback."""
        g = self.loader.graph
        payloads: List[Dict[str, Any]] = []
        seen_iris = set()

        def _get_label(subj: URIRef) -> str:
            for p in [SKOS.prefLabel, RDFS.label]:
                for o in g.objects(subj, p):
                    return str(o)
            return _extract_local_name(str(subj))

        def _get_synonyms(subj: URIRef) -> List[str]:
            syns: List[str] = []
            for p in [SKOS.altLabel, SKOS.hiddenLabel]:
                for o in g.objects(subj, p):
                    s = str(o)
                    if s and s not in syns:
                        syns.append(s)
            return syns

        def _get_comment(subj: URIRef) -> str:
            for o in g.objects(subj, RDFS.comment):
                return str(o)
            return ""

        # Classes
        for s in g.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef) and str(s) not in seen_iris:
                iri = str(s)
                seen_iris.add(iri)
                supers = [str(o) for o in g.objects(s, RDFS.subClassOf) if isinstance(o, URIRef)]
                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": _get_label(s),
                    "entity_type": "Class",
                    "description": _get_comment(s),
                    "synonyms": _get_synonyms(s),
                    "superclasses": supers,
                    "metadata": {"superclasses": supers},
                })

        # Object Properties
        for s in g.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef) and str(s) not in seen_iris:
                iri = str(s)
                seen_iris.add(iri)
                domains = [str(o) for o in g.objects(s, RDFS.domain) if isinstance(o, URIRef)]
                ranges = [str(o) for o in g.objects(s, RDFS.range) if isinstance(o, URIRef)]
                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": _get_label(s),
                    "entity_type": "ObjectProperty",
                    "description": _get_comment(s),
                    "synonyms": _get_synonyms(s),
                    "domain": domains,
                    "range": ranges,
                    "metadata": {"domain": domains, "range": ranges},
                })

        # Datatype Properties
        for s in g.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef) and str(s) not in seen_iris:
                iri = str(s)
                seen_iris.add(iri)
                domains = [str(o) for o in g.objects(s, RDFS.domain) if isinstance(o, URIRef)]
                ranges = [str(o) for o in g.objects(s, RDFS.range) if isinstance(o, URIRef)]
                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": _get_label(s),
                    "entity_type": "DatatypeProperty",
                    "description": _get_comment(s),
                    "synonyms": _get_synonyms(s),
                    "domain": domains,
                    "range": ranges,
                    "metadata": {"domain": domains, "range": ranges},
                })

        # Individuals
        for s in g.subjects(RDF.type, OWL.NamedIndividual):
            if isinstance(s, URIRef) and str(s) not in seen_iris:
                iri = str(s)
                seen_iris.add(iri)
                types = [str(o) for o in g.objects(s, RDF.type) if isinstance(o, URIRef) and o != OWL.NamedIndividual]
                payloads.append({
                    "id": _extract_local_name(iri),
                    "iri": iri,
                    "label": _get_label(s),
                    "entity_type": "Individual",
                    "description": _get_comment(s),
                    "synonyms": _get_synonyms(s),
                    "types": types,
                    "metadata": {"types": types},
                })

        return payloads

    def build_index(self) -> OntologyIndexBuilder:
        """Extract and index all classes, properties, and individuals from the active ontology loader."""
        payloads = self._extract_from_loader_lists()
        if not payloads:
            payloads = self._extract_from_graph_fallback()

        if not payloads:
            logger.warning("No ontology entities found to index.")
            return self

        # Format texts for embedding
        texts = [_format_entity_for_embedding(p) for p in payloads]
        logger.info(
            "Embedding %d ontology concepts with embedder (dim=%d)...",
            len(texts),
            self.embedder.dimension,
        )
        vectors = self.embedder.encode(texts, batch_size=64, normalize=True)

        self.index.add(vectors, payloads)
        for p in payloads:
            self._entities[p["iri"]] = p

        logger.info(
            "Successfully built ontology vector index: %d concepts indexed.",
            len(self.index),
        )
        return self

    def build_from_file(self, file_path: Union[str, Path]) -> OntologyIndexBuilder:
        """Load ontology from a turtle/rdf file and index it."""
        self.loader.load_file(file_path)
        return self.build_index()

    def build_from_graph(self, graph: rdflib.Graph) -> OntologyIndexBuilder:
        """Index concepts from an existing rdflib.Graph."""
        self.loader = OntologyLoader(graph=graph)
        return self.build_index()

    def add_custom_entity(
        self,
        iri: str,
        label: str,
        entity_type: str,
        description: str = "",
        synonyms: Optional[List[str]] = None,
        domain: Optional[List[str]] = None,
        range_: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Manually add an extra entity or instance into the vector index."""
        payload = {
            "id": _extract_local_name(iri),
            "iri": iri,
            "label": label,
            "entity_type": entity_type,
            "description": description,
            "synonyms": synonyms or [],
            "domain": domain or [],
            "range": range_ or [],
            "types": types or [],
            "metadata": metadata or {},
        }
        text = _format_entity_for_embedding(payload)
        vec = self.embedder.encode_single(text, normalize=True)
        self.index.add(vec.reshape(1, -1), [payload])
        self._entities[iri] = payload

    # -------------------------------------------------------------------------
    # Search and Retrieval API
    # -------------------------------------------------------------------------

    def search(
        self,
        query_text: str,
        top_k: int = 10,
        filter_type: Optional[Union[str, Sequence[str]]] = None,
    ) -> List[ScoredMatch]:
        """Search ontology vector index with dense query embedding and cosine ranking."""
        if not query_text or not query_text.strip():
            return []

        q_vec = self.embedder.encode_single(query_text, normalize=True)
        return self.index.search(q_vec, top_k=top_k, filter_type=filter_type)

    def search_concept(
        self,
        query_text: str,
        top_k: int = 10,
        filter_type: Optional[Union[str, Sequence[str]]] = None,
    ) -> List[ScoredMatch]:
        """Search general ontology concepts (classes, properties, individuals)."""
        return self.search(query_text, top_k=top_k, filter_type=filter_type)

    def search_class(self, query_text: str, top_k: int = 10) -> List[ScoredMatch]:
        """Search ontology classes only."""
        return self.search(query_text, top_k=top_k, filter_type="Class")

    def search_relation(self, query_text: str, top_k: int = 10) -> List[ScoredMatch]:
        """Search ontology relationships (ObjectProperty and DatatypeProperty)."""
        return self.search(
            query_text,
            top_k=top_k,
            filter_type=["ObjectProperty", "DatatypeProperty", "Property"],
        )

    def search_object_property(self, query_text: str, top_k: int = 10) -> List[ScoredMatch]:
        """Search OWL ObjectProperties."""
        return self.search(query_text, top_k=top_k, filter_type="ObjectProperty")

    def search_datatype_property(self, query_text: str, top_k: int = 10) -> List[ScoredMatch]:
        """Search OWL DatatypeProperties."""
        return self.search(query_text, top_k=top_k, filter_type="DatatypeProperty")

    def search_individual(self, query_text: str, top_k: int = 10) -> List[ScoredMatch]:
        """Search Named Individuals and domain instances."""
        return self.search(query_text, top_k=top_k, filter_type="Individual")

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self, path: Union[str, Path]) -> None:
        """Save vector index and builder state to disk."""
        target_path = Path(path)
        self.index.save(target_path)
        logger.info("OntologyIndexBuilder saved index to %s", target_path)

    @classmethod
    def load(
        cls,
        path: Union[str, Path],
        embedder: Optional[BaseEmbedder] = None,
    ) -> OntologyIndexBuilder:
        """Load an existing index from disk."""
        target_path = Path(path)
        loaded_index = VectorIndex.load(target_path)
        emb = embedder if embedder is not None else TextEmbedder(fallback_dimension=loaded_index.dimension)

        builder = cls(embedder=emb, index=loaded_index)
        for p in loaded_index.payloads:
            if "iri" in p:
                builder._entities[p["iri"]] = p
        logger.info(
            "Loaded OntologyIndexBuilder with %d entities from %s",
            len(builder.index),
            target_path,
        )
        return builder
