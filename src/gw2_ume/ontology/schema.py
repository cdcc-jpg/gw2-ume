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


# Canonical Entity Catalog for Disambiguation and CEA Matching
ENTITY_CATALOG: Dict[str, Dict[str, Any]] = {
    # Precursors
    "ravenswood_branch": {
        "label": "Ravenswood Branch",
        "type": CLASS_PRECURSOR_WEAPON,
        "type_label": "PrecursorWeapon",
        "uri": ITEM["ravenswood_branch"],
        "tier": 1,
        "discipline": "Artificer",
        "min_rating": 450,
        "aliases": ["ravenswood branch", "branch", "tier 1 precursor", "ravenswood staff 1"],
    },
    "ravenswood_staff": {
        "label": "Ravenswood Staff",
        "type": CLASS_PRECURSOR_WEAPON,
        "type_label": "PrecursorWeapon",
        "uri": ITEM["ravenswood_staff"],
        "tier": 2,
        "discipline": "Artificer",
        "min_rating": 450,
        "aliases": ["ravenswood staff", "staff", "tier 2 precursor", "spiritwood staff 2"],
    },
    "the_raven_spirit": {
        "label": "The Raven Spirit",
        "type": CLASS_PRECURSOR_WEAPON,
        "type_label": "PrecursorWeapon",
        "uri": ITEM["the_raven_spirit"],
        "tier": 3,
        "discipline": "Artificer",
        "min_rating": 450,
        "aliases": ["the raven spirit", "raven spirit", "tier 3 precursor", "raven", "spirit"],
    },
    "the_living_ravens": {
        "label": "The Living Ravens",
        "type": CLASS_PRECURSOR_WEAPON,
        "type_label": "PrecursorWeapon",
        "uri": ITEM["the_living_ravens"],
        "tier": 4,
        "discipline": "Artificer",
        "min_rating": 450,
        "aliases": ["the living ravens", "living ravens", "tier 4 precursor", "the livinq ravens", "living raven"],
    },
    # Legendary Weapon
    "nevermore": {
        "label": "Nevermore",
        "type": CLASS_LEGENDARY_WEAPON,
        "type_label": "LegendaryWeapon",
        "uri": ITEM["nevermore"],
        "aliases": ["nevermore", "n3vermore", "legendary staff", "raven staff"],
    },
    # Mystic Forge Components
    "gift_of_nevermore": {
        "label": "Gift of Nevermore",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["gift_of_nevermore"],
        "aliases": ["gift of nevermore", "gift of n3vermore", "nevermore gift", "gift"],
    },
    "mystic_tribute": {
        "label": "Mystic Tribute",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["mystic_tribute"],
        "aliases": ["mystic tribute", "mystic tribut", "tribute", "mystick tribute"],
    },
    "gift_of_mastery": {
        "label": "Gift of Mastery",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["gift_of_mastery"],
        "aliases": ["gift of mastery", "mastery gift", "gift mastery"],
    },
    "gift_of_wood": {
        "label": "Gift of Wood",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["gift_of_wood"],
        "aliases": ["gift of wood", "wood gift"],
    },
    "gift_of_energy": {
        "label": "Gift of Energy",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["gift_of_energy"],
        "aliases": ["gift of energy", "energy gift"],
    },
    # Materials
    "spiritwood_plank": {
        "label": "Spiritwood Plank",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["spiritwood_plank"],
        "aliases": ["spiritwood plank", "spiritwood", "spiritwood planks", "spirit plank"],
    },
    "elder_wood_plank": {
        "label": "Elder Wood Plank",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["elder_wood_plank"],
        "aliases": ["elder wood plank", "elder wood", "elder plank", "elder planks"],
    },
    "ancient_wood_plank": {
        "label": "Ancient Wood Plank",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["ancient_wood_plank"],
        "aliases": ["ancient wood plank", "ancient wood", "ancient plank", "ancient planks"],
    },
    "deldrimor_steel_ingot": {
        "label": "Deldrimor Steel Ingot",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["deldrimor_steel_ingot"],
        "aliases": ["deldrimor steel ingot", "deldrimor steel", "deldrimor ingot", "deldrimor"],
    },
    "elonian_leather_square": {
        "label": "Elonian Leather Square",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["elonian_leather_square"],
        "aliases": ["elonian leather square", "elonian leather", "elonian square"],
    },
    "bolt_of_damask": {
        "label": "Bolt of Damask",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["bolt_of_damask"],
        "aliases": ["bolt of damask", "damask bolt", "damask"],
    },
    "mystic_clover": {
        "label": "Mystic Clover",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["mystic_clover"],
        "aliases": ["mystic clover", "mystic clovers", "clover", "clovers"],
    },
    "mystic_coin": {
        "label": "Mystic Coin",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["mystic_coin"],
        "aliases": ["mystic coin", "mystic coins", "coin", "coins"],
    },
    "amalgamated_gemstone": {
        "label": "Amalgamated Gemstone",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["amalgamated_gemstone"],
        "aliases": ["amalgamated gemstone", "amalgamated gemstones", "amalgamated gem", "amalgams"],
    },
    "bloodstone_shard": {
        "label": "Bloodstone Shard",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["bloodstone_shard"],
        "aliases": ["bloodstone shard", "bloodstone shards", "bloodstone"],
    },
    "icy_runestone": {
        "label": "Icy Runestone",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["icy_runestone"],
        "aliases": ["icy runestone", "icy runestones", "runestone", "runestones"],
    },
    "crystalline_ore": {
        "label": "Crystalline Ore",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["crystalline_ore"],
        "aliases": ["crystalline ore", "cryst ore"],
    },
    # Additional Journey / Collection Items
    "essence_of_the_raven": {
        "label": "Essence of the Raven",
        "type": CLASS_TROPHY_ITEM,
        "type_label": "TrophyItem",
        "uri": ITEM["essence_of_the_raven"],
        "aliases": ["essence of the raven", "raven essence"],
    },
    "jar_of_luminescence": {
        "label": "Jar of Luminescence",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["jar_of_luminescence"],
        "aliases": ["jar of luminescence", "luminescence jar", "jar of luminesce"],
    },
    "spiritwood_staff_shaft": {
        "label": "Spiritwood Staff Shaft",
        "type": CLASS_COMPONENT_ITEM,
        "type_label": "ComponentItem",
        "uri": ITEM["spiritwood_staff_shaft"],
        "aliases": ["spiritwood staff shaft", "staff shaft"],
    },
    "raven_egg": {
        "label": "Raven Egg",
        "type": CLASS_TROPHY_ITEM,
        "type_label": "TrophyItem",
        "uri": ITEM["raven_egg"],
        "aliases": ["raven egg", "egg"],
    },
    "heart_of_the_mists_essence": {
        "label": "Heart of the Mists Essence",
        "type": CLASS_TROPHY_ITEM,
        "type_label": "TrophyItem",
        "uri": ITEM["heart_of_the_mists_essence"],
        "aliases": ["heart of the mists essence", "heart of mists essence", "mist essence"],
    },
    "spiritwood_dowel": {
        "label": "Spiritwood Dowel",
        "type": CLASS_CRAFTING_MATERIAL,
        "type_label": "CraftingMaterial",
        "uri": ITEM["spiritwood_dowel"],
        "aliases": ["spiritwood dowel", "spiritwood dowels"],
    },
    "friends_of_the_owl": {
        "label": "Friends of the Owl",
        "type": CLASS_TROPHY_ITEM,
        "type_label": "TrophyItem",
        "uri": ITEM["friends_of_the_owl"],
        "aliases": ["friends of the owl", "friend of the owl", "friend owl"],
    },
    "friends_of_the_raven": {
        "label": "Friends of the Raven",
        "type": CLASS_TROPHY_ITEM,
        "type_label": "TrophyItem",
        "uri": ITEM["friends_of_the_raven"],
        "aliases": ["friends of the raven", "friend of the raven", "friend raven"],
    },
    "wood_for_the_roost": {
        "label": "Wood for the Roost",
        "type": CLASS_TROPHY_ITEM,
        "type_label": "TrophyItem",
        "uri": ITEM["wood_for_the_roost"],
        "aliases": ["wood for the roost", "wood for roost", "roost wood"],
    },
    # Vendors (priory-ref:vendor/)
    "miyani": {
        "label": "Miyani",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/miyani"],
        "zone": "Lion's Arch",
        "aliases": ["miyani", "mystic forge vendor"],
    },
    "grandmaster_craftsman_hobbs": {
        "label": "Grandmaster Craftsman Hobbs",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/grandmaster_craftsman_hobbs"],
        "zone": "Lion's Arch",
        "aliases": ["grandmaster craftsman hobbs", "hobbs", "legendary vendor"],
    },
    "riel_runecrafter": {
        "label": "Riel Runecrafter",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/riel_runecrafter"],
        "zone": "Lion's Arch",
        "aliases": ["riel runecrafter", "riel", "runecrafter vendor"],
    },
    "shaman_sigurlina": {
        "label": "Shaman Sigurlina",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/shaman_sigurlina"],
        "zone": "Wayfarer Foothills",
        "aliases": ["shaman sigurlina", "sigurlina"],
    },
    "hylek_alchemist": {
        "label": "Hylek Alchemist",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/hylek_alchemist"],
        "zone": "Sparkfly Fen",
        "aliases": ["hylek alchemist", "hylek alchemists", "alchemists", "alchemist"],
    },
    "great_raven_spirit": {
        "label": "Great Raven Spirit",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/great_raven_spirit"],
        "zone": "Lornar's Pass",
        "aliases": ["great raven spirit", "great raven spirit roost", "raven spirit npc"],
    },
    "mist_warrior": {
        "label": "Mist Warrior",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/mist_warrior"],
        "zone": "Heart of the Mists",
        "aliases": ["mist warrior", "mist warriors"],
    },
    "owl_shaman": {
        "label": "Owl Shaman",
        "type": CLASS_NPC_VENDOR,
        "type_label": "NPCVendor",
        "uri": PRIORY_REF["vendor/owl_shaman"],
        "zone": "Dredgehaunt Cliffs",
        "aliases": ["owl shaman"],
    },
    # Zones (priory-ref:zone/)
    "lions_arch": {
        "label": "Lion's Arch",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/lions_arch"],
        "aliases": ["lion's arch", "lions arch", "la"],
    },
    "frostgorge_sound": {
        "label": "Frostgorge Sound",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/frostgorge_sound"],
        "aliases": ["frostgorge sound", "frostgorge", "fgs"],
    },
    "verdant_brink": {
        "label": "Verdant Brink",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/verdant_brink"],
        "aliases": ["verdant brink", "vb"],
    },
    "auric_basin": {
        "label": "Auric Basin",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/auric_basin"],
        "aliases": ["auric basin", "ab"],
    },
    "tangled_depths": {
        "label": "Tangled Depths",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/tangled_depths"],
        "aliases": ["tangled depths", "td"],
    },
    "dragons_stand": {
        "label": "Dragon's Stand",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/dragons_stand"],
        "aliases": ["dragon's stand", "dragons stand", "ds"],
    },
    "wayfarer_foothills": {
        "label": "Wayfarer Foothills",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/wayfarer_foothills"],
        "aliases": ["wayfarer foothills", "wayfarer"],
    },
    "sparkfly_fen": {
        "label": "Sparkfly Fen",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/sparkfly_fen"],
        "aliases": ["sparkfly fen", "sparkfly"],
    },
    "lornars_pass": {
        "label": "Lornar's Pass",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/lornars_pass"],
        "aliases": ["lornar's pass", "lornars pass"],
    },
    "heart_of_the_mists": {
        "label": "Heart of the Mists",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/heart_of_the_mists"],
        "aliases": ["heart of the mists", "mists", "pvp lobby"],
    },
    "dredgehaunt_cliffs": {
        "label": "Dredgehaunt Cliffs",
        "type": CLASS_ZONE,
        "type_label": "Zone",
        "uri": PRIORY_REF["zone/dredgehaunt_cliffs"],
        "aliases": ["dredgehaunt cliffs", "dredgehaunt"],
    },
    # Disciplines (priory-ref:discipline/)
    "artificer": {
        "label": "Artificer",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.artificer,
        "aliases": ["artificer", "artifice"],
    },
    "weaponsmith": {
        "label": "Weaponsmith",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.weaponsmith,
        "aliases": ["weaponsmith", "weapon smith"],
    },
    "huntsman": {
        "label": "Huntsman",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.huntsman,
        "aliases": ["huntsman", "hunt"],
    },
    "armorsmith": {
        "label": "Armorsmith",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.armorsmith,
        "aliases": ["armorsmith", "armor smith"],
    },
    "tailor": {
        "label": "Tailor",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.tailor,
        "aliases": ["tailor"],
    },
    "leatherworker": {
        "label": "Leatherworker",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.leatherworker,
        "aliases": ["leatherworker", "leather worker"],
    },
    "mystic_forge": {
        "label": "Mystic Forge",
        "type": CLASS_CRAFTING_DISCIPLINE,
        "type_label": "CraftingDiscipline",
        "uri": DISCIPLINE.mystic_forge,
        "aliases": ["mystic forge", "mystic frge", "mystick forge", "zommoros"],
    },
}


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

    for curr_key, curr_uri in CONTROLLED_CURRENCIES.items():
        g.add((curr_uri, RDF.type, CLASS_CURRENCY))
        g.add((curr_uri, RDF.type, OWL.NamedIndividual))
        g.add((curr_uri, RDFS.label, Literal(curr_key.replace("_", " ").title(), datatype=XSD.string)))

    for rar_key, rar_uri in CONTROLLED_RARITIES.items():
        g.add((rar_uri, RDF.type, CLASS_RARITY))
        g.add((rar_uri, RDF.type, OWL.NamedIndividual))
        g.add((rar_uri, RDFS.label, Literal(rar_key.capitalize(), datatype=XSD.string)))

    for wpn_key, wpn_uri in CONTROLLED_WEAPONS.items():
        g.add((wpn_uri, RDF.type, CLASS_WEAPON))
        g.add((wpn_uri, RDF.type, OWL.NamedIndividual))
        g.add((wpn_uri, RDFS.label, Literal(wpn_key.replace("_", " ").title(), datatype=XSD.string)))

    return g


__all__ = [
    "Restriction",
    "OntologyClass",
    "ObjectProperty",
    "DatatypeProperty",
    "Individual",
    "AxiomVerificationResult",
    "ENTITY_CATALOG",
    "build_gw2_ontology_graph",
]
