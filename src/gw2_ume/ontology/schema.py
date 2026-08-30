"""Schema definitions and dataclasses for OWL 2 ontologies and symbolic reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import rdflib
from rdflib import Graph, Literal, URIRef, RDF, RDFS, OWL, XSD, SKOS, Namespace

from gw2_ume.ontology.vocab import (
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
    GW2,
    GW2RES,
    CLASS_ITEM,
    CLASS_EQUIPABLE,
    CLASS_EQUIPMENT,
    CLASS_WEAPON,
    CLASS_ARMOR,
    CLASS_TRINKET,
    CLASS_LEGENDARY_WEAPON,
    CLASS_PRECURSOR_WEAPON,
    CLASS_COMPONENT_ITEM,
    CLASS_TROPHY_ITEM,
    CLASS_CRAFTING_MATERIAL,
    CLASS_CURATED_COLLECTION,
    CLASS_COLLECTION_STEP,
    CLASS_COLLECTION_TIER,
    CLASS_MYSTIC_FORGE_RECIPE,
    CLASS_CRAFTING_RECIPE,
    CLASS_DISCIPLINE_RECIPE,
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_NPC_VENDOR,
    CLASS_ZONE,
    CLASS_DISCIPLINE_RATING,
    CLASS_INGREDIENT_QUANTITY,
    CLASS_CURRENCY,
    CLASS_DISCIPLINE,
    CLASS_RARITY,
    CLASS_COLLECTION_HUNT_PRECURSOR,
    CLASS_LEGENDARY_STEP,
    PROP_REQUIRES_INGREDIENT,
    PROP_REQUIRES_MATERIAL,
    PROP_INGREDIENT_QUANTITY,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_HAS_DISCIPLINE,
    PROP_REQUIRES_DISCIPLINE_RATING,
    PROP_REQUIRED_RATING,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_SOLD_BY,
    PROP_SOLD_BY_NPC,
    PROP_LOCATED_IN_ZONE,
    PROP_LOCATED_IN,
    PROP_HAS_PRECURSOR,
    PROP_IS_PRECURSOR_OF,
    PROP_PRECURSOR_TO,
    PROP_UPGRADES_TO,
    PROP_REWARD_FOR_STEP,
    PROP_PART_OF_COLLECTION,
    PROP_COLLECTION_TIER,
    PROP_TIER_NUMBER,
    PROP_OUTPUT_ITEM,
    PROP_PRODUCES_ITEM,
    PROP_PRODUCED_BY,
    PROP_FORGE_SLOT,
    PROP_ACQUISITION_METHOD,
    PROP_CONFIDENCE,
    PROP_CONFIDENCE_SCORE,
    PROP_COSTS_CURRENCY,
    PROP_REQUIRES_CURRENCY,
    CONTROLLED_DISCIPLINES,
    CONTROLLED_CURRENCIES,
    CONTROLLED_RARITIES,
    CONTROLLED_WEAPONS,
)


@dataclass
class Restriction:
    """Represents an OWL restriction axiom on a class or property."""
    property_iri: str
    restriction_type: str  # e.g., "someValuesFrom", "allValuesFrom", "hasValue", "cardinality", "minCardinality", "maxCardinality"
    target: Optional[str] = None
    min_cardinality: Optional[int] = None
    max_cardinality: Optional[int] = None
    exact_cardinality: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_iri": self.property_iri,
            "restriction_type": self.restriction_type,
            "target": self.target,
            "min_cardinality": self.min_cardinality,
            "max_cardinality": self.max_cardinality,
            "exact_cardinality": self.exact_cardinality,
        }


@dataclass
class OntologyClass:
    """Represents an OWL/RDFS Class with its hierarchy and constraints."""
    iri: str
    label: Optional[str] = None
    pref_label: Optional[str] = None
    alt_labels: List[str] = field(default_factory=list)
    comment: Optional[str] = None
    super_classes: List[str] = field(default_factory=list)
    sub_classes: List[str] = field(default_factory=list)
    disjoint_with: List[str] = field(default_factory=list)
    equivalent_classes: List[str] = field(default_factory=list)
    restrictions: List[Restriction] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Returns prefLabel, label, or the local fragment of IRI."""
        if self.pref_label:
            return self.pref_label
        if self.label:
            return self.label
        if "#" in self.iri:
            return self.iri.split("#")[-1]
        return self.iri.split("/")[-1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iri": self.iri,
            "label": self.label,
            "pref_label": self.pref_label,
            "alt_labels": self.alt_labels,
            "comment": self.comment,
            "super_classes": self.super_classes,
            "sub_classes": self.sub_classes,
            "disjoint_with": self.disjoint_with,
            "equivalent_classes": self.equivalent_classes,
            "restrictions": [r.to_dict() for r in self.restrictions],
        }


