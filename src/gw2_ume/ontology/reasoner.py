"""Symbolic axiom reasoner and constraint validator for GW2 OWL 2 ontologies."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import rdflib
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from gw2_ume.ontology.loader import OntologyLoader
from gw2_ume.ontology.schema import (
    AxiomVerificationResult,
    DatatypeProperty,
    Individual,
    ObjectProperty,
    OntologyClass,
)


class SymbolicAxiomReasoner:
    """Performs symbolic reasoning, constraint validation, path finding, and hierarchy analysis."""

    def __init__(self, loader: Optional[OntologyLoader] = None, auto_load_defaults: bool = False) -> None:
        self.loader: OntologyLoader = loader if loader is not None else OntologyLoader(auto_load_defaults=auto_load_defaults)
        self.graph: Graph = self.loader.graph
        self._depth_cache: Dict[str, int] = {}

    # -------------------------------------------------------------------------
    # Programmatic Taxonomy Registration Helpers
    # -------------------------------------------------------------------------

    def register_class(
        self,
        class_iri: Union[str, URIRef],
        super_class_iri: Optional[Union[str, URIRef]] = None,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Register a class and optional subclass relation into the ontology."""
        self._depth_cache.clear()
        c_uri = self.loader.resolve_iri(class_iri)
        self.graph.add((c_uri, RDF.type, OWL.Class))
        if super_class_iri is not None:
            s_uri = self.loader.resolve_iri(super_class_iri)
            if s_uri != OWL.Thing and str(s_uri) != str(OWL.Thing):
                self.graph.add((c_uri, RDFS.subClassOf, s_uri))
        if label:
            self.graph.add((c_uri, RDFS.label, Literal(label, datatype=XSD.string)))
        if description:
            self.graph.add((c_uri, RDFS.comment, Literal(description, datatype=XSD.string)))

    def register_disjoint_classes(
        self,
        class_a: Union[str, URIRef],
        class_b: Union[str, URIRef],
    ) -> None:
        """Register an owl:disjointWith axiom between two classes."""
        ca = self.loader.resolve_iri(class_a)
        cb = self.loader.resolve_iri(class_b)
        self.graph.add((ca, OWL.disjointWith, cb))

    def register_property(
        self,
        property_iri: Union[str, URIRef],
        domain_iri: Optional[Union[str, URIRef]] = None,
        range_iri: Optional[Union[str, URIRef]] = None,
        label: Optional[str] = None,
        description: Optional[str] = None,
        is_datatype: bool = False,
    ) -> None:
        """Register an object or datatype property with domain and range."""
        p_uri = self.loader.resolve_iri(property_iri)
        prop_type = OWL.DatatypeProperty if is_datatype else OWL.ObjectProperty
        self.graph.add((p_uri, RDF.type, prop_type))
        if domain_iri:
            d_uri = self.loader.resolve_iri(domain_iri)
            self.graph.add((p_uri, RDFS.domain, d_uri))
        if range_iri:
            r_uri = self.loader.resolve_iri(range_iri)
            self.graph.add((p_uri, RDFS.range, r_uri))
        if label:
            self.graph.add((p_uri, RDFS.label, Literal(label, datatype=XSD.string)))
        if description:
            self.graph.add((p_uri, RDFS.comment, Literal(description, datatype=XSD.string)))

    def register_entity(
        self,
        entity_iri: Union[str, URIRef],
        types: List[Union[str, URIRef]],
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Register a named individual entity with types and label."""
        e_uri = self.loader.resolve_iri(entity_iri)
        self.graph.add((e_uri, RDF.type, OWL.NamedIndividual))
        for t in types:
            t_uri = self.loader.resolve_iri(t)
            self.graph.add((e_uri, RDF.type, t_uri))
        if label:
            self.graph.add((e_uri, RDFS.label, Literal(label, datatype=XSD.string)))
        if description:
            self.graph.add((e_uri, RDFS.comment, Literal(description, datatype=XSD.string)))

    def register_triple(
        self,
        subject: Union[str, URIRef],
        predicate: Union[str, URIRef],
        object_val: Union[str, URIRef, Literal, Any],
    ) -> None:
        """Register a triple in the knowledge graph."""
        s = self.loader.resolve_iri(subject)
        p = self.loader.resolve_iri(predicate)
        if isinstance(object_val, Literal):
            o = object_val
        elif isinstance(object_val, str) and (object_val.startswith("http://") or object_val.startswith("https://") or ":" in object_val):
            o = self.loader.resolve_iri(object_val)
        else:
            o = Literal(object_val)
        self.graph.add((s, p, o))

    def has_triple(
        self,
        subject: Union[str, URIRef],
        predicate: Union[str, URIRef],
        object_val: Union[str, URIRef, Literal, Any],
    ) -> bool:
        """Checks if a triple exists in the graph."""
        s = self.loader.resolve_iri(subject)
        p = self.loader.resolve_iri(predicate)
        if isinstance(object_val, Literal):
            o = object_val
        elif isinstance(object_val, str) and (object_val.startswith("http://") or object_val.startswith("https://") or ":" in object_val):
            o = self.loader.resolve_iri(object_val)
        else:
            o = Literal(object_val)
        return (s, p, o) in self.graph

    def get_all_classes(self) -> List[str]:
        """Returns a list of all class IRIs registered in the ontology."""
        return [c.iri for c in self.loader.list_classes()]

    def get_class_labels(self, class_iri: Union[str, URIRef]) -> List[str]:
        """Returns all labels for a class."""
        labels_dict = self.loader.get_labels(class_iri)
        res = labels_dict["prefLabel"] + labels_dict["label"]
        if not res:
            name = self.loader.to_prefixed_name(class_iri)
            return [name.split(":")[-1]]
        return res

    def get_all_properties(self) -> List[str]:
        """Returns a list of all property IRIs registered in the ontology."""
        props = [p.iri for p in self.loader.list_object_properties()]
        props.extend([p.iri for p in self.loader.list_datatype_properties()])
        return sorted(list(set(props)))

    def get_property_labels(self, property_iri: Union[str, URIRef]) -> List[str]:
        """Returns all labels for a property."""
        labels_dict = self.loader.get_labels(property_iri)
        res = labels_dict["prefLabel"] + labels_dict["label"]
        if not res:
            name = self.loader.to_prefixed_name(property_iri)
            return [name.split(":")[-1]]
        return res

    @property
    def property_domains(self) -> Dict[str, Set[str]]:
        """Dictionary mapping property IRIs to their set of domain class IRIs."""
        result: Dict[str, Set[str]] = {}
        for p in self.loader.list_object_properties():
            result[p.iri] = set(p.domains)
        for dp in self.loader.list_datatype_properties():
            result[dp.iri] = set(dp.domains)
        return result

    @property
    def property_ranges(self) -> Dict[str, Set[str]]:
        """Dictionary mapping property IRIs to their set of range class IRIs."""
        result: Dict[str, Set[str]] = {}
        for p in self.loader.list_object_properties():
            result[p.iri] = set(p.ranges)
        for dp in self.loader.list_datatype_properties():
            result[dp.iri] = set(dp.ranges)
        return result

    def get_superclasses(
        self,
        class_iri: Union[str, URIRef],
        direct: bool = False,
        include_self: bool = False,
    ) -> Set[str]:
        """Returns superclasses of the given class as strings."""
        iri = self.loader.resolve_iri(class_iri)
        supers = {str(s) for s in self.loader.get_superclasses(iri, direct=direct)}
        if include_self:
            supers.add(str(iri))
        return supers

    def get_subclasses(
        self,
        class_iri: Union[str, URIRef],
        direct: bool = False,
        include_self: bool = False,
    ) -> Set[str]:
        """Returns subclasses of the given class as strings."""
        iri = self.loader.resolve_iri(class_iri)
        subs = {str(s) for s in self.loader.get_subclasses(iri, direct=direct)}
        if include_self:
            subs.add(str(iri))
        return subs

    def get_class_depth(self, class_iri: Union[str, URIRef]) -> int:
        """Calculate depth of a class in the ontology hierarchy (Thing=0, direct children=1, etc.)."""
        iri_str = str(class_iri)
        if iri_str in self._depth_cache:
            return self._depth_cache[iri_str]

        uri = self.loader.resolve_iri(class_iri)
        if uri in (OWL.Thing, URIRef("http://www.w3.org/2002/07/owl#Thing")):
            self._depth_cache[iri_str] = 0
            return 0

        parents = list(self.loader.get_superclasses(uri, direct=True))
        if not parents:
            self._depth_cache[iri_str] = 1
            return 1

        max_parent_depth = max((self.get_class_depth(p) for p in parents if p != uri), default=0)
        depth = max_parent_depth + 1
        self._depth_cache[iri_str] = depth
        return depth

    def find_lcs(self, class_iris: List[Union[str, URIRef]]) -> Optional[str]:
        """Finds the Least Common Subsumer (LCS) for a list of classes."""
        if not class_iris:
            return None
        resolved = [self.loader.resolve_iri(c) for c in class_iris if c]
        if not resolved:
            return None
        if len(set(resolved)) == 1:
            return str(resolved[0])

        ancestor_sets: List[Set[URIRef]] = []
        for c in resolved:
            supers = self.loader.get_superclasses(c, direct=False)
            ancestor_sets.append({c} | supers)

        common_ancestors = set.intersection(*ancestor_sets)
        if not common_ancestors:
            return str(OWL.Thing)

        candidates = list(common_ancestors)
        def depth(cls: URIRef) -> int:
            return len(self.loader.get_superclasses(cls, direct=False))

        candidates.sort(key=depth, reverse=True)
        return str(candidates[0])

    def find_least_common_subsumer(self, class_iris: List[Union[str, URIRef]]) -> Optional[str]:
        """Alias for find_lcs."""
        return self.find_lcs(class_iris)

    def evaluate_axiom_bonus(
        self,
        cand_i: Any = None,
        prop: Any = None,
        cand_j: Any = None,
        subject_iri: Optional[str] = None,
        predicate_iri: Optional[str] = None,
        object_iri: Optional[str] = None,
        subject_types: Optional[List[str]] = None,
        object_types: Optional[List[str]] = None,
    ) -> float:
        """Evaluates ontology axiom bonus for a candidate relation between cell entities."""
        prop_iri = predicate_iri or getattr(prop, "property_iri", str(prop) if prop is not None else None)
        if not prop_iri:
            return 0.0

        domains = self.get_expected_domains(prop_iri)
        ranges = self.get_expected_ranges(prop_iri)

        types_i = subject_types if subject_types is not None else getattr(cand_i, "types", [])
        types_j = object_types if object_types is not None else getattr(cand_j, "types", [])

        score = 0.0
        if domains and types_i:
            if any(self.is_subclass_of(ti, d) for ti in types_i for d in domains):
                score += 0.2
            elif any(self.are_disjoint(ti, d) for ti in types_i for d in domains):
                score -= 0.5

        if ranges and types_j:
            if any(self.is_subclass_of(tj, r) for tj in types_j for r in ranges):
                score += 0.2
            elif any(self.are_disjoint(tj, r) for tj in types_j for r in ranges):
                score -= 0.5

        return score

    # -------------------------------------------------------------------------
    # Subclass and Hierarchy Reasoning
    # -------------------------------------------------------------------------

    def is_subclass_of(
        self,
        child_iri: Union[str, URIRef],
        parent_iri: Union[str, URIRef],
    ) -> bool:
        """Determines if child_iri is a subclass of (or equivalent to, or identical to) parent_iri."""
        child = self.loader.resolve_iri(child_iri)
        parent = self.loader.resolve_iri(parent_iri)

        if not isinstance(child, URIRef) or not isinstance(parent, URIRef):
            return False

        if child == parent:
            return True

        if parent == OWL.Thing or str(parent) == str(OWL.Thing):
            return True

        if (child, OWL.equivalentClass, parent) in self.graph or (parent, OWL.equivalentClass, child) in self.graph:
            return True

        supers = self.loader.get_superclasses(child, direct=False)
        return parent in supers

    def is_instance_of(
        self,
        individual_iri: Union[str, URIRef],
        class_iri: Union[str, URIRef],
    ) -> bool:
        """Determines if an individual is an instance of class_iri (directly or via subclass inheritance)."""
        ind = self.loader.resolve_iri(individual_iri)
        cls = self.loader.resolve_iri(class_iri)

        if not isinstance(ind, URIRef) or not isinstance(cls, URIRef):
            return False

        if cls == OWL.Thing or str(cls) == str(OWL.Thing):
            return True

        direct_types: Set[URIRef] = {
            o for o in self.graph.objects(ind, RDF.type)
            if isinstance(o, URIRef) and o != OWL.NamedIndividual
        }

        for dt in direct_types:
            if self.is_subclass_of(dt, cls):
                return True
        return False

    def are_disjoint(
        self,
        class_a_iri: Union[str, URIRef],
        class_b_iri: Union[str, URIRef],
    ) -> bool:
        """Determines if class_a and class_b are disjoint directly or via ancestor disjointness."""
        ca = self.loader.resolve_iri(class_a_iri)
        cb = self.loader.resolve_iri(class_b_iri)

        if not isinstance(ca, URIRef) or not isinstance(cb, URIRef):
            return False

        if ca == cb:
            return False

        ancestors_a = {ca} | self.loader.get_superclasses(ca, direct=False)
        ancestors_b = {cb} | self.loader.get_superclasses(cb, direct=False)

        for a in ancestors_a:
            disjoints_a = self.loader.get_disjoint_classes(a)
            for b in ancestors_b:
                if b in disjoints_a:
                    return True

        return False

    def are_classes_disjoint(
        self,
        class_a_iri: Union[str, URIRef],
        class_b_iri: Union[str, URIRef],
    ) -> bool:
        """Alias for are_disjoint."""
        return self.are_disjoint(class_a_iri, class_b_iri)

    def get_disjoint_classes(
        self,
        class_iri: Union[str, URIRef],
        include_inherited: bool = True,
    ) -> Set[URIRef]:
        """Retrieves all classes declared or inherited as disjoint with class_iri."""
        iri = self.loader.resolve_iri(class_iri)
        if not isinstance(iri, URIRef):
            return set()

        if not include_inherited:
            return self.loader.get_disjoint_classes(iri)

        ancestors = {iri} | self.loader.get_superclasses(iri, direct=False)
        disjoint_ancestors: Set[URIRef] = set()
        for a in ancestors:
            disjoint_ancestors.update(self.loader.get_disjoint_classes(a))

        all_disjoints: Set[URIRef] = set(disjoint_ancestors)
        for d in disjoint_ancestors:
            all_disjoints.update(self.loader.get_subclasses(d, direct=False))
        return all_disjoints

    def get_disjoint_types_map(self) -> Dict[str, Set[str]]:
        """Dynamically extracts a mapping of class names/IRIs to disjoint class names/IRIs from loaded ontology."""
        disjoint_map: Dict[str, Set[str]] = {}
        all_classes = self.get_all_classes()

        for c_iri in all_classes:
            c_uri = self.loader.resolve_iri(c_iri)
            disjoints = self.get_disjoint_classes(c_uri, include_inherited=True)
            if not disjoints:
                continue

            disjoint_names: Set[str] = set()
            for d in disjoints:
                disjoint_names.add(str(d))
                d_pref = self.loader.to_prefixed_name(d)
                disjoint_names.add(d_pref)
                d_local = d_pref.split(":")[-1]
                disjoint_names.add(d_local)

            c_pref = self.loader.to_prefixed_name(c_uri)
            c_local = c_pref.split(":")[-1]

            for key in (str(c_uri), c_pref, c_local):
                disjoint_map.setdefault(key, set()).update(disjoint_names)

        return disjoint_map

    def get_predicate_signatures(self) -> Dict[str, Tuple[Set[str], Set[str]]]:
        """Dynamically extracts predicate domain/range signatures (valid_domains, valid_ranges) from loaded ontology."""
        signatures: Dict[str, Tuple[Set[str], Set[str]]] = {}
        props = self.get_all_properties()

        for p_iri in props:
            p_uri = self.loader.resolve_iri(p_iri)
            domains = self.get_expected_domains(p_uri)
            ranges = self.get_expected_ranges(p_uri)

            valid_domains: Set[str] = set()
            for d in domains:
                valid_domains.add(str(d))
                d_pref = self.loader.to_prefixed_name(d)
                valid_domains.add(d_pref)
                valid_domains.add(d_pref.split(":")[-1])
                for sub in self.loader.get_subclasses(d, direct=False):
                    valid_domains.add(str(sub))
                    s_pref = self.loader.to_prefixed_name(sub)
                    valid_domains.add(s_pref)
                    valid_domains.add(s_pref.split(":")[-1])

            valid_ranges: Set[str] = set()
            for r in ranges:
                valid_ranges.add(str(r))
                r_pref = self.loader.to_prefixed_name(r)
                valid_ranges.add(r_pref)
                valid_ranges.add(r_pref.split(":")[-1])
                for sub in self.loader.get_subclasses(r, direct=False):
                    valid_ranges.add(str(sub))
                    s_pref = self.loader.to_prefixed_name(sub)
                    valid_ranges.add(s_pref)
                    valid_ranges.add(s_pref.split(":")[-1])

            sig_tuple = (valid_domains, valid_ranges)
            p_pref = self.loader.to_prefixed_name(p_uri)
            p_local = p_pref.split(":")[-1]

            signatures[str(p_uri)] = sig_tuple
            signatures[p_pref] = sig_tuple
            signatures[p_local] = sig_tuple

        return signatures

    # -------------------------------------------------------------------------
    # Domain and Range Checks
    # -------------------------------------------------------------------------

    def get_expected_domains(self, property_iri: Union[str, URIRef]) -> Set[URIRef]:
        """Retrieves all declared or inherited domain classes for a property."""
        prop = self.loader.resolve_iri(property_iri)
        domains: Set[URIRef] = set()

        for o in self.graph.objects(prop, RDFS.domain):
            if isinstance(o, URIRef):
                domains.add(o)

        if not domains:
            super_props = self.loader.get_superproperties(prop, direct=False)
            for sp in super_props:
                for o in self.graph.objects(sp, RDFS.domain):
                    if isinstance(o, URIRef):
                        domains.add(o)
        return domains

    def get_expected_ranges(self, property_iri: Union[str, URIRef]) -> Set[URIRef]:
        """Retrieves all declared or inherited range classes/datatypes for a property."""
        prop = self.loader.resolve_iri(property_iri)
        ranges: Set[URIRef] = set()

        for o in self.graph.objects(prop, RDFS.range):
            if isinstance(o, URIRef):
                ranges.add(o)

        if not ranges:
            super_props = self.loader.get_superproperties(prop, direct=False)
            for sp in super_props:
                for o in self.graph.objects(sp, RDFS.range):
                    if isinstance(o, URIRef):
                        ranges.add(o)
        return ranges

    def get_compatible_properties(
        self,
        subject_type_iri: Union[str, URIRef],
        object_type_iri: Union[str, URIRef],
    ) -> List[ObjectProperty]:
        """Finds all ObjectProperties where subject_type satisfies the domain and object_type satisfies the range."""
        subj_type = self.loader.resolve_iri(subject_type_iri)
        obj_type = self.loader.resolve_iri(object_type_iri)

        compatible: List[ObjectProperty] = []
        all_props = self.loader.list_object_properties()

        for prop in all_props:
            prop_iri = self.loader.resolve_iri(prop.iri)
            domains = self.get_expected_domains(prop_iri)
            ranges = self.get_expected_ranges(prop_iri)

            domain_ok = True
            if domains:
                domain_ok = any(self.is_subclass_of(subj_type, d) for d in domains)

            range_ok = True
            if ranges:
                range_ok = any(self.is_subclass_of(obj_type, r) for r in ranges)

            if domain_ok and range_ok:
                compatible.append(prop)

        return compatible

    # -------------------------------------------------------------------------
    # Relation & Axiom Validation
    # -------------------------------------------------------------------------

    def validate_relation(
        self,
        subject_iri: Union[str, URIRef],
        property_iri: Union[str, URIRef],
        object_val: Union[str, URIRef, Literal, Any],
    ) -> AxiomVerificationResult:
        """Validates whether a proposed (subject, property, object) triple complies with all ontology axioms."""
        subj = self.loader.resolve_iri(subject_iri)
        prop = self.loader.resolve_iri(property_iri)

        prop_obj = self.loader.get_object_property(prop)
        data_prop_obj = self.loader.get_datatype_property(prop)

        if not prop_obj and not data_prop_obj:
            return AxiomVerificationResult(
                is_valid=False,
                message=f"Property '{self.loader.to_prefixed_name(prop)}' is not defined in the ontology.",
                details={"subject": str(subj), "property": str(prop), "object": str(object_val)},
                violated_axioms=["UndefinedProperty"],
            )

        subj_types: Set[URIRef] = set()
        if isinstance(subj, URIRef):
            for t in self.graph.objects(subj, RDF.type):
                if isinstance(t, URIRef) and t != OWL.NamedIndividual:
                    subj_types.add(t)
            if (subj, RDF.type, OWL.Class) in self.graph or (subj, RDF.type, RDFS.Class) in self.graph:
                subj_types.add(subj)

        # Validate ObjectProperty
        if prop_obj:
            if isinstance(object_val, Literal):
                return AxiomVerificationResult(
                    is_valid=False,
                    message=f"Object property '{prop_obj.display_name}' requires an individual/URI object, but received literal: {object_val}",
                    details={"subject": str(subj), "property": str(prop), "object": str(object_val)},
                    violated_axioms=["ObjectPropertyRequiresURI"],
                )

            obj_uri = self.loader.resolve_iri(object_val)
            obj_types: Set[URIRef] = set()
            if isinstance(obj_uri, URIRef):
                for t in self.graph.objects(obj_uri, RDF.type):
                    if isinstance(t, URIRef) and t != OWL.NamedIndividual:
                        obj_types.add(t)
                if (obj_uri, RDF.type, OWL.Class) in self.graph or (obj_uri, RDF.type, RDFS.Class) in self.graph:
                    obj_types.add(obj_uri)

            # Check domain compatibility
            domains = self.get_expected_domains(prop)
            if domains and subj_types:
                is_domain_compatible = any(
                    self.is_subclass_of(st, d)
                    for st in subj_types
                    for d in domains
                )
                if not is_domain_compatible:
                    expected_dom_names = [self.loader.to_prefixed_name(d) for d in domains]
                    actual_type_names = [self.loader.to_prefixed_name(t) for t in subj_types]
                    return AxiomVerificationResult(
                        is_valid=False,
                        message=(
                            f"Domain violation for property '{prop_obj.display_name}': Subject '{self.loader.to_prefixed_name(subj)}' "
                            f"has types {actual_type_names}, none of which satisfy domain {expected_dom_names}."
                        ),
                        details={"expected_domains": expected_dom_names, "actual_types": actual_type_names},
                        violated_axioms=["DomainConstraintViolation"],
                    )

                for st in subj_types:
                    for d in domains:
                        if self.are_disjoint(st, d):
                            return AxiomVerificationResult(
                                is_valid=False,
                                message=(
                                    f"Disjointness violation: Subject type '{self.loader.to_prefixed_name(st)}' "
                                    f"is disjoint with property domain '{self.loader.to_prefixed_name(d)}'."
                                ),
                                details={"subject_type": str(st), "domain": str(d)},
                                violated_axioms=["DisjointDomainViolation"],
                            )

            # Check range compatibility
            ranges = self.get_expected_ranges(prop)
            if ranges and obj_types:
                is_range_compatible = any(
                    self.is_subclass_of(ot, r)
                    for ot in obj_types
                    for r in ranges
                )
                if not is_range_compatible:
                    expected_rng_names = [self.loader.to_prefixed_name(r) for r in ranges]
                    actual_obj_types = [self.loader.to_prefixed_name(t) for t in obj_types]
                    return AxiomVerificationResult(
                        is_valid=False,
                        message=(
                            f"Range violation for property '{prop_obj.display_name}': Object '{self.loader.to_prefixed_name(obj_uri)}' "
                            f"has types {actual_obj_types}, none of which satisfy range {expected_rng_names}."
                        ),
                        details={"expected_ranges": expected_rng_names, "actual_types": actual_obj_types},
                        violated_axioms=["RangeConstraintViolation"],
                    )

                for ot in obj_types:
                    for r in ranges:
                        if self.are_disjoint(ot, r):
                            return AxiomVerificationResult(
                                is_valid=False,
                                message=(
                                    f"Disjointness violation: Object type '{self.loader.to_prefixed_name(ot)}' "
                                    f"is disjoint with property range '{self.loader.to_prefixed_name(r)}'."
                                ),
                                details={"object_type": str(ot), "range": str(r)},
                                violated_axioms=["DisjointRangeViolation"],
                            )

            if prop_obj.is_functional:
                existing_objects = list(self.graph.objects(subj, prop))
                if existing_objects and (len(existing_objects) > 1 or existing_objects[0] != obj_uri):
                    return AxiomVerificationResult(
                        is_valid=False,
                        message=f"Functional property '{prop_obj.display_name}' can only have one value for subject '{self.loader.to_prefixed_name(subj)}'.",
                        details={"existing_values": [str(x) for x in existing_objects]},
                        violated_axioms=["FunctionalPropertyViolation"],
                    )

            return AxiomVerificationResult(
                is_valid=True,
                message=f"Relation '{self.loader.to_prefixed_name(subj)}' --[{prop_obj.display_name}]--> '{self.loader.to_prefixed_name(obj_uri)}' is valid.",
                details={"subject": str(subj), "property": str(prop), "object": str(obj_uri)},
            )

        # Validate DatatypeProperty
        if data_prop_obj:
            domains = self.get_expected_domains(prop)
            if domains and subj_types:
                is_domain_compatible = any(
                    self.is_subclass_of(st, d)
                    for st in subj_types
                    for d in domains
                )
                if not is_domain_compatible:
                    expected_dom_names = [self.loader.to_prefixed_name(d) for d in domains]
                    actual_type_names = [self.loader.to_prefixed_name(t) for t in subj_types]
                    return AxiomVerificationResult(
                        is_valid=False,
                        message=(
                            f"Domain violation for datatype property '{data_prop_obj.display_name}': Subject '{self.loader.to_prefixed_name(subj)}' "
                            f"has types {actual_type_names}, none of which satisfy domain {expected_dom_names}."
                        ),
                        details={"expected_domains": expected_dom_names, "actual_types": actual_type_names},
                        violated_axioms=["DomainConstraintViolation"],
                    )

            ranges = self.get_expected_ranges(prop)
            if ranges:
                if XSD.integer in ranges or XSD.nonNegativeInteger in ranges or XSD.int in ranges:
                    if not isinstance(object_val, (int, Literal)) or (isinstance(object_val, Literal) and not object_val.datatype in [XSD.integer, XSD.nonNegativeInteger, XSD.int, None]):
                        try:
                            int(str(object_val))
                        except (ValueError, TypeError):
                            return AxiomVerificationResult(
                                is_valid=False,
                                message=f"Datatype mismatch for property '{data_prop_obj.display_name}': expected integer, got '{object_val}'.",
                                details={"expected_ranges": [str(r) for r in ranges], "actual_value": str(object_val)},
                                violated_axioms=["DatatypeMismatchViolation"],
                            )

            return AxiomVerificationResult(
                is_valid=True,
                message=f"Datatype property '{data_prop_obj.display_name}' assignment for '{self.loader.to_prefixed_name(subj)}' is valid.",
                details={"subject": str(subj), "property": str(prop), "object": str(object_val)},
            )

        return AxiomVerificationResult(is_valid=False, message="Unknown validation error.")

    # -------------------------------------------------------------------------
    # Cardinality Checking
    # -------------------------------------------------------------------------

    def check_cardinality(
        self,
        subject_iri: Union[str, URIRef],
        property_iri: Union[str, URIRef],
        count: Optional[int] = None,
    ) -> AxiomVerificationResult:
        """Checks whether the subject satisfies cardinality restrictions for property_iri."""
        subj = self.loader.resolve_iri(subject_iri)
        prop = self.loader.resolve_iri(property_iri)

        if count is None:
            actual_count = len(list(self.graph.objects(subj, prop)))
        else:
            actual_count = count

        is_functional = (prop, RDF.type, OWL.FunctionalProperty) in self.graph
        if is_functional and actual_count > 1:
            return AxiomVerificationResult(
                is_valid=False,
                message=f"Functional property '{self.loader.to_prefixed_name(prop)}' cannot have {actual_count} values (max 1 allowed).",
                details={"property": str(prop), "actual_count": actual_count, "max_allowed": 1},
                violated_axioms=["MaxCardinalityViolation"],
            )

        types = [o for o in self.graph.objects(subj, RDF.type) if isinstance(o, URIRef)]
        for t in types:
            cls_obj = self.loader.get_class(t)
            if cls_obj:
                for r in cls_obj.restrictions:
                    if r.property_iri == str(prop):
                        if r.exact_cardinality is not None and actual_count != r.exact_cardinality:
                            return AxiomVerificationResult(
                                is_valid=False,
                                message=f"Exact cardinality mismatch for '{self.loader.to_prefixed_name(prop)}': required {r.exact_cardinality}, got {actual_count}.",
                                details={"required": r.exact_cardinality, "actual": actual_count},
                                violated_axioms=["ExactCardinalityViolation"],
                            )
                        if r.min_cardinality is not None and actual_count < r.min_cardinality:
                            return AxiomVerificationResult(
                                is_valid=False,
                                message=f"Minimum cardinality violation for '{self.loader.to_prefixed_name(prop)}': minimum {r.min_cardinality}, got {actual_count}.",
                                details={"min_required": r.min_cardinality, "actual": actual_count},
                                violated_axioms=["MinCardinalityViolation"],
                            )
                        if r.max_cardinality is not None and actual_count > r.max_cardinality:
                            return AxiomVerificationResult(
                                is_valid=False,
                                message=f"Maximum cardinality violation for '{self.loader.to_prefixed_name(prop)}': maximum {r.max_cardinality}, got {actual_count}.",
                                details={"max_allowed": r.max_cardinality, "actual": actual_count},
                                violated_axioms=["MaxCardinalityViolation"],
                            )

        return AxiomVerificationResult(
            is_valid=True,
            message=f"Cardinality check passed: {actual_count} occurrences.",
            details={"actual_count": actual_count},
        )

    # -------------------------------------------------------------------------
    # Path Finding and Progression Analysis
    # -------------------------------------------------------------------------

    def find_connecting_paths(
        self,
        source_iri: Union[str, URIRef],
        target_iri: Union[str, URIRef],
        max_hops: int = 3,
        directed: bool = False,
    ) -> List[List[Tuple[URIRef, URIRef, URIRef, bool]]]:
        """Finds all semantic paths between source_iri and target_iri up to max_hops length.

        Returns:
            List of paths, where each path is a list of (start_node, predicate, end_node, is_forward: bool).
        """
        src = self.loader.resolve_iri(source_iri)
        tgt = self.loader.resolve_iri(target_iri)

        if not isinstance(src, URIRef) or not isinstance(tgt, URIRef):
            return []

        ignored_predicates = {RDF.type, RDFS.label, SKOS.prefLabel, SKOS.altLabel, RDFS.comment, OWL.versionInfo}

        queue: deque[Tuple[URIRef, List[Tuple[URIRef, URIRef, URIRef, bool]], Set[URIRef]]] = deque()
        queue.append((src, [], {src}))
        all_paths: List[List[Tuple[URIRef, URIRef, URIRef, bool]]] = []

        while queue:
            current, path, visited = queue.popleft()

            if current == tgt and path:
                all_paths.append(path)
                continue

            if len(path) >= max_hops:
                continue

            for pred, obj in self.graph.predicate_objects(current):
                if isinstance(obj, URIRef) and pred not in ignored_predicates:
                    if obj not in visited or obj == tgt:
                        new_visited = set(visited) | {obj}
                        new_step = (current, pred, obj, True)
                        queue.append((obj, path + [new_step], new_visited))

            if not directed:
                for sub, pred in self.graph.subject_predicates(current):
                    if isinstance(sub, URIRef) and pred not in ignored_predicates:
                        if sub not in visited or sub == tgt:
                            new_visited = set(visited) | {sub}
                            new_step = (sub, pred, current, False)
                            queue.append((sub, path + [new_step], new_visited))

        return all_paths

    def find_relation_paths(
        self,
        source_iri: Union[str, URIRef],
        target_iri: Union[str, URIRef],
        max_hops: int = 2,
    ) -> List[List[Tuple[URIRef, URIRef, URIRef, bool]]]:
        """Alias for find_connecting_paths."""
        return self.find_connecting_paths(source_iri, target_iri, max_hops=max_hops)

    def get_precursor_chain(self, legendary_iri: Union[str, URIRef]) -> List[URIRef]:
        """Traces the sequential precursor progression chain for a Legendary Weapon.

        Returns list from Tier 1 -> Tier 2 -> ... -> Final Precursor -> Legendary.
        """
        leg = self.loader.resolve_iri(legendary_iri)
        chain: List[URIRef] = [leg]

        precursor = None
        for p in self.graph.objects(leg, self.loader.resolve_iri("gw2:hasPrecursor")):
            if isinstance(p, URIRef):
                precursor = p
                break
        if not precursor:
            for p in self.graph.subjects(self.loader.resolve_iri("gw2:isPrecursorOf"), leg):
                if isinstance(p, URIRef):
                    precursor = p
                    break

        if not precursor:
            return chain

        chain.insert(0, precursor)

        current = precursor
        while True:
            prev_tier = None
            for prev in self.graph.subjects(self.loader.resolve_iri("gw2:upgradesTo"), current):
                if isinstance(prev, URIRef) and prev not in chain:
                    prev_tier = prev
                    break
            if prev_tier:
                chain.insert(0, prev_tier)
                current = prev_tier
            else:
                break

        return chain

    def get_crafting_discipline(self, item_iri: Union[str, URIRef]) -> Optional[URIRef]:
        """Returns the crafting discipline associated with an item or weapon type."""
        iri = self.loader.resolve_iri(item_iri)
        if isinstance(iri, URIRef):
            disc_props = [
                self.loader.resolve_iri("priory:craftedByDiscipline"),
                self.loader.resolve_iri("gw2:hasDiscipline"),
                self.loader.resolve_iri("gw2:craftedByDiscipline"),
            ]
            for prop in disc_props:
                for obj in self.graph.objects(iri, prop):
                    if isinstance(obj, URIRef):
                        return obj

        # Dynamic heuristic resolution based on weapon/item type keywords
        name = str(item_iri).lower()
        if any(w in name for w in ["staff", "scepter", "focus", "trident", "ravenswood", "nevermore", "bifrost", "meteorlogicus", "minstrel"]):
            return URIRef("https://priory.gw2/ref/discipline/artificer")
        elif any(w in name for w in ["sword", "axe", "mace", "hammer", "greatsword", "dagger", "shield", "spear", "rodgort", "twilight", "sunrise", "bolt", "frostfang"]):
            return URIRef("https://priory.gw2/ref/discipline/weaponsmith")
        elif any(w in name for w in ["bow", "pistol", "rifle", "torch", "warhorn", "hope", "predator", "kudzu", "chuka", "howler"]):
            return URIRef("https://priory.gw2/ref/discipline/huntsman")

        return None

    def is_discipline_compatible(self, item_iri: Union[str, URIRef], discipline_iri: Union[str, URIRef]) -> bool:
        """Checks if an item or weapon type is compatible with a proposed crafting discipline."""
        i_uri = self.loader.resolve_iri(item_iri)
        d_uri = self.loader.resolve_iri(discipline_iri)

        disc_props = [
            self.loader.resolve_iri("priory:craftedByDiscipline"),
            self.loader.resolve_iri("gw2:hasDiscipline"),
            self.loader.resolve_iri("gw2:craftedByDiscipline"),
        ]
        expected_discs: Set[str] = set()
        if isinstance(i_uri, URIRef):
            for prop in disc_props:
                for obj in self.graph.objects(i_uri, prop):
                    if isinstance(obj, URIRef):
                        expected_discs.add(str(obj).split("/")[-1].lower())

        expected_disc = self.get_crafting_discipline(item_iri)
        if expected_disc:
            expected_discs.add(str(expected_disc).split("/")[-1].lower())

        if not expected_discs:
            return True

        d_name = str(discipline_iri).split("/")[-1].lower()
        return d_name in expected_discs


__all__ = ["SymbolicAxiomReasoner"]
