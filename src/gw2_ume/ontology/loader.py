"""RDFLib ontology loader and introspector for Guild Wars 2 OWL 2 ontologies."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple, Union

import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from gw2_ume.ontology.schema import (
    DatatypeProperty,
    Individual,
    ObjectProperty,
    OntologyClass,
    Restriction,
)

# Official Priory Namespaces
from gw2_ume.ontology.namespaces import (
    DEFAULT_PRIORY_PREFIXES,
    PRIORY,
    PRIORY_REF,
    ITEM,
    RECIPE,
    RARITY,
    WEAPON,
    DISCIPLINE,
    CURRENCY,
    ARMOR,
    SLOT,
    ITEMTYPE,
    GAMEMODE,
    ZONE,
    VENDOR,
)

# Standard and GW2 Namespaces
GW2 = Namespace("https://schema.gw2ume.org/core#")
GW2LEG = Namespace("https://schema.gw2ume.org/legendary#")
GW2RES = Namespace("https://priory.gw2/id/")
SCHEMA = Namespace("http://schema.org/")

DEFAULT_PREFIXES = {
    "gw2": GW2,
    "gw2leg": GW2LEG,
    "gw2res": GW2RES,
    **DEFAULT_PRIORY_PREFIXES,
    "schema": SCHEMA,
    "rdfs": RDFS,
    "owl": OWL,
    "skos": SKOS,
    "rdf": RDF,
    "xsd": XSD,
}


class OntologyLoader:
    """Loads, binds, and provides rich introspection over Guild Wars 2 OWL 2 ontologies."""

    def __init__(
        self,
        ontology_path: Optional[Union[str, Path]] = None,
        graph: Optional[Graph] = None,
        auto_load_defaults: bool = False,
    ) -> None:
        self._graph: Graph = graph if graph is not None else Graph()
        self._ontology_path: Optional[Path] = Path(ontology_path) if ontology_path else None
        self._bind_default_prefixes()

        if self._ontology_path and self._ontology_path.exists():
            self.load_file(self._ontology_path)
        elif auto_load_defaults:
            self.load_defaults()

    def _bind_default_prefixes(self) -> None:
        """Bind common namespaces to the graph for pretty serialization and query resolution."""
        for prefix, ns in DEFAULT_PREFIXES.items():
            self._graph.bind(prefix, ns, override=True)

    @property
    def graph(self) -> Graph:
        """Return the underlying rdflib.Graph instance."""
        return self._graph

    def get_graph(self) -> Graph:
        """Return the underlying rdflib.Graph instance."""
        return self._graph

    @classmethod
    def default_ontologies_path(cls) -> Path:
        """Returns the default directory path containing the .ttl files."""
        candidates = [
            Path("ontologies"),
            Path(__file__).resolve().parent.parent.parent.parent / "ontologies",
            Path(__file__).resolve().parent.parent.parent / "ontologies",
            Path.cwd() / "ontologies",
        ]
        for p in candidates:
            if p.exists() and p.is_dir():
                return p.resolve()
        return Path("ontologies").resolve()

    def load_defaults(self) -> OntologyLoader:
        """Loads both local ontologies and master Priory ontologies from gw2-priory-def and gw2-priory-ref if present."""
        # 1. Check for sibling master Priory repositories
        workspace_parent = Path.cwd().parent
        priory_def_dir = workspace_parent / "gw2-priory-def" / "ontology"
        priory_ref_dir = workspace_parent / "gw2-priory-ref" / "vocab"

        loaded_priory = False
        if priory_def_dir.exists() and priory_def_dir.is_dir():
            for ttl in priory_def_dir.rglob("*.ttl"):
                try:
                    self.load_file(ttl)
                    loaded_priory = True
                except Exception:
                    pass

        if priory_ref_dir.exists() and priory_ref_dir.is_dir():
            for ttl in priory_ref_dir.rglob("*.ttl"):
                try:
                    self.load_file(ttl)
                    loaded_priory = True
                except Exception:
                    pass

        # 2. Also load local base ontologies
        ont_dir = self.default_ontologies_path()
        core_file = ont_dir / "gw2_core.ttl"
        leg_file = ont_dir / "gw2_legendary.ttl"

        if core_file.exists():
            self.load_file(core_file)
        if leg_file.exists():
            self.load_file(leg_file)

        # 3. Dynamically populate controlled reference vocabularies
        from gw2_ume.ontology.vocab import (
            CONTROLLED_DISCIPLINES,
            CONTROLLED_CURRENCIES,
            CONTROLLED_RARITIES,
            CONTROLLED_WEAPONS,
            CLASS_CRAFTING_DISCIPLINE,
            CLASS_CURRENCY,
            CLASS_RARITY,
            CLASS_WEAPON,
        )
        for disc_key, disc_uri in CONTROLLED_DISCIPLINES.items():
            self._graph.add((disc_uri, RDF.type, CLASS_CRAFTING_DISCIPLINE))
            self._graph.add((disc_uri, RDF.type, OWL.NamedIndividual))
            self._graph.add((disc_uri, RDFS.label, Literal(disc_key.replace("_", " ").title(), datatype=XSD.string)))

        for curr_key, curr_uri in CONTROLLED_CURRENCIES.items():
            self._graph.add((curr_uri, RDF.type, CLASS_CURRENCY))
            self._graph.add((curr_uri, RDF.type, OWL.NamedIndividual))
            self._graph.add((curr_uri, RDFS.label, Literal(curr_key.replace("_", " ").title(), datatype=XSD.string)))

        for rar_key, rar_uri in CONTROLLED_RARITIES.items():
            self._graph.add((rar_uri, RDF.type, CLASS_RARITY))
            self._graph.add((rar_uri, RDF.type, OWL.NamedIndividual))
            self._graph.add((rar_uri, RDFS.label, Literal(rar_key.capitalize(), datatype=XSD.string)))

        weapon_discipline_map = {
            "staff": DISCIPLINE.artificer,
            "scepter": DISCIPLINE.artificer,
            "focus": DISCIPLINE.artificer,
            "sword": DISCIPLINE.weaponsmith,
            "greatsword": DISCIPLINE.weaponsmith,
            "axe": DISCIPLINE.weaponsmith,
            "dagger": DISCIPLINE.weaponsmith,
            "hammer": DISCIPLINE.weaponsmith,
            "mace": DISCIPLINE.weaponsmith,
            "shield": DISCIPLINE.weaponsmith,
            "pistol": DISCIPLINE.huntsman,
            "rifle": DISCIPLINE.huntsman,
            "short_bow": DISCIPLINE.huntsman,
            "longbow": DISCIPLINE.huntsman,
            "torch": DISCIPLINE.huntsman,
            "warhorn": DISCIPLINE.huntsman,
        }

        for wpn_key, wpn_uri in CONTROLLED_WEAPONS.items():
            self._graph.add((wpn_uri, RDF.type, CLASS_WEAPON))
            self._graph.add((wpn_uri, RDF.type, OWL.NamedIndividual))
            self._graph.add((wpn_uri, RDFS.label, Literal(wpn_key.replace("_", " ").title(), datatype=XSD.string)))
            disc_target = weapon_discipline_map.get(wpn_key)
            if disc_target:
                from gw2_ume.ontology.vocab import PROP_CRAFTED_BY_DISCIPLINE
                self._graph.add((wpn_uri, PROP_CRAFTED_BY_DISCIPLINE, disc_target))

        from gw2_ume.ontology.schema import ENTITY_CATALOG
        from gw2_ume.ontology.vocab import (
            CLASS_ITEM,
            PROP_CRAFTED_BY_DISCIPLINE,
            PROP_IS_PRECURSOR_OF,
            PROP_HAS_PRECURSOR,
            PROP_UPGRADES_TO,
            PROP_REQUIRES_INGREDIENT,
        )

        for item_key, item_data in ENTITY_CATALOG.items():
            item_uri = URIRef(str(item_data["uri"]))
            item_type = URIRef(str(item_data.get("type", CLASS_ITEM)))
            self._graph.add((item_uri, RDF.type, item_type))
            self._graph.add((item_uri, RDF.type, OWL.NamedIndividual))
            self._graph.add((item_uri, RDFS.label, Literal(item_data["label"], datatype=XSD.string)))
            if "discipline" in item_data:
                disc_name = item_data["discipline"].lower().replace(" ", "_")
                disc_uri = CONTROLLED_DISCIPLINES.get(disc_name)
                if disc_uri:
                    self._graph.add((item_uri, PROP_CRAFTED_BY_DISCIPLINE, disc_uri))

        return self

    def load_file(self, file_path: Union[str, Path], format: Optional[str] = None) -> Graph:
        """Parses an ontology file into the graph."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Ontology file not found: {path}")

        fmt = format
        if fmt is None:
            if path.suffix in [".ttl", ".turtle"]:
                fmt = "turtle"
            elif path.suffix in [".rdf", ".owl", ".xml"]:
                fmt = "xml"
            elif path.suffix in [".jsonld", ".json"]:
                fmt = "json-ld"
            elif path.suffix in [".nt"]:
                fmt = "nt"
            else:
                fmt = "turtle"

        self._graph.parse(location=str(path), format=fmt)
        self._ontology_path = path
        return self._graph

    def load_turtle_string(self, turtle_content: str) -> Graph:
        """Parses a Turtle string into the graph."""
        self._graph.parse(data=turtle_content, format="turtle")
        return self._graph

    def load_directory(self, dir_path: Union[str, Path], pattern: str = "*.ttl") -> OntologyLoader:
        """Parses all matching ontology files in a directory."""
        directory = Path(dir_path)
        if not directory.exists() or not directory.is_dir():
            raise NotADirectoryError(f"Directory not found: {directory}")

        for file_path in sorted(directory.glob(pattern)):
            self.load_file(file_path)
        return self

    def resolve_iri(self, term: Union[str, URIRef, BNode]) -> Union[URIRef, BNode]:
        """Resolves prefixed strings like 'gw2:Item', short local names, or full URI strings into URIRef."""
        if isinstance(term, (URIRef, BNode)):
            return term
        if not isinstance(term, str):
            raise TypeError(f"Expected str, URIRef or BNode, got {type(term)}")

        if ":" in term and not term.startswith("http://") and not term.startswith("https://") and not term.startswith("urn:"):
            prefix, local = term.split(":", 1)
            if prefix in DEFAULT_PREFIXES:
                ns = DEFAULT_PREFIXES[prefix]
                return URIRef(f"{ns}{local}")
            for p, ns in self._graph.namespaces():
                if p == prefix:
                    return URIRef(f"{ns}{local}")
            return URIRef(term)

        if term.startswith("http://") or term.startswith("https://") or term.startswith("urn:"):
            return URIRef(term)

        raw_uri = URIRef(term)
        if (raw_uri, None, None) in self._graph or (None, None, raw_uri) in self._graph or (None, raw_uri, None) in self._graph:
            return raw_uri

        # Check default namespaces (gw2, gw2leg, item, recipe, etc.)
        for prefix in ("gw2", "gw2leg", "item", "recipe", "discipline", "currency", "weapon", "armor", "vendor", "zone", "schema", "rdfs", "owl"):
            if prefix in DEFAULT_PREFIXES:
                ns = DEFAULT_PREFIXES[prefix]
                cand = URIRef(f"{ns}{term}")
                if (cand, None, None) in self._graph or (None, cand, None) in self._graph or (None, None, cand) in self._graph:
                    return cand

        # Check all registered namespaces in graph
        for _, ns in self._graph.namespaces():
            cand = URIRef(f"{ns}{term}")
            if (cand, None, None) in self._graph or (None, cand, None) in self._graph or (None, None, cand) in self._graph:
                return cand

        # Fallback: search subjects and predicates ending with #{term} or /{term}
        for s in self._graph.subjects(RDF.type, None):
            if isinstance(s, URIRef):
                s_str = str(s)
                if s_str.endswith(f"#{term}") or s_str.endswith(f"/{term}"):
                    return s

        for p in self._graph.predicates(None, None):
            if isinstance(p, URIRef):
                p_str = str(p)
                if p_str.endswith(f"#{term}") or p_str.endswith(f"/{term}"):
                    return p

        return raw_uri

    def to_prefixed_name(self, uri: Union[str, URIRef]) -> str:
        """Converts a full URI to a prefixed string (e.g. gw2:Item) if possible."""
        uri_str = str(uri)
        for prefix, ns in DEFAULT_PREFIXES.items():
            ns_str = str(ns)
            if uri_str.startswith(ns_str):
                return f"{prefix}:{uri_str[len(ns_str):]}"
        for p, ns in self._graph.namespaces():
            ns_str = str(ns)
            if p and uri_str.startswith(ns_str):
                return f"{p}:{uri_str[len(ns_str):]}"
        return uri_str

    # -------------------------------------------------------------------------
    # Label and Annotation Helpers
    # -------------------------------------------------------------------------

    def get_labels(self, uri: Union[str, URIRef]) -> Dict[str, List[str]]:
        """Retrieves rdfs:label, skos:prefLabel, and skos:altLabel values for a resource."""
        res_uri = self.resolve_iri(uri)
        labels: List[str] = [str(o) for o in self._graph.objects(res_uri, RDFS.label) if isinstance(o, Literal)]
        pref_labels: List[str] = [str(o) for o in self._graph.objects(res_uri, SKOS.prefLabel) if isinstance(o, Literal)]
        alt_labels: List[str] = [str(o) for o in self._graph.objects(res_uri, SKOS.altLabel) if isinstance(o, Literal)]

        return {
            "label": labels,
            "prefLabel": pref_labels,
            "altLabel": alt_labels,
        }

    def get_comment(self, uri: Union[str, URIRef]) -> Optional[str]:
        """Retrieves rdfs:comment for a resource."""
        res_uri = self.resolve_iri(uri)
        for o in self._graph.objects(res_uri, RDFS.comment):
            return str(o)
        return None

    # -------------------------------------------------------------------------
    # Class Introspection
    # -------------------------------------------------------------------------

    def list_classes(self) -> List[OntologyClass]:
        """Lists all OWL/RDFS classes declared in the ontology."""
        class_iris: Set[URIRef] = set()
        for s in self._graph.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                class_iris.add(s)
        for s in self._graph.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                class_iris.add(s)

        results: List[OntologyClass] = []
        for iri in sorted(class_iris, key=str):
            cls_obj = self.get_class(iri)
            if cls_obj:
                results.append(cls_obj)
        return results

    def get_class(self, class_iri: Union[str, URIRef]) -> Optional[OntologyClass]:
        """Retrieves details of an OntologyClass."""
        iri = self.resolve_iri(class_iri)
        if not isinstance(iri, URIRef):
            return None

        is_class = (iri, RDF.type, OWL.Class) in self._graph or (iri, RDF.type, RDFS.Class) in self._graph
        has_subclass_rel = (iri, RDFS.subClassOf, None) in self._graph or (None, RDFS.subClassOf, iri) in self._graph
        if not is_class and not has_subclass_rel:
            return None

        labels_dict = self.get_labels(iri)
        label = labels_dict["label"][0] if labels_dict["label"] else None
        pref_label = labels_dict["prefLabel"][0] if labels_dict["prefLabel"] else None
        alt_labels = labels_dict["altLabel"]
        comment = self.get_comment(iri)

        super_classes = [str(o) for o in self.get_superclasses(iri, direct=True)]
        sub_classes = [str(s) for s in self.get_subclasses(iri, direct=True)]
        disjoint_with = [str(o) for o in self.get_disjoint_classes(iri)]
        equivalent_classes = [str(o) for o in self._graph.objects(iri, OWL.equivalentClass) if isinstance(o, URIRef)]

        restrictions: List[Restriction] = []
        for sc in self._graph.objects(iri, RDFS.subClassOf):
            if isinstance(sc, BNode) and (sc, RDF.type, OWL.Restriction) in self._graph:
                prop = self._graph.value(sc, OWL.onProperty)
                if prop:
                    prop_str = str(prop)
                    some_val = self._graph.value(sc, OWL.someValuesFrom)
                    all_val = self._graph.value(sc, OWL.allValuesFrom)
                    has_val = self._graph.value(sc, OWL.hasValue)
                    card = self._graph.value(sc, OWL.cardinality)
                    min_card = self._graph.value(sc, OWL.minCardinality)
                    max_card = self._graph.value(sc, OWL.maxCardinality)

                    if some_val:
                        restrictions.append(Restriction(prop_str, "someValuesFrom", target=str(some_val)))
                    elif all_val:
                        restrictions.append(Restriction(prop_str, "allValuesFrom", target=str(all_val)))
                    elif has_val:
                        restrictions.append(Restriction(prop_str, "hasValue", target=str(has_val)))
                    elif card:
                        restrictions.append(Restriction(prop_str, "cardinality", exact_cardinality=int(card)))
                    elif min_card or max_card:
                        restrictions.append(Restriction(
                            prop_str,
                            "cardinalityRange",
                            min_cardinality=int(min_card) if min_card else None,
                            max_cardinality=int(max_card) if max_card else None,
                        ))

        return OntologyClass(
            iri=str(iri),
            label=label,
            pref_label=pref_label,
            alt_labels=alt_labels,
            comment=comment,
            super_classes=super_classes,
            sub_classes=sub_classes,
            disjoint_with=disjoint_with,
            equivalent_classes=equivalent_classes,
            restrictions=restrictions,
        )

    def get_subclasses(self, class_iri: Union[str, URIRef], direct: bool = False) -> Set[URIRef]:
        """Returns subclasses of the given class. If direct=False, includes transitive subclasses."""
        iri = self.resolve_iri(class_iri)
        if not isinstance(iri, URIRef):
            return set()

        direct_subs: Set[URIRef] = {
            s for s in self._graph.subjects(RDFS.subClassOf, iri)
            if isinstance(s, URIRef) and s != iri
        }

        if direct:
            return direct_subs

        all_subs: Set[URIRef] = set(direct_subs)
        frontier = list(direct_subs)
        while frontier:
            current = frontier.pop()
            for s in self._graph.subjects(RDFS.subClassOf, current):
                if isinstance(s, URIRef) and s != current and s not in all_subs and s != iri:
                    all_subs.add(s)
                    frontier.append(s)
        return all_subs

    def get_superclasses(self, class_iri: Union[str, URIRef], direct: bool = False) -> Set[URIRef]:
        """Returns superclasses of the given class. If direct=False, includes transitive superclasses."""
        iri = self.resolve_iri(class_iri)
        if not isinstance(iri, URIRef):
            return set()

        direct_supers: Set[URIRef] = {
            o for o in self._graph.objects(iri, RDFS.subClassOf)
            if isinstance(o, URIRef) and o != iri
        }

        if direct:
            return direct_supers

        all_supers: Set[URIRef] = set(direct_supers)
        frontier = list(direct_supers)
        while frontier:
            current = frontier.pop()
            for o in self._graph.objects(current, RDFS.subClassOf):
                if isinstance(o, URIRef) and o != current and o not in all_supers and o != iri:
                    all_supers.add(o)
                    frontier.append(o)
        return all_supers

    def get_disjoint_classes(self, class_iri: Union[str, URIRef]) -> Set[URIRef]:
        """Returns classes directly or via owl:AllDisjointClasses declared disjoint with class_iri."""
        iri = self.resolve_iri(class_iri)
        disjoints: Set[URIRef] = set()

        # Direct owl:disjointWith
        for o in self._graph.objects(iri, OWL.disjointWith):
            if isinstance(o, URIRef):
                disjoints.add(o)
        for s in self._graph.subjects(OWL.disjointWith, iri):
            if isinstance(s, URIRef):
                disjoints.add(s)

        # owl:AllDisjointClasses
        for bnode in self._graph.subjects(RDF.type, OWL.AllDisjointClasses):
            members_node = self._graph.value(bnode, OWL.members)
            if members_node:
                try:
                    members = [m for m in self._graph.items(members_node) if isinstance(m, URIRef)]
                    if iri in members:
                        for m in members:
                            if m != iri:
                                disjoints.add(m)
                except Exception:
                    pass

        return disjoints

    def get_class_hierarchy(self, root_iri: Optional[Union[str, URIRef]] = None) -> Dict[str, Any]:
        """Builds a hierarchical tree dictionary starting from root_iri or top-level classes."""
        if root_iri is not None:
            root = self.resolve_iri(root_iri)
            return self._build_subclass_tree(root)

        all_classes = self.list_classes()
        top_classes = [
            c for c in all_classes
            if not self.get_superclasses(c.iri, direct=True)
        ]
        return {
            "root": "owl:Thing",
            "children": [self._build_subclass_tree(self.resolve_iri(c.iri)) for c in top_classes],
        }

    def _build_subclass_tree(self, class_iri: URIRef) -> Dict[str, Any]:
        cls_obj = self.get_class(class_iri)
        name = cls_obj.display_name if cls_obj else str(class_iri)
        direct_subs = sorted(self.get_subclasses(class_iri, direct=True), key=str)
        return {
            "iri": str(class_iri),
            "name": name,
            "children": [self._build_subclass_tree(sub) for sub in direct_subs],
        }

    # -------------------------------------------------------------------------
    # Property Introspection
    # -------------------------------------------------------------------------

    def list_object_properties(self) -> List[ObjectProperty]:
        """Lists all OWL Object Properties."""
        props: Set[URIRef] = set()
        for s in self._graph.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef):
                props.add(s)

        results: List[ObjectProperty] = []
        for iri in sorted(props, key=str):
            p_obj = self.get_object_property(iri)
            if p_obj:
                results.append(p_obj)
        return results

    def get_object_property(self, prop_iri: Union[str, URIRef]) -> Optional[ObjectProperty]:
        """Retrieves details of an ObjectProperty."""
        iri = self.resolve_iri(prop_iri)
        if not isinstance(iri, URIRef):
            return None

        is_obj_prop = (iri, RDF.type, OWL.ObjectProperty) in self._graph
        is_data_prop = (iri, RDF.type, OWL.DatatypeProperty) in self._graph
        if is_data_prop and not is_obj_prop:
            return None
        if not is_obj_prop and not (iri, RDFS.domain, None) in self._graph and not (iri, RDFS.range, None) in self._graph:
            return None

        labels_dict = self.get_labels(iri)
        label = labels_dict["label"][0] if labels_dict["label"] else None
        pref_label = labels_dict["prefLabel"][0] if labels_dict["prefLabel"] else None
        alt_labels = labels_dict["altLabel"]
        comment = self.get_comment(iri)

        domains = [str(o) for o in self._graph.objects(iri, RDFS.domain) if isinstance(o, URIRef)]
        ranges = [str(o) for o in self._graph.objects(iri, RDFS.range) if isinstance(o, URIRef)]

        inverse = self._graph.value(iri, OWL.inverseOf)
        inverse_str = str(inverse) if isinstance(inverse, URIRef) else None

        is_functional = (iri, RDF.type, OWL.FunctionalProperty) in self._graph
        is_transitive = (iri, RDF.type, OWL.TransitiveProperty) in self._graph
        is_symmetric = (iri, RDF.type, OWL.SymmetricProperty) in self._graph

        sub_props = [str(s) for s in self._graph.subjects(RDFS.subPropertyOf, iri) if isinstance(s, URIRef)]
        super_props = [str(o) for o in self._graph.objects(iri, RDFS.subPropertyOf) if isinstance(o, URIRef)]

        return ObjectProperty(
            iri=str(iri),
            label=label,
            pref_label=pref_label,
            alt_labels=alt_labels,
            comment=comment,
            domains=domains,
            ranges=ranges,
            inverse_of=inverse_str,
            is_functional=is_functional,
            is_transitive=is_transitive,
            is_symmetric=is_symmetric,
            sub_properties=sub_props,
            super_properties=super_props,
        )

    def list_datatype_properties(self) -> List[DatatypeProperty]:
        """Lists all OWL Datatype Properties."""
        props: Set[URIRef] = set()
        for s in self._graph.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef):
                props.add(s)

        results: List[DatatypeProperty] = []
        for iri in sorted(props, key=str):
            p_obj = self.get_datatype_property(iri)
            if p_obj:
                results.append(p_obj)
        return results

    def get_datatype_property(self, prop_iri: Union[str, URIRef]) -> Optional[DatatypeProperty]:
        """Retrieves details of a DatatypeProperty."""
        iri = self.resolve_iri(prop_iri)
        if not isinstance(iri, URIRef):
            return None

        is_data_prop = (iri, RDF.type, OWL.DatatypeProperty) in self._graph
        if not is_data_prop:
            return None

        labels_dict = self.get_labels(iri)
        label = labels_dict["label"][0] if labels_dict["label"] else None
        pref_label = labels_dict["prefLabel"][0] if labels_dict["prefLabel"] else None
        alt_labels = labels_dict["altLabel"]
        comment = self.get_comment(iri)

        domains = [str(o) for o in self._graph.objects(iri, RDFS.domain) if isinstance(o, URIRef)]
        ranges = [str(o) for o in self._graph.objects(iri, RDFS.range) if isinstance(o, URIRef)]
        is_functional = (iri, RDF.type, OWL.FunctionalProperty) in self._graph

        sub_props = [str(s) for s in self._graph.subjects(RDFS.subPropertyOf, iri) if isinstance(s, URIRef)]
        super_props = [str(o) for o in self._graph.objects(iri, RDFS.subPropertyOf) if isinstance(o, URIRef)]

        return DatatypeProperty(
            iri=str(iri),
            label=label,
            pref_label=pref_label,
            alt_labels=alt_labels,
            comment=comment,
            domains=domains,
            ranges=ranges,
            is_functional=is_functional,
            sub_properties=sub_props,
            super_properties=super_props,
        )

    def get_subproperties(self, prop_iri: Union[str, URIRef], direct: bool = False) -> Set[URIRef]:
        """Returns subproperties of a property."""
        iri = self.resolve_iri(prop_iri)
        if not isinstance(iri, URIRef):
            return set()

        direct_subs: Set[URIRef] = {
            s for s in self._graph.subjects(RDFS.subPropertyOf, iri)
            if isinstance(s, URIRef) and s != iri
        }
        if direct:
            return direct_subs

        all_subs: Set[URIRef] = set(direct_subs)
        frontier = list(direct_subs)
        while frontier:
            current = frontier.pop()
            for s in self._graph.subjects(RDFS.subPropertyOf, current):
                if isinstance(s, URIRef) and s != current and s not in all_subs and s != iri:
                    all_subs.add(s)
                    frontier.append(s)
        return all_subs

    def get_superproperties(self, prop_iri: Union[str, URIRef], direct: bool = False) -> Set[URIRef]:
        """Returns superproperties of a property."""
        iri = self.resolve_iri(prop_iri)
        if not isinstance(iri, URIRef):
            return set()

        direct_supers: Set[URIRef] = {
            o for o in self._graph.objects(iri, RDFS.subPropertyOf)
            if isinstance(o, URIRef) and o != iri
        }
        if direct:
            return direct_supers

        all_supers: Set[URIRef] = set(direct_supers)
        frontier = list(direct_supers)
        while frontier:
            current = frontier.pop()
            for o in self._graph.objects(current, RDFS.subPropertyOf):
                if isinstance(o, URIRef) and o != current and o not in all_supers and o != iri:
                    all_supers.add(o)
                    frontier.append(o)
        return all_supers

    def get_domain_and_range(self, property_iri: Union[str, URIRef]) -> Tuple[List[URIRef], List[URIRef]]:
        """Returns the domain and range URIRef lists for an Object or Datatype property."""
        iri = self.resolve_iri(property_iri)
        domains = [o for o in self._graph.objects(iri, RDFS.domain) if isinstance(o, URIRef)]
        ranges = [o for o in self._graph.objects(iri, RDFS.range) if isinstance(o, URIRef)]
        return domains, ranges

    # -------------------------------------------------------------------------
    # Individual Introspection & Querying
    # -------------------------------------------------------------------------

    def list_individuals(self, type_iri: Optional[Union[str, URIRef]] = None) -> List[Individual]:
        """Lists individuals in the ontology, optionally filtered by type."""
        ind_iris: Set[URIRef] = set()

        if type_iri is not None:
            resolved_type = self.resolve_iri(type_iri)
            matching_types = {resolved_type} | self.get_subclasses(resolved_type, direct=False)
            for t in matching_types:
                for s in self._graph.subjects(RDF.type, t):
                    if isinstance(s, URIRef):
                        ind_iris.add(s)
        else:
            for s in self._graph.subjects(RDF.type, OWL.NamedIndividual):
                if isinstance(s, URIRef):
                    ind_iris.add(s)
            for s, _, o in self._graph.triples((None, RDF.type, None)):
                if isinstance(s, URIRef) and isinstance(o, URIRef) and o not in [OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Ontology]:
                    ind_iris.add(s)

        results: List[Individual] = []
        for iri in sorted(ind_iris, key=str):
            ind = self.get_individual(iri)
            if ind:
                results.append(ind)
        return results

    def get_individual(self, ind_iri: Union[str, URIRef]) -> Optional[Individual]:
        """Retrieves details of an individual instance."""
        iri = self.resolve_iri(ind_iri)
        if not isinstance(iri, URIRef):
            return None

        types = [
            str(o) for o in self._graph.objects(iri, RDF.type)
            if isinstance(o, URIRef) and o != OWL.NamedIndividual
        ]
        if not types and (iri, RDF.type, OWL.NamedIndividual) not in self._graph:
            if not any(self._graph.predicate_objects(iri)) and not any(self._graph.subject_predicates(iri)):
                return None

        labels_dict = self.get_labels(iri)
        label = labels_dict["label"][0] if labels_dict["label"] else None
        pref_label = labels_dict["prefLabel"][0] if labels_dict["prefLabel"] else None
        alt_labels = labels_dict["altLabel"]
        comment = self.get_comment(iri)

        properties: Dict[str, List[str]] = {}
        data_properties: Dict[str, List[Any]] = {}

        ignored_preds = {RDF.type, RDFS.label, SKOS.prefLabel, SKOS.altLabel, RDFS.comment}

        for pred, obj in self._graph.predicate_objects(iri):
            if pred in ignored_preds or not isinstance(pred, URIRef):
                continue
            pred_str = str(pred)
            if isinstance(obj, URIRef):
                properties.setdefault(pred_str, []).append(str(obj))
            elif isinstance(obj, Literal):
                data_properties.setdefault(pred_str, []).append(obj.toPython())

        return Individual(
            iri=str(iri),
            label=label,
            pref_label=pref_label,
            alt_labels=alt_labels,
            types=types,
            properties=properties,
            data_properties=data_properties,
            comment=comment,
        )

    def find_individuals_by_label(
        self,
        label_query: str,
        exact: bool = False,
        case_sensitive: bool = False,
    ) -> List[Individual]:
        """Searches individuals by matching their rdfs:label, skos:prefLabel, or skos:altLabel."""
        q = label_query if case_sensitive else label_query.lower()
        matched_iris: Set[URIRef] = set()

        label_preds = [RDFS.label, SKOS.prefLabel, SKOS.altLabel]

        for pred in label_preds:
            for s, _, o in self._graph.triples((None, pred, None)):
                if not isinstance(s, URIRef) or not isinstance(o, Literal):
                    continue
                val = str(o) if case_sensitive else str(o).lower()
                if exact:
                    if val == q:
                        matched_iris.add(s)
                else:
                    if q in val:
                        matched_iris.add(s)

        results: List[Individual] = []
        for iri in sorted(matched_iris, key=str):
            ind = self.get_individual(iri)
            if ind:
                results.append(ind)
        return results

    # -------------------------------------------------------------------------
    # Graph & SPARQL Helpers
    # -------------------------------------------------------------------------

    def query_triples(
        self,
        subject: Optional[Union[str, URIRef]] = None,
        predicate: Optional[Union[str, URIRef]] = None,
        object: Optional[Union[str, URIRef, Literal, Any]] = None,
    ) -> List[Tuple[Any, Any, Any]]:
        """Queries matching triples from the RDF graph."""
        s = self.resolve_iri(subject) if subject is not None else None
        p = self.resolve_iri(predicate) if predicate is not None else None
        o = object
        if o is not None and isinstance(o, str) and (o.startswith("http://") or o.startswith("https://") or ":" in o):
            try:
                o = self.resolve_iri(o)
            except Exception:
                pass

        results: List[Tuple[Any, Any, Any]] = []
        for sub, pred, obj in self._graph.triples((s, p, o)):
            results.append((sub, pred, obj))
        return results

    def sparql_query(self, query_str: str) -> Any:
        """Executes a SPARQL query against the loaded graph."""
        return self._graph.query(query_str)


__all__ = [
    "GW2",
    "GW2LEG",
    "SCHEMA",
    "DEFAULT_PREFIXES",
    "OntologyLoader",
]