@dataclass
class ObjectProperty:
    """Represents an OWL Object Property relating individuals."""
    iri: str
    label: Optional[str] = None
    pref_label: Optional[str] = None
    alt_labels: List[str] = field(default_factory=list)
    comment: Optional[str] = None
    domains: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    inverse_of: Optional[str] = None
    is_functional: bool = False
    is_transitive: bool = False
    is_symmetric: bool = False
    sub_properties: List[str] = field(default_factory=list)
    super_properties: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        if self.pref_label:
            return self.pref_label
        if self.label:
            return self.label
        if "#" in self.iri:
            return self.iri.split("#")[-1]
        return self.iri.split("/")[-1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iri": self.iri,
            "label": self.label,
            "pref_label": self.pref_label,
            "alt_labels": self.alt_labels,
            "comment": self.comment,
            "domains": self.domains,
            "ranges": self.ranges,
            "inverse_of": self.inverse_of,
            "is_functional": self.is_functional,
            "is_transitive": self.is_transitive,
            "is_symmetric": self.is_symmetric,
            "sub_properties": self.sub_properties,
            "super_properties": self.super_properties,
        }


@dataclass
class DatatypeProperty:
    """Represents an OWL Datatype Property relating individuals to literal values."""
    iri: str
    label: Optional[str] = None
    pref_label: Optional[str] = None
    alt_labels: List[str] = field(default_factory=list)
    comment: Optional[str] = None
    domains: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    is_functional: bool = False
    sub_properties: List[str] = field(default_factory=list)
    super_properties: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        if self.pref_label:
            return self.pref_label
        if self.label:
            return self.label
        if "#" in self.iri:
            return self.iri.split("#")[-1]
        return self.iri.split("/")[-1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iri": self.iri,
            "label": self.label,
            "pref_label": self.pref_label,
            "alt_labels": self.alt_labels,
            "comment": self.comment,
            "domains": self.domains,
            "ranges": self.ranges,
            "is_functional": self.is_functional,
            "sub_properties": self.sub_properties,
            "super_properties": self.super_properties,
        }


@dataclass
class Individual:
    """Represents an individual instance in the ontology."""
    iri: str
    label: Optional[str] = None
    pref_label: Optional[str] = None
    alt_labels: List[str] = field(default_factory=list)
    types: List[str] = field(default_factory=list)
    properties: Dict[str, List[str]] = field(default_factory=dict)
    data_properties: Dict[str, List[Any]] = field(default_factory=dict)
    comment: Optional[str] = None

    @property
    def display_name(self) -> str:
        if self.pref_label:
            return self.pref_label
        if self.label:
            return self.label
        if "#" in self.iri:
            return self.iri.split("#")[-1]
        return self.iri.split("/")[-1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iri": self.iri,
            "label": self.label,
            "pref_label": self.pref_label,
            "alt_labels": self.alt_labels,
            "types": self.types,
            "properties": self.properties,
            "data_properties": self.data_properties,
            "comment": self.comment,
        }


@dataclass
class AxiomVerificationResult:
    """Outcome of validating a triple or relation against ontology axioms."""
    is_valid: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    violated_axioms: List[str] = field(default_factory=list)

    def __iter__(self):
        """Allows tuple unpacking: is_valid, reason = result"""
        return iter((self.is_valid, self.message))

    def __bool__(self) -> bool:
        return self.is_valid

    def __getitem__(self, item: int) -> Any:
        if item == 0:
            return self.is_valid
        elif item == 1:
            return self.message
        raise IndexError("AxiomVerificationResult index out of range")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "message": self.message,
            "details": self.details,
            "violated_axioms": self.violated_axioms,
        }


