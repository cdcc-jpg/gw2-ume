"""Stage 0: One-Time Ontology Setup, Introspection, Hierarchy Walker, and Indexer.

Zero Domain Semantics in Python: Everything is dynamically discovered from the RDF graph.
Provides:
- Hierarchy Walker: rdfs:subClassOf, rdfs:domain, rdfs:range, rdfs:label, rdfs:comment,
  skos:prefLabel, skos:altLabel, owl:disjointWith, owl:AllDisjointClasses.
- Summary Generator:
  - Classes: "{label}: {definition} (parent: {parent_class})"
  - Properties: "{label}: {definition} (domain: {domain_class}, range: {range_class})"
- String Index Sets:
  - Exact (0.98), Normalised (0.95), TokenSubset (0.70-0.92), Containment (0.51-0.85), Fuzzy (ratio * 0.92).
- Vector Embedding Index:
  - Dense cosine similarity search (FAISS-Edge >= 0.40).
"""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

SHACL = Namespace("http://www.w3.org/ns/shacl#")


def normalize_string(s: str) -> str:
    """Normalize string by removing non-alphanumeric chars, lowercasing, and stripping."""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def tokenize_string(s: str) -> List[str]:
    """Tokenize camelCase, snake_case, kebab-case, or spaced strings."""
    # Split camelCase and letter-digit transitions
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", s)
    s = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", s)
    # Replace non-alphanumeric with spaces
    tokens = re.findall(r"[A-Za-z0-9]+", s.lower())
    return [t for t in tokens if t]


@dataclass
class ClassInfo:
    """Ontology class metadata dynamically discovered from graph."""
    uri: str
    label: str
    pref_label: Optional[str] = None
    alt_labels: List[str] = field(default_factory=list)
    comment: str = ""
    super_classes: List[str] = field(default_factory=list)
    sub_classes: List[str] = field(default_factory=list)
    disjoint_with: Set[str] = field(default_factory=set)
    summary: str = ""


@dataclass
class PropertyInfo:
    """Ontology property metadata dynamically discovered from graph."""
    uri: str
    label: str
    pref_label: Optional[str] = None
    alt_labels: List[str] = field(default_factory=list)
    comment: str = ""
    property_type: str = "DatatypeProperty"  # DatatypeProperty, ObjectProperty, Property
    domains: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    super_properties: List[str] = field(default_factory=list)
    sub_properties: List[str] = field(default_factory=list)
    summary: str = ""
    min_inclusive: Optional[float] = None
    max_inclusive: Optional[float] = None


class LightweightEmbedder:
    """Fast, zero-dependency character n-gram + token TF-IDF embedder.
    Used when SentenceTransformer is unavailable or offline.
    """

    def __init__(self, n_features: int = 512):
        self.n_features = n_features
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[int, float] = {}

    def fit(self, texts: List[str]) -> LightweightEmbedder:
        doc_counts: Dict[int, int] = {}
        for text in texts:
            features = self._extract_features(text)
            seen_in_doc: Set[int] = set()
            for f in features:
                idx = self._hash_feature(f)
                if idx not in seen_in_doc:
                    seen_in_doc.add(idx)
                    doc_counts[idx] = doc_counts.get(idx, 0) + 1

        n_docs = max(len(texts), 1)
        for idx, count in doc_counts.items():
            self.idf[idx] = math.log((1 + n_docs) / (1 + count)) + 1.0
        return self

    def _hash_feature(self, feature: str) -> int:
        return hash(feature) % self.n_features

    def _extract_features(self, text: str) -> List[str]:
        tokens = tokenize_string(text)
        features = list(tokens)
        clean = normalize_string(text)
        for i in range(len(clean) - 2):
            features.append(f"3g:{clean[i:i+3]}")
        return features

    def encode(self, texts: List[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.n_features), dtype=np.float32)
        for i, text in enumerate(texts):
            features = self._extract_features(text)
            counts: Dict[int, float] = {}
            for f in features:
                idx = self._hash_feature(f)
                counts[idx] = counts.get(idx, 0.0) + 1.0
            for idx, count in counts.items():
                vectors[i, idx] = count * self.idf.get(idx, 1.0)
            norm = np.linalg.norm(vectors[i])
            if norm > 1e-8:
                vectors[i] /= norm
        return vectors


