"""Schema definitions and dataclasses for OWL 2 ontologies and symbolic reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import rdflib
from rdflib import Graph, Literal, URIRef, RDF, RDFS, OWL, XSD, SKOS

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


# Canonical Named Individuals ABox Definition for GW2-UME
BASE_NAMED_INDIVIDUALS: List[Dict[str, Any]] = [
    # Precursors
    {
        "uri": ITEM["ravenswood_branch"],
        "type": CLASS_PRECURSOR_WEAPON,
        "label": "Ravenswood Branch",
        "aliases": ["ravenswood branch", "branch", "tier 1 precursor", "ravenswood staff 1"],
        "tier": 1,
        "discipline": "Artificer",
        "min_rating": 450,
        "requires_ingredient": [ITEM["spiritwood_plank"]],
        "comment": "Tier 1 precursor weapon for Nevermore",
    },
    {
        "uri": ITEM["ravenswood_staff"],
        "type": CLASS_PRECURSOR_WEAPON,
        "label": "Ravenswood Staff",
        "aliases": ["ravenswood staff", "staff", "tier 2 precursor", "spiritwood staff 2"],
        "tier": 2,
        "discipline": "Artificer",
        "min_rating": 450,
        "requires_ingredient": [ITEM["spiritwood_plank"]],
        "comment": "Tier 2 precursor weapon for Nevermore",
    },
    {
        "uri": ITEM["the_raven_spirit"],
        "type": CLASS_PRECURSOR_WEAPON,
        "label": "The Raven Spirit",
        "aliases": ["the raven spirit", "raven spirit", "tier 3 precursor", "raven", "spirit"],
        "tier": 3,
        "discipline": "Artificer",
        "min_rating": 450,
        "requires_ingredient": [ITEM["spiritwood_plank"]],
        "comment": "Tier 3 precursor weapon for Nevermore",
    },
    {
        "uri": ITEM["the_living_ravens"],
        "type": CLASS_PRECURSOR_WEAPON,
        "label": "The Living Ravens",
        "aliases": ["the living ravens", "living ravens", "tier 4 precursor", "the livinq ravens", "living raven"],
        "tier": 4,
        "discipline": "Artificer",
        "min_rating": 450,
        "requires_ingredient": [ITEM["spiritwood_plank"]],
        "comment": "Tier 4 precursor weapon for Nevermore",
    },
    # Legendary Weapon
    {
        "uri": ITEM["nevermore"],
        "type": CLASS_LEGENDARY_WEAPON,
        "label": "Nevermore",
        "aliases": ["nevermore", "n3vermore", "legendary staff", "raven staff"],
        "comment": "Generation 2 Legendary Staff",
    },
    # Mystic Forge Components
    {
        "uri": ITEM["gift_of_nevermore"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Gift of Nevermore",
        "aliases": ["gift of nevermore", "gift of n3vermore", "nevermore gift", "gift"],
        "comment": "Weapon-specific gift for Nevermore",
    },
    {
        "uri": ITEM["mystic_tribute"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Mystic Tribute",
        "aliases": ["mystic tribute", "mystic tribut", "tribute", "mystick tribute"],
        "comment": "Universal Gen 2 tribute component",
    },
    {
        "uri": ITEM["gift_of_mastery"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Gift of Mastery",
        "aliases": ["gift of mastery", "mastery gift", "gift mastery"],
        "comment": "Core legendary gift component",
    },
    {
        "uri": ITEM["gift_of_wood"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Gift of Wood",
        "aliases": ["gift of wood", "wood gift"],
        "comment": "Component gift made of refined woods",
    },
    {
        "uri": ITEM["gift_of_energy"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Gift of Energy",
        "aliases": ["gift of energy", "energy gift"],
        "comment": "Component gift crafted by Artificer",
    },
    # Materials
    {
        "uri": ITEM["spiritwood_plank"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Spiritwood Plank",
        "aliases": ["spiritwood plank", "spiritwood", "spiritwood planks", "spirit plank"],
        "comment": "Ascended wood crafting material",
    },
    {
        "uri": ITEM["elder_wood_plank"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Elder Wood Plank",
        "aliases": ["elder wood plank", "elder wood", "elder plank", "elder planks"],
        "comment": "Refined tier 5 wood material",
    },
    {
        "uri": ITEM["ancient_wood_plank"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Ancient Wood Plank",
        "aliases": ["ancient wood plank", "ancient wood", "ancient plank", "ancient planks"],
        "comment": "Refined tier 6 wood material",
    },
    {
        "uri": ITEM["deldrimor_steel_ingot"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Deldrimor Steel Ingot",
        "aliases": ["deldrimor steel ingot", "deldrimor steel", "deldrimor ingot", "deldrimor"],
        "comment": "Ascended metal crafting material",
    },
    {
        "uri": ITEM["elonian_leather_square"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Elonian Leather Square",
        "aliases": ["elonian leather square", "elonian leather", "elonian square"],
        "comment": "Ascended leather crafting material",
    },
    {
        "uri": ITEM["bolt_of_damask"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Bolt of Damask",
        "aliases": ["bolt of damask", "damask bolt", "damask"],
        "comment": "Ascended cloth crafting material",
    },
    {
        "uri": ITEM["mystic_clover"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Mystic Clover",
        "aliases": ["mystic clover", "mystic clovers", "clover", "clovers"],
        "comment": "Mystic component for legendary tributes",
    },
    {
        "uri": ITEM["mystic_coin"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Mystic Coin",
        "aliases": ["mystic coin", "mystic coins", "coin", "coins"],
        "comment": "Valuable token for Mystic Forge recipes",
    },
    {
        "uri": ITEM["amalgamated_gemstone"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Amalgamated Gemstone",
        "aliases": ["amalgamated gemstone", "amalgamated gemstones", "amalgamated gem", "amalgams"],
        "comment": "Composite gemstone for Mystic Tribute",
    },
    {
        "uri": ITEM["bloodstone_shard"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Bloodstone Shard",
        "aliases": ["bloodstone shard", "bloodstone shards", "bloodstone"],
        "comment": "Mystic component purchased from Miyani",
    },
    {
        "uri": ITEM["icy_runestone"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Icy Runestone",
        "aliases": ["icy runestone", "icy runestones", "runestone", "runestones"],
        "comment": "Vendor component sold by Riel Runecrafter",
    },
    {
        "uri": ITEM["crystalline_ore"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Crystalline Ore",
        "aliases": ["crystalline ore", "cryst ore"],
        "comment": "Ore from Dragon's Stand pods",
    },
    # Additional Journey / Collection Items
    {
        "uri": ITEM["essence_of_the_raven"],
        "type": CLASS_TROPHY_ITEM,
        "label": "Essence of the Raven",
        "aliases": ["essence of the raven", "raven essence"],
        "comment": "Trophy item for Nevermore journey",
    },
    {
        "uri": ITEM["jar_of_luminescence"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Jar of Luminescence",
        "aliases": ["jar of luminescence", "luminescence jar", "jar of luminesce"],
        "comment": "Component item for precursor collections",
    },
    {
        "uri": ITEM["spiritwood_staff_shaft"],
        "type": CLASS_COMPONENT_ITEM,
        "label": "Spiritwood Staff Shaft",
        "aliases": ["spiritwood staff shaft", "staff shaft"],
        "comment": "Staff shaft component",
    },
    {
        "uri": ITEM["raven_egg"],
        "type": CLASS_TROPHY_ITEM,
        "label": "Raven Egg",
        "aliases": ["raven egg", "egg"],
        "comment": "Quest trophy item for Nevermore IV",
    },
    {
        "uri": ITEM["heart_of_the_mists_essence"],
        "type": CLASS_TROPHY_ITEM,
        "label": "Heart of the Mists Essence",
        "aliases": ["heart of the mists essence", "heart of mists essence", "mist essence"],
        "comment": "Trophy from Heart of the Mists",
    },
    {
        "uri": ITEM["spiritwood_dowel"],
        "type": CLASS_CRAFTING_MATERIAL,
        "label": "Spiritwood Dowel",
        "aliases": ["spiritwood dowel", "spiritwood dowels"],
        "comment": "Ascended crafting dowel",
    },
    {
        "uri": ITEM["friends_of_the_owl"],
        "type": CLASS_TROPHY_ITEM,
        "label": "Friends of the Owl",
        "aliases": ["friends of the owl", "friend of the owl", "friend owl"],
        "comment": "Collection trophy",
    },
    {
        "uri": ITEM["friends_of_the_raven"],
        "type": CLASS_TROPHY_ITEM,
        "label": "Friends of the Raven",
        "aliases": ["friends of the raven", "friend of the raven", "friend raven"],
        "comment": "Collection trophy",
    },
    {
        "uri": ITEM["wood_for_the_roost"],
        "type": CLASS_TROPHY_ITEM,
        "label": "Wood for the Roost",
        "aliases": ["wood for the roost", "wood for roost", "roost wood"],
        "comment": "Collection trophy",
    },
    # Vendors (priory-ref:vendor/)
    {
        "uri": PRIORY_REF["vendor/miyani"],
        "type": CLASS_NPC_VENDOR,
        "label": "Miyani",
        "zone": "Lion's Arch",
        "located_in": PRIORY_REF["zone/lions_arch"],
        "aliases": ["miyani", "mystic forge vendor"],
        "comment": "Mystic Forge attendant in Lion's Arch",
    },
    {
        "uri": PRIORY_REF["vendor/grandmaster_craftsman_hobbs"],
        "type": CLASS_NPC_VENDOR,
        "label": "Grandmaster Craftsman Hobbs",
        "zone": "Lion's Arch",
        "located_in": PRIORY_REF["zone/lions_arch"],
        "aliases": ["grandmaster craftsman hobbs", "hobbs", "legendary vendor"],
        "comment": "Legendary crafting merchant in Lion's Arch",
    },
    {
        "uri": PRIORY_REF["vendor/riel_runecrafter"],
        "type": CLASS_NPC_VENDOR,
        "label": "Riel Runecrafter",
        "zone": "Lion's Arch",
        "located_in": PRIORY_REF["zone/frostgorge_sound"],
        "aliases": ["riel runecrafter", "riel", "runecrafter vendor"],
        "comment": "Merchant selling Icy Runestones",
    },
    {
        "uri": PRIORY_REF["vendor/shaman_sigurlina"],
        "type": CLASS_NPC_VENDOR,
        "label": "Shaman Sigurlina",
        "zone": "Wayfarer Foothills",
        "located_in": PRIORY_REF["zone/wayfarer_foothills"],
        "aliases": ["shaman sigurlina", "sigurlina"],
        "comment": "Vendor in Wayfarer Foothills",
    },
    {
        "uri": PRIORY_REF["vendor/hylek_alchemist"],
        "type": CLASS_NPC_VENDOR,
        "label": "Hylek Alchemist",
        "zone": "Sparkfly Fen",
        "located_in": PRIORY_REF["zone/sparkfly_fen"],
        "aliases": ["hylek alchemist", "hylek alchemists", "alchemists", "alchemist"],
        "comment": "Vendor in Sparkfly Fen",
    },
    {
        "uri": PRIORY_REF["vendor/great_raven_spirit"],
        "type": CLASS_NPC_VENDOR,
        "label": "Great Raven Spirit",
        "zone": "Lornar's Pass",
        "located_in": PRIORY_REF["zone/lornars_pass"],
        "aliases": ["great raven spirit", "great raven spirit roost", "raven spirit npc"],
        "comment": "Spirit NPC in Lornar's Pass",
    },
    {
        "uri": PRIORY_REF["vendor/mist_warrior"],
        "type": CLASS_NPC_VENDOR,
        "label": "Mist Warrior",
        "zone": "Heart of the Mists",
        "located_in": PRIORY_REF["zone/heart_of_the_mists"],
        "aliases": ["mist warrior", "mist warriors"],
        "comment": "NPC in Heart of the Mists",
    },
    {
        "uri": PRIORY_REF["vendor/owl_shaman"],
        "type": CLASS_NPC_VENDOR,
        "label": "Owl Shaman",
        "zone": "Dredgehaunt Cliffs",
        "located_in": PRIORY_REF["zone/dredgehaunt_cliffs"],
        "aliases": ["owl shaman"],
        "comment": "Shaman in Dredgehaunt Cliffs",
    },
    # Zones (priory-ref:zone/)
    {
        "uri": PRIORY_REF["zone/lions_arch"],
        "type": CLASS_ZONE,
        "label": "Lion's Arch",
        "aliases": ["lion's arch", "lions arch", "la"],
        "comment": "Major trading port city",
    },
    {
        "uri": PRIORY_REF["zone/frostgorge_sound"],
        "type": CLASS_ZONE,
        "label": "Frostgorge Sound",
        "aliases": ["frostgorge sound", "frostgorge", "fgs"],
        "comment": "Shiverpeaks high level zone",
    },
    {
        "uri": PRIORY_REF["zone/verdant_brink"],
        "type": CLASS_ZONE,
        "label": "Verdant Brink",
        "aliases": ["verdant brink", "vb"],
        "comment": "Heart of Maguuma canopy zone",
    },
    {
        "uri": PRIORY_REF["zone/auric_basin"],
        "type": CLASS_ZONE,
        "label": "Auric Basin",
        "aliases": ["auric basin", "ab"],
        "comment": "Heart of Maguuma zone with Tarir",
    },
    {
        "uri": PRIORY_REF["zone/tangled_depths"],
        "type": CLASS_ZONE,
        "label": "Tangled Depths",
        "aliases": ["tangled depths", "td"],
        "comment": "Heart of Maguuma underground zone",
    },
    {
        "uri": PRIORY_REF["zone/dragons_stand"],
        "type": CLASS_ZONE,
        "label": "Dragon's Stand",
        "aliases": ["dragon's stand", "dragons stand", "ds"],
        "comment": "Heart of Maguuma jungle zone",
    },
    {
        "uri": PRIORY_REF["zone/wayfarer_foothills"],
        "type": CLASS_ZONE,
        "label": "Wayfarer Foothills",
        "aliases": ["wayfarer foothills", "wayfarer"],
        "comment": "Norn starting zone",
    },
    {
        "uri": PRIORY_REF["zone/sparkfly_fen"],
        "type": CLASS_ZONE,
        "label": "Sparkfly Fen",
        "aliases": ["sparkfly fen", "sparkfly"],
        "comment": "Tequatl swamp zone",
    },
    {
        "uri": PRIORY_REF["zone/lornars_pass"],
        "type": CLASS_ZONE,
        "label": "Lornar's Pass",
        "aliases": ["lornar's pass", "lornars pass"],
        "comment": "Shiverpeaks pass zone",
    },
    {
        "uri": PRIORY_REF["zone/heart_of_the_mists"],
        "type": CLASS_ZONE,
        "label": "Heart of the Mists",
        "aliases": ["heart of the mists", "mists", "pvp lobby"],
        "comment": "PvP lobby area",
    },
    {
        "uri": PRIORY_REF["zone/dredgehaunt_cliffs"],
        "type": CLASS_ZONE,
        "label": "Dredgehaunt Cliffs",
        "aliases": ["dredgehaunt cliffs", "dredgehaunt"],
        "comment": "Shiverpeaks dredge zone",
    },
    # Disciplines (priory-ref:discipline/)
    {
        "uri": DISCIPLINE.artificer,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Artificer",
        "aliases": ["artificer", "artifice"],
        "comment": "Crafting magical weapons and staves",
    },
    {
        "uri": DISCIPLINE.weaponsmith,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Weaponsmith",
        "aliases": ["weaponsmith", "weapon smith"],
        "comment": "Crafting melee weapons",
    },
    {
        "uri": DISCIPLINE.huntsman,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Huntsman",
        "aliases": ["huntsman", "hunt"],
        "comment": "Crafting ranged weapons",
    },
    {
        "uri": DISCIPLINE.armorsmith,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Armorsmith",
        "aliases": ["armorsmith", "armor smith"],
        "comment": "Crafting heavy armor",
    },
    {
        "uri": DISCIPLINE.tailor,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Tailor",
        "aliases": ["tailor"],
        "comment": "Crafting light armor",
    },
    {
        "uri": DISCIPLINE.leatherworker,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Leatherworker",
        "aliases": ["leatherworker", "leather worker"],
        "comment": "Crafting medium armor",
    },
    {
        "uri": DISCIPLINE.mystic_forge,
        "type": CLASS_CRAFTING_DISCIPLINE,
        "label": "Mystic Forge",
        "aliases": ["mystic forge", "mystic frge", "mystick forge", "zommoros"],
        "comment": "Mystic Forge crafting conduit",
    },
]


def extract_entity_catalog_from_graph(graph: Graph) -> Dict[str, Dict[str, Any]]:
    """Extracts an entity catalog dictionary from all owl:NamedIndividual instances in an RDF graph."""
    import re
    catalog: Dict[str, Dict[str, Any]] = {}

    tier_preds = [GW2.tier, PRIORY.tierNumber, PROP_TIER_NUMBER]
    disc_preds = [GW2.discipline, PRIORY.craftedByDiscipline, PROP_CRAFTED_BY_DISCIPLINE]
    rating_preds = [GW2.minRating, PRIORY.requiresDisciplineRating, PROP_REQUIRES_DISCIPLINE_RATING]
    zone_preds = [GW2.zone, PRIORY.locatedInZone, PROP_LOCATED_IN_ZONE]

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
                val_str = str(val).split("#")[-1].split("/")[-1].replace("_", " ").title()
                entry["discipline"] = val_str
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

        catalog[key] = entry

    return catalog


def build_gw2_ontology_graph() -> Graph:
    """Constructs the base RDFLib OWL Ontology Graph for GW2-UME using official Priory namespaces."""
    g = Graph()
    g.bind("priory", PRIORY, override=True)
    g.bind("priory-ref", PRIORY_REF, override=True)
    g.bind("gw2", GW2, override=True)
    g.bind("gw2res", GW2RES, override=True)
    g.bind("item", ITEM, override=True)
    g.bind("recipe", RECIPE, override=True)
    g.bind("rarity", RARITY, override=True)
    g.bind("weapon", WEAPON, override=True)
    g.bind("discipline", DISCIPLINE, override=True)
    g.bind("currency", CURRENCY, override=True)
    g.bind("armor", ARMOR, override=True)
    g.bind("slot", SLOT, override=True)
    g.bind("itemtype", ITEMTYPE, override=True)
    g.bind("gamemode", GAMEMODE, override=True)
    g.bind("zone", ZONE, override=True)
    g.bind("vendor", VENDOR, override=True)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    g.bind("xsd", XSD)
    g.bind("skos", SKOS)

    # Declare Ontology & Namespace Equivalence
    g.add((URIRef("https://gw2ume.org/ontology#"), RDF.type, OWL.Ontology))
    g.add((GW2.Item, OWL.equivalentClass, PRIORY.Item))

    # Declare Classes (TBox Domain Universals)
    classes = [
        (CLASS_ITEM, "Base Item in GW2", OWL.Class),
        (CLASS_EQUIPABLE, "Equipable Item", CLASS_ITEM),
        (CLASS_WEAPON, "Combat Weapon", CLASS_EQUIPABLE),
        (CLASS_ARMOR, "Defensive Armor", CLASS_EQUIPABLE),
        (CLASS_TRINKET, "Accessory or Trinket", CLASS_EQUIPABLE),
        (CLASS_LEGENDARY_WEAPON, "Gen 2 Legendary Weapon", CLASS_WEAPON),
        (CLASS_PRECURSOR_WEAPON, "Precursor Weapon Tier", CLASS_WEAPON),
        (CLASS_COMPONENT_ITEM, "Component or Sub-Ingredient Item", CLASS_ITEM),
        (CLASS_TROPHY_ITEM, "Collection Trophy or Quest Item", CLASS_ITEM),
        (CLASS_CRAFTING_MATERIAL, "Raw or Refined Crafting Material", CLASS_ITEM),
        (CLASS_CURATED_COLLECTION, "Legendary Precursor Journey Collection", OWL.Class),
        (CLASS_COLLECTION_STEP, "Individual Collection Step", OWL.Class),
        (CLASS_COLLECTION_TIER, "Precursor Collection Tier (1-4)", OWL.Class),
        (CLASS_COLLECTION_HUNT_PRECURSOR, "Precursor Journey Hunt Step", CLASS_ITEM),
        (CLASS_MYSTIC_FORGE_RECIPE, "4-Slot Mystic Forge Recipe", OWL.Class),
        (CLASS_CRAFTING_RECIPE, "Discipline Crafting Recipe", OWL.Class),
        (CLASS_DISCIPLINE_RECIPE, "Discipline Crafting Recipe", OWL.Class),
        (CLASS_CRAFTING_DISCIPLINE, "Crafting Profession Discipline", OWL.Class),
        (CLASS_NPC_VENDOR, "NPC Vendor or Quest Giver", OWL.Class),
        (CLASS_ZONE, "Tyria Geographic Zone", OWL.Class),
        (CLASS_DISCIPLINE_RATING, "Required Crafting Skill Level", OWL.Class),
        (CLASS_INGREDIENT_QUANTITY, "Quantity count for recipe ingredient", OWL.Class),
        (CLASS_CURRENCY, "In-Game Currency", OWL.Class),
        (CLASS_DISCIPLINE, "Crafting Discipline", OWL.Class),
        (CLASS_RARITY, "Item Rarity Tier", OWL.Class),
    ]

    for c_uri, label, parent in classes:
        g.add((c_uri, RDF.type, OWL.Class))
        g.add((c_uri, RDFS.label, Literal(label, datatype=XSD.string)))
        if parent != OWL.Class:
            g.add((c_uri, RDFS.subClassOf, parent))

    # Declare Formal Disjointness Axioms (John Beverley / BFO Non-Conflation Principle)
    disjoint_pairs = [
        (CLASS_ITEM, CLASS_ZONE),
        (CLASS_ITEM, CLASS_NPC_VENDOR),
        (CLASS_ITEM, CLASS_CRAFTING_DISCIPLINE),
        (CLASS_CRAFTING_MATERIAL, CLASS_EQUIPABLE),
        (CLASS_ZONE, CLASS_NPC_VENDOR),
        (CLASS_WEAPON, CLASS_ARMOR),
    ]
    for c1, c2 in disjoint_pairs:
        g.add((c1, OWL.disjointWith, c2))

    # Declare Properties with Domain and Range (TBox Property Signatures)
    properties = [
        (PROP_REQUIRES_INGREDIENT, "requiresIngredient", CLASS_ITEM, CLASS_ITEM),
        (PROP_INGREDIENT_QUANTITY, "ingredientQuantity", CLASS_ITEM, XSD.integer),
        (PROP_CRAFTED_BY_DISCIPLINE, "craftedByDiscipline", CLASS_ITEM, CLASS_CRAFTING_DISCIPLINE),
        (PROP_REQUIRES_DISCIPLINE_RATING, "requiresDisciplineRating", CLASS_ITEM, XSD.integer),
        (PROP_OBTAINED_FROM_VENDOR, "soldBy", CLASS_ITEM, CLASS_NPC_VENDOR),
        (PROP_LOCATED_IN_ZONE, "locatedInZone", CLASS_NPC_VENDOR, CLASS_ZONE),
        (PROP_HAS_PRECURSOR, "hasPrecursor", CLASS_LEGENDARY_WEAPON, CLASS_PRECURSOR_WEAPON),
        (PROP_PRECURSOR_TO, "precursorTo", CLASS_PRECURSOR_WEAPON, CLASS_PRECURSOR_WEAPON),
        (PROP_UPGRADES_TO, "upgradesTo", CLASS_ITEM, CLASS_ITEM),
        (PROP_REWARD_FOR_STEP, "rewardForStep", CLASS_ITEM, CLASS_COLLECTION_STEP),
        (PROP_PART_OF_COLLECTION, "partOfCollection", CLASS_ITEM, CLASS_CURATED_COLLECTION),
        (PROP_COLLECTION_TIER, "tierNumber", CLASS_ITEM, XSD.integer),
        (PROP_OUTPUT_ITEM, "producesItem", CLASS_DISCIPLINE_RECIPE, CLASS_ITEM),
        (PROP_FORGE_SLOT, "forgeSlot", CLASS_MYSTIC_FORGE_RECIPE, XSD.string),
        (PROP_ACQUISITION_METHOD, "acquisitionMethod", CLASS_ITEM, XSD.string),
        (PROP_CONFIDENCE, "confidenceScore", OWL.Thing, XSD.float),
        (PROP_COSTS_CURRENCY, "requiresCurrency", CLASS_ITEM, CLASS_CURRENCY),
    ]

    for p_uri, label, domain, rng in properties:
        is_obj_prop = str(rng).startswith("https://") or str(rng).startswith("http://www.w3.org/2002/07/owl")
        g.add((p_uri, RDF.type, OWL.ObjectProperty if is_obj_prop else OWL.DatatypeProperty))
        g.add((p_uri, RDFS.label, Literal(label, datatype=XSD.string)))
        g.add((p_uri, RDFS.domain, domain))
        g.add((p_uri, RDFS.range, rng))

    # Dynamically Populate Controlled Reference Dimensions (priory-ref: individuals)
    for disc_key, disc_uri in CONTROLLED_DISCIPLINES.items():
        g.add((disc_uri, RDF.type, CLASS_CRAFTING_DISCIPLINE))
        g.add((disc_uri, RDF.type, OWL.NamedIndividual))
        g.add((disc_uri, RDFS.label, Literal(disc_key.replace("_", " ").title(), datatype=XSD.string)))
        g.add((disc_uri, SKOS.prefLabel, Literal(disc_key.replace("_", " ").title(), datatype=XSD.string)))

    for curr_key, curr_uri in CONTROLLED_CURRENCIES.items():
        g.add((curr_uri, RDF.type, CLASS_CURRENCY))
        g.add((curr_uri, RDF.type, OWL.NamedIndividual))
        g.add((curr_uri, RDFS.label, Literal(curr_key.replace("_", " ").title(), datatype=XSD.string)))
        g.add((curr_uri, SKOS.prefLabel, Literal(curr_key.replace("_", " ").title(), datatype=XSD.string)))

    for rar_key, rar_uri in CONTROLLED_RARITIES.items():
        g.add((rar_uri, RDF.type, CLASS_RARITY))
        g.add((rar_uri, RDF.type, OWL.NamedIndividual))
        g.add((rar_uri, RDFS.label, Literal(rar_key.capitalize(), datatype=XSD.string)))
        g.add((rar_uri, SKOS.prefLabel, Literal(rar_key.capitalize(), datatype=XSD.string)))

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
        g.add((wpn_uri, RDF.type, CLASS_WEAPON))
        g.add((wpn_uri, RDF.type, OWL.NamedIndividual))
        g.add((wpn_uri, RDFS.label, Literal(wpn_key.replace("_", " ").title(), datatype=XSD.string)))
        g.add((wpn_uri, SKOS.prefLabel, Literal(wpn_key.replace("_", " ").title(), datatype=XSD.string)))
        disc_target = weapon_discipline_map.get(wpn_key)
        if disc_target:
            g.add((wpn_uri, PROP_CRAFTED_BY_DISCIPLINE, disc_target))

    # Populate Base Named Individuals (ABox Domain Individuals)
    for ind in BASE_NAMED_INDIVIDUALS:
        u = ind["uri"]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, ind["type"]))
        g.add((u, RDFS.label, Literal(ind["label"], datatype=XSD.string)))
        g.add((u, SKOS.prefLabel, Literal(ind["label"], datatype=XSD.string)))

        for alias in ind.get("aliases", []):
            g.add((u, SKOS.altLabel, Literal(alias, datatype=XSD.string)))

        if ind.get("tier") is not None:
            g.add((u, GW2.tier, Literal(ind["tier"], datatype=XSD.integer)))
            g.add((u, PROP_TIER_NUMBER, Literal(ind["tier"], datatype=XSD.integer)))

        if ind.get("discipline"):
            g.add((u, GW2.discipline, Literal(ind["discipline"], datatype=XSD.string)))
            disc_slug = ind["discipline"].lower().replace(" ", "_")
            if disc_slug in CONTROLLED_DISCIPLINES:
                g.add((u, PROP_CRAFTED_BY_DISCIPLINE, CONTROLLED_DISCIPLINES[disc_slug]))

        if ind.get("min_rating") is not None:
            g.add((u, GW2.minRating, Literal(ind["min_rating"], datatype=XSD.integer)))
            g.add((u, PROP_REQUIRES_DISCIPLINE_RATING, Literal(ind["min_rating"], datatype=XSD.integer)))

        if ind.get("zone"):
            g.add((u, GW2.zone, Literal(ind["zone"], datatype=XSD.string)))

        if ind.get("located_in"):
            g.add((u, PROP_LOCATED_IN_ZONE, ind["located_in"]))

        for ing in ind.get("requires_ingredient", []):
            g.add((u, PROP_REQUIRES_INGREDIENT, ing))

        if ind.get("comment"):
            g.add((u, RDFS.comment, Literal(ind["comment"], datatype=XSD.string)))

    # Populate precursor progression & component dependencies
    g.add((URIRef(str(ITEM["the_living_ravens"])), PROP_IS_PRECURSOR_OF, URIRef(str(ITEM["nevermore"]))))
    g.add((URIRef(str(ITEM["nevermore"])), PROP_HAS_PRECURSOR, URIRef(str(ITEM["the_living_ravens"]))))
    g.add((URIRef(str(ITEM["ravenswood_branch"])), PROP_UPGRADES_TO, URIRef(str(ITEM["ravenswood_staff"]))))
    g.add((URIRef(str(ITEM["ravenswood_staff"])), PROP_UPGRADES_TO, URIRef(str(ITEM["the_raven_spirit"]))))
    g.add((URIRef(str(ITEM["the_raven_spirit"])), PROP_UPGRADES_TO, URIRef(str(ITEM["the_living_ravens"]))))

    g.add((URIRef(str(ITEM["nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["gift_of_nevermore"]))))
    g.add((URIRef(str(ITEM["nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["mystic_tribute"]))))
    g.add((URIRef(str(ITEM["nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["gift_of_mastery"]))))
    g.add((URIRef(str(ITEM["nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["the_living_ravens"]))))

    g.add((URIRef(str(ITEM["gift_of_nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["gift_of_wood"]))))
    g.add((URIRef(str(ITEM["gift_of_nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["gift_of_energy"]))))
    g.add((URIRef(str(ITEM["gift_of_nevermore"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["icy_runestone"]))))

    g.add((URIRef(str(ITEM["mystic_tribute"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["mystic_clover"]))))
    g.add((URIRef(str(ITEM["mystic_tribute"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["amalgamated_gemstone"]))))

    g.add((URIRef(str(ITEM["gift_of_wood"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["spiritwood_plank"]))))
    g.add((URIRef(str(ITEM["gift_of_wood"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["elder_wood_plank"]))))
    g.add((URIRef(str(ITEM["gift_of_wood"])), PROP_REQUIRES_INGREDIENT, URIRef(str(ITEM["ancient_wood_plank"]))))

    return g


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