def extract_entity_catalog_from_graph(graph: Graph) -> Dict[str, Dict[str, Any]]:
    """Extracts an entity catalog dictionary from all owl:NamedIndividual instances in an RDF graph."""
    import re
    catalog: Dict[str, Dict[str, Any]] = {}

    gw2_core_ns = Namespace("https://schema.gw2ume.org/core#")
    tier_preds = [GW2.tier, PRIORY.tierNumber, PROP_TIER_NUMBER, gw2_core_ns.tier, gw2_core_ns.tierNumber, gw2_core_ns.generationNumber]
    disc_preds = [GW2.discipline, PRIORY.craftedByDiscipline, PROP_CRAFTED_BY_DISCIPLINE, gw2_core_ns.discipline, gw2_core_ns.hasDiscipline, gw2_core_ns.craftedByDiscipline]
    rating_preds = [GW2.minRating, PRIORY.requiresDisciplineRating, PROP_REQUIRES_DISCIPLINE_RATING, gw2_core_ns.minRating, gw2_core_ns.disciplineMinRating, gw2_core_ns.requiresDisciplineRating]
    zone_preds = [GW2.zone, PRIORY.locatedInZone, PROP_LOCATED_IN_ZONE, gw2_core_ns.locatedIn, gw2_core_ns.zone, gw2_core_ns.locatedInZone]

    for s in set(graph.subjects(RDF.type, OWL.NamedIndividual)):
        if not isinstance(s, URIRef):
            continue

        s_str = str(s)
        if "#" in s_str:
            frag = s_str.split("#")[-1]
        else:
            frag = s_str.rstrip("/").split("/")[-1]

        key = re.sub(r"(?<!^)(?=[A-Z])", "_", frag).lower()

        # Labels
        pref_labels = [str(o) for o in graph.objects(s, SKOS.prefLabel)]
        rdfs_labels = [str(o) for o in graph.objects(s, RDFS.label)]
        alt_labels = [str(o) for o in graph.objects(s, SKOS.altLabel)]

        if pref_labels:
            label = pref_labels[0]
        elif rdfs_labels:
            label = rdfs_labels[0]
        else:
            label = key.replace("_", " ").title()

        # Types
        types = [o for o in graph.objects(s, RDF.type) if o not in (OWL.NamedIndividual, OWL.Thing)]
        main_type = types[0] if types else CLASS_ITEM

        type_str = str(main_type)
        if "#" in type_str:
            type_label = type_str.split("#")[-1]
        else:
            type_label = type_str.rstrip("/").split("/")[-1]

        # Comments
        comments = [str(o) for o in graph.objects(s, RDFS.comment)]
        comment = comments[0] if comments else None

        # Build aliases
        aliases: List[str] = []
        for a in alt_labels:
            if a and a not in aliases:
                aliases.append(a)
        if label.lower() not in aliases:
            aliases.append(label.lower())

        entry: Dict[str, Any] = {
            "label": label,
            "type": main_type,
            "type_label": type_label,
            "uri": s,
            "aliases": aliases,
        }
        if comment:
            entry["comment"] = comment
            entry["description"] = comment

        # Custom properties
        for p in tier_preds:
            val = graph.value(s, p)
            if val is not None:
                try:
                    entry["tier"] = int(val)
                    break
                except (ValueError, TypeError):
                    pass

        for p in disc_preds:
            val = graph.value(s, p)
            if val is not None:
                val_label = graph.value(val, RDFS.label)
                if val_label:
                    entry["discipline"] = str(val_label)
                else:
                    entry["discipline"] = str(val).split("#")[-1].split("/")[-1].replace("_", " ").title()
                break

        for p in rating_preds:
            val = graph.value(s, p)
            if val is not None:
                try:
                    entry["min_rating"] = int(val)
                    break
                except (ValueError, TypeError):
                    pass

        for p in zone_preds:
            val = graph.value(s, p)
            if val is not None:
                val_label = graph.value(val, RDFS.label)
                if val_label:
                    entry["zone"] = str(val_label)
                else:
                    entry["zone"] = str(val).split("#")[-1].split("/")[-1].replace("_", " ").title()
                break

        # Attribute combination metadata
        exotic_pfx = graph.value(s, PRIORY.hasExoticPrefix)
        if exotic_pfx:
            entry["exotic_prefix"] = str(exotic_pfx)
            for pfx_val in [str(exotic_pfx), str(exotic_pfx).lower(), str(exotic_pfx).rstrip("'s"), str(exotic_pfx).rstrip("'s").lower()]:
                if pfx_val and pfx_val not in aliases:
                    aliases.append(pfx_val)

        ascended_pfx = graph.value(s, PRIORY.hasAscendedPrefix)
        if ascended_pfx:
            entry["ascended_prefix"] = str(ascended_pfx)
            for pfx_val in [str(ascended_pfx), str(ascended_pfx).lower(), str(ascended_pfx).rstrip("'s"), str(ascended_pfx).rstrip("'s").lower()]:
                if pfx_val and pfx_val not in aliases:
                    aliases.append(pfx_val)

        primary_attrs = [str(o) for o in graph.objects(s, PRIORY.hasPrimaryAttribute)]
        if primary_attrs:
            entry["primary_attributes"] = primary_attrs

        secondary_attrs = [str(o) for o in graph.objects(s, PRIORY.hasSecondaryAttribute)]
        if secondary_attrs:
            entry["secondary_attributes"] = secondary_attrs

        expansion = graph.value(s, PRIORY.releasedInExpansion)
        if expansion:
            entry["expansion"] = str(expansion)

        catalog[key] = entry

    return catalog


def build_gw2_ontology_graph() -> Graph:
    """Constructs the base RDFLib OWL Ontology Graph for GW2-UME by parsing default .ttl files."""
    from gw2_ume.ontology.loader import OntologyLoader

    loader = OntologyLoader(auto_load_defaults=True)
    return loader.graph


# Dynamically populated Entity Catalog driven from Ontology Graph ABox
ENTITY_CATALOG: Dict[str, Dict[str, Any]] = extract_entity_catalog_from_graph(build_gw2_ontology_graph())


__all__ = [
    "Restriction",
    "OntologyClass",
    "ObjectProperty",
    "DatatypeProperty",
    "Individual",
    "AxiomVerificationResult",
    "extract_entity_catalog_from_graph",
    "ENTITY_CATALOG",
    "build_gw2_ontology_graph",
]