class OntologyIndex:
    """Central dynamic ontology index constructed from an RDF graph.
    Maintains class and property metadata, summaries, string indexes, and vector embeddings.
    Zero Domain Semantics: all facts originate from the RDF graph.
    """

    def __init__(
        self,
        graph: Optional[Graph] = None,
        use_sentence_transformers: bool = True,
    ):
        self.graph = graph if graph is not None else Graph()
        self.classes: Dict[str, ClassInfo] = {}
        self.properties: Dict[str, PropertyInfo] = {}
        
        # Label to URIs maps
        self.class_label_map: Dict[str, Set[str]] = {}
        self.property_label_map: Dict[str, Set[str]] = {}

        # Disjoint classes mapping
        self.disjoint_map: Dict[str, Set[str]] = {}

        # Embedder & Embeddings
        self.use_sentence_transformers = use_sentence_transformers
        self.st_model = None
        self.embedder = LightweightEmbedder()
        self.property_uris: List[str] = []
        self.property_embeddings: Optional[np.ndarray] = None
        self.class_uris: List[str] = []
        self.class_embeddings: Optional[np.ndarray] = None

        if len(self.graph) > 0:
            self.build_index()

    def load_graph(self, graph_or_path: Union[Graph, str, Path]) -> OntologyIndex:
        """Load RDF graph from rdflib.Graph or file path."""
        if isinstance(graph_or_path, Graph):
            self.graph = graph_or_path
        else:
            path = Path(graph_or_path)
            if not path.exists():
                raise FileNotFoundError(f"Ontology path not found: {path}")
            fmt = "turtle" if path.suffix in [".ttl", ".turtle"] else None
            self.graph.parse(location=str(path), format=fmt)
        self.build_index()
        return self

    def build_index(self) -> None:
        """Walks the RDF graph and dynamically extracts classes, properties, and indexes."""
        self._introspect_classes()
        self._introspect_properties()
        self._build_summaries()
        self._build_vector_index()

    def _get_local_name(self, uri: Union[URIRef, str]) -> str:
        s = str(uri)
        if "#" in s:
            return s.split("#")[-1]
        return s.rstrip("/").split("/")[-1]

    def _get_labels_for_entity(self, uri: URIRef) -> Tuple[str, Optional[str], List[str]]:
        labels: List[str] = [str(o) for o in self.graph.objects(uri, RDFS.label) if isinstance(o, Literal)]
        pref_labels: List[str] = [str(o) for o in self.graph.objects(uri, SKOS.prefLabel) if isinstance(o, Literal)]
        alt_labels: List[str] = [str(o) for o in self.graph.objects(uri, SKOS.altLabel) if isinstance(o, Literal)]

        local_name = self._get_local_name(uri)
        split_local = re.sub(r"([a-z])([A-Z])", r"\1 \2", local_name)
        split_local = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", split_local)
        split_local = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", split_local)
        split_local = split_local.replace("_", " ").strip()

        pref = pref_labels[0] if pref_labels else None
        main_label = pref if pref else (labels[0] if labels else split_local)
        
        all_alts = list(alt_labels)
        for l in labels:
            if l != main_label and l not in all_alts:
                all_alts.append(l)

        if local_name not in all_alts and local_name != main_label:
            all_alts.append(local_name)
        if split_local not in all_alts and split_local != main_label:
            all_alts.append(split_local)

        return main_label, pref, all_alts

    def _get_comment(self, uri: URIRef) -> str:
        for p in (RDFS.comment, SKOS.definition):
            for o in self.graph.objects(uri, p):
                if isinstance(o, Literal):
                    return str(o).strip()
        return ""

    def _introspect_classes(self) -> None:
        class_uris: Set[URIRef] = set()
        for s in self.graph.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                class_uris.add(s)
        for s in self.graph.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                class_uris.add(s)
        for s in self.graph.subjects(RDF.type, SKOS.Concept):
            if isinstance(s, URIRef):
                class_uris.add(s)
        # Also include subjects/objects of rdfs:subClassOf and skos:broader/narrower
        for s, o in self.graph.subject_objects(RDFS.subClassOf):
            if isinstance(s, URIRef):
                class_uris.add(s)
            if isinstance(o, URIRef):
                class_uris.add(o)
        for s, o in self.graph.subject_objects(SKOS.broader):
            if isinstance(s, URIRef):
                class_uris.add(s)
            if isinstance(o, URIRef):
                class_uris.add(o)

        for c_uri in class_uris:
            uri_str = str(c_uri)
            label, pref, alts = self._get_labels_for_entity(c_uri)
            comment = self._get_comment(c_uri)

            supers = [str(o) for o in self.graph.objects(c_uri, RDFS.subClassOf) if isinstance(o, URIRef) and o != c_uri]
            supers.extend([str(o) for o in self.graph.objects(c_uri, SKOS.broader) if isinstance(o, URIRef) and o != c_uri])
            subs = [str(s) for s in self.graph.subjects(RDFS.subClassOf, c_uri) if isinstance(s, URIRef) and s != c_uri]
            subs.extend([str(s) for s in self.graph.subjects(SKOS.narrower, c_uri) if isinstance(s, URIRef) and s != c_uri])

            disjoints: Set[str] = set()
            for o in self.graph.objects(c_uri, OWL.disjointWith):
                if isinstance(o, URIRef):
                    disjoints.add(str(o))
            for s in self.graph.subjects(OWL.disjointWith, c_uri):
                if isinstance(s, URIRef):
                    disjoints.add(str(s))

            info = ClassInfo(
                uri=uri_str,
                label=label,
                pref_label=pref,
                alt_labels=alts,
                comment=comment,
                super_classes=supers,
                sub_classes=subs,
                disjoint_with=disjoints,
            )
            self.classes[uri_str] = info
            self.disjoint_map[uri_str] = disjoints

            for l in [label] + alts + ([pref] if pref else []):
                norm = normalize_string(l)
                self.class_label_map.setdefault(norm, set()).add(uri_str)

        # Handle owl:AllDisjointClasses
        for bnode in self.graph.subjects(RDF.type, OWL.AllDisjointClasses):
            members_node = self.graph.value(bnode, OWL.members)
            if members_node:
                try:
                    members = [str(m) for m in self.graph.items(members_node) if isinstance(m, URIRef)]
                    for m1 in members:
                        for m2 in members:
                            if m1 != m2:
                                self.disjoint_map.setdefault(m1, set()).add(m2)
                                if m1 in self.classes:
                                    self.classes[m1].disjoint_with.add(m2)
                except Exception:
                    pass

    def _introspect_properties(self) -> None:
        prop_uris: Set[Tuple[URIRef, str]] = set()

        for s in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef):
                prop_uris.add((s, "DatatypeProperty"))
        for s in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef):
                prop_uris.add((s, "ObjectProperty"))
        for s in self.graph.subjects(RDF.type, RDF.Property):
            if isinstance(s, URIRef) and not any(s == p[0] for p in prop_uris):
                prop_uris.add((s, "Property"))

        for p in self.graph.subjects(RDFS.domain, None):
            if isinstance(p, URIRef) and not any(p == u[0] for u in prop_uris):
                prop_uris.add((p, "Property"))
        for p in self.graph.subjects(RDFS.range, None):
            if isinstance(p, URIRef) and not any(p == u[0] for u in prop_uris):
                prop_uris.add((p, "Property"))

        # Add universal standard RDF/RDFS/SKOS annotation properties
        standard_annot_props = [
            (RDFS.label, "AnnotationProperty", "label", ["name", "title"], "Human-readable label or name of an entity.", [str(XSD.string)]),
            (RDFS.comment, "AnnotationProperty", "comment", ["description", "notes", "summary"], "Human-readable description or notes.", [str(XSD.string)]),
            (SKOS.prefLabel, "AnnotationProperty", "preferred label", ["pref label"], "Preferred lexical label for a resource.", [str(XSD.string)]),
            (SKOS.altLabel, "AnnotationProperty", "alternative label", ["alias", "synonym"], "Alternative lexical label for a resource.", [str(XSD.string)]),
            (SKOS.definition, "AnnotationProperty", "definition", ["definition", "meaning"], "Complete explanation of the intended meaning.", [str(XSD.string)]),
        ]
        for p_uri, p_type, p_label, p_alts, p_comment, p_ranges in standard_annot_props:
            uri_str = str(p_uri)
            info = PropertyInfo(
                uri=uri_str,
                label=p_label,
                pref_label=p_label,
                alt_labels=p_alts,
                comment=p_comment,
                property_type=p_type,
                domains=[],
                ranges=p_ranges,
                super_properties=[],
                sub_properties=[],
            )
            self.properties[uri_str] = info
            for l in [p_label] + p_alts:
                norm = normalize_string(l)
                self.property_label_map.setdefault(norm, set()).add(uri_str)

        for p_uri, p_type in prop_uris:
            uri_str = str(p_uri)
            label, pref, alts = self._get_labels_for_entity(p_uri)
            comment = self._get_comment(p_uri)

            domains = []
            for o in self.graph.objects(p_uri, RDFS.domain):
                if isinstance(o, URIRef):
                    domains.append(str(o))
                elif isinstance(o, BNode):
                    union_list = self.graph.value(o, OWL.unionOf)
                    if union_list:
                        try:
                            for m in self.graph.items(union_list):
                                if isinstance(m, URIRef):
                                    domains.append(str(m))
                        except Exception:
                            pass

            ranges = []
            for o in self.graph.objects(p_uri, RDFS.range):
                if isinstance(o, URIRef):
                    ranges.append(str(o))
                elif isinstance(o, BNode):
                    union_list = self.graph.value(o, OWL.unionOf)
                    if union_list:
                        try:
                            for m in self.graph.items(union_list):
                                if isinstance(m, URIRef):
                                    ranges.append(str(m))
                        except Exception:
                            pass

            supers = [str(o) for o in self.graph.objects(p_uri, RDFS.subPropertyOf) if isinstance(o, URIRef)]
            subs = [str(s) for s in self.graph.subjects(RDFS.subPropertyOf, p_uri) if isinstance(s, URIRef)]

            # SHACL Bounds Introspection
            min_inclusive: Optional[float] = None
            max_inclusive: Optional[float] = None

            # Look for SHACL shapes targeting p_uri or on p_uri itself
            target_shapes = set(self.graph.subjects(SHACL.path, p_uri))
            target_shapes.add(p_uri)
            for shape in target_shapes:
                sh_min = self.graph.value(shape, SHACL.minInclusive)
                if sh_min is not None:
                    try:
                        val = float(sh_min.toPython()) if hasattr(sh_min, "toPython") else float(str(sh_min))
                        if min_inclusive is None or val > min_inclusive:
                            min_inclusive = val
                    except (ValueError, TypeError):
                        pass

                sh_max = self.graph.value(shape, SHACL.maxInclusive)
                if sh_max is not None:
                    try:
                        val = float(sh_max.toPython()) if hasattr(sh_max, "toPython") else float(str(sh_max))
                        if max_inclusive is None or val < max_inclusive:
                            max_inclusive = val
                    except (ValueError, TypeError):
                        pass

            # Extract bounds from comments using regex, e.g. (0-80), (0 to 80), (0–80)
            if comment:
                m = re.search(r"\((\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\)", comment, re.IGNORECASE)
                if not m:
                    m = re.search(r"\[\s*(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*\]", comment, re.IGNORECASE)
                if not m:
                    m = re.search(r"\b(?:range|between)\s*:?\s*(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\b", comment, re.IGNORECASE)
                if m:
                    try:
                        c_min = float(m.group(1))
                        c_max = float(m.group(2))
                        if min_inclusive is None:
                            min_inclusive = c_min
                        if max_inclusive is None:
                            max_inclusive = c_max
                    except (ValueError, TypeError):
                        pass

            info = PropertyInfo(
                uri=uri_str,
                label=label,
                pref_label=pref,
                alt_labels=alts,
                comment=comment,
                property_type=p_type,
                domains=domains,
                ranges=ranges,
                super_properties=supers,
                sub_properties=subs,
                min_inclusive=min_inclusive,
                max_inclusive=max_inclusive,
            )
            self.properties[uri_str] = info

            for l in [label] + alts + ([pref] if pref else []):
                norm = normalize_string(l)
                self.property_label_map.setdefault(norm, set()).add(uri_str)

    def _build_summaries(self) -> None:
        """Build text summaries for classes and properties according to spec:
        - Classes: "{label}: {definition} (parent: {parent_class})"
        - Properties: "{label}: {definition} (domain: {domain_class}, range: {range_class})"
        """
        for uri, c in self.classes.items():
            parent_str = ", ".join([self._get_local_name(p) for p in c.super_classes]) if c.super_classes else "owl:Thing"
            definition = c.comment if c.comment else c.label
            c.summary = f"{c.label}: {definition} (parent: {parent_str})"

        for uri, p in self.properties.items():
            domain_str = ", ".join([self._get_local_name(d) for d in p.domains]) if p.domains else "Any"
            range_str = ", ".join([self._get_local_name(r) for r in p.ranges]) if p.ranges else "Any"
            definition = p.comment if p.comment else p.label
            p.summary = f"{p.label}: {definition} (domain: {domain_str}, range: {range_str})"

    def _build_vector_index(self) -> None:
        """Build vector embeddings over property and class summaries."""
        self.property_uris = list(self.properties.keys())
        self.class_uris = list(self.classes.keys())

        prop_summaries = [self.properties[u].summary for u in self.property_uris]
        cls_summaries = [self.classes[u].summary for u in self.class_uris]

        all_texts = prop_summaries + cls_summaries
        if not all_texts:
            return

        if self.use_sentence_transformers:
            try:
                from sentence_transformers import SentenceTransformer
                if self.st_model is None:
                    self.st_model = SentenceTransformer("all-MiniLM-L6-v2")
                self.property_embeddings = self.st_model.encode(prop_summaries, normalize_embeddings=True)
                self.class_embeddings = self.st_model.encode(cls_summaries, normalize_embeddings=True)
                return
            except Exception:
                pass

        self.embedder.fit(all_texts)
        self.property_embeddings = self.embedder.encode(prop_summaries)
        self.class_embeddings = self.embedder.encode(cls_summaries)

    def encode_text(self, text: str) -> np.ndarray:
        """Encode query text using the active embedding model."""
        if self.st_model is not None:
            return self.st_model.encode([text], normalize_embeddings=True)[0]
        return self.embedder.encode([text])[0]

    def are_classes_disjoint(self, class_a: str, class_b: str) -> bool:
        """Dynamically check if two classes are declared disjoint in the RDF graph."""
        if class_a == class_b:
            return False
        disjoints_a = self.disjoint_map.get(class_a, set())
        if class_b in disjoints_a:
            return True
        disjoints_b = self.disjoint_map.get(class_b, set())
        if class_a in disjoints_b:
            return True
        return False

    def get_subclasses(self, class_uri: str, recursive: bool = True) -> Set[str]:
        """Returns all subclasses of a given class URI."""
        visited: Set[str] = set()
        queue = [class_uri]
        while queue:
            curr = queue.pop(0)
            c = self.classes.get(curr)
            if c:
                for sub in c.sub_classes:
                    if sub not in visited and sub != class_uri:
                        visited.add(sub)
                        if recursive:
                            queue.append(sub)
        return visited
