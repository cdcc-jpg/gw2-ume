"""Vocabulary and URI definitions for GW2-UME using official Priory namespaces."""

from rdflib import Namespace, RDF, RDFS, OWL, XSD, SKOS

from gw2_ume.ontology.namespaces import (
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
    DEFAULT_PRIORY_PREFIXES,
    GW2 as PRIORY_GW2_ALIAS,
    GW2_ITEM,
    GW2_RECIPE,
    GW2_CURRENCY,
)

# Canonical Namespaces
GW2 = Namespace("https://gw2ume.org/ontology#")
GW2RES = Namespace("https://gw2ume.org/resource/")
SCHEMA = Namespace("http://schema.org/")
SH = Namespace("http://www.w3.org/ns/shacl#")

# Core TBox Classes (Domain Universals in https://priory.gw2/def/)
CLASS_THING = OWL.Thing
CLASS_ENTITY = PRIORY.Entity
CLASS_ITEM = PRIORY.Item
CLASS_EQUIPABLE = PRIORY.EquipableItem
CLASS_EQUIPMENT = PRIORY.EquipableItem
CLASS_WEAPON = PRIORY.Weapon
CLASS_ARMOR = PRIORY.Armor
CLASS_TRINKET = PRIORY.Trinket
CLASS_LEGENDARY_WEAPON = PRIORY.LegendaryWeapon
CLASS_PRECURSOR_WEAPON = PRIORY.PrecursorWeapon
CLASS_COMPONENT_ITEM = PRIORY.ComponentItem
CLASS_TROPHY_ITEM = PRIORY.TrophyItem
CLASS_CRAFTING_MATERIAL = PRIORY.CraftingMaterial
CLASS_CURATED_COLLECTION = PRIORY.CuratedCollection
CLASS_COLLECTION_STEP = PRIORY.CollectionStep
CLASS_COLLECTION_TIER = PRIORY.CollectionTier
CLASS_MYSTIC_FORGE_RECIPE = PRIORY.MysticForgeRecipe
CLASS_CRAFTING_RECIPE = PRIORY.DisciplineRecipe
CLASS_DISCIPLINE_RECIPE = PRIORY.DisciplineRecipe
CLASS_CRAFTING_DISCIPLINE = PRIORY.CraftingDiscipline
CLASS_NPC_VENDOR = PRIORY.NPCVendor
CLASS_ZONE = PRIORY.Zone
CLASS_DISCIPLINE_RATING = PRIORY.DisciplineRating
CLASS_INGREDIENT_QUANTITY = PRIORY.IngredientQuantity
CLASS_CURRENCY = PRIORY.Currency
CLASS_DISCIPLINE = PRIORY.Discipline
CLASS_RARITY = PRIORY.Rarity
CLASS_COLLECTION_HUNT_PRECURSOR = PRIORY.CollectionHuntPrecursor
CLASS_LEGENDARY_STEP = PRIORY.CollectionHuntPrecursor
CLASS_PET = PRIORY.Entity

# Core TBox Properties (Property Signatures in https://priory.gw2/def/)
PROP_REQUIRES_INGREDIENT = PRIORY.requiresIngredient
PROP_REQUIRES_MATERIAL = PRIORY.requiresIngredient
PROP_INGREDIENT_QUANTITY = PRIORY.ingredientQuantity
PROP_CRAFTED_BY_DISCIPLINE = PRIORY.craftedByDiscipline
PROP_HAS_DISCIPLINE = PRIORY.craftedByDiscipline
PROP_REQUIRES_DISCIPLINE_RATING = PRIORY.requiresDisciplineRating
PROP_REQUIRED_RATING = PRIORY.requiresDisciplineRating
PROP_OBTAINED_FROM_VENDOR = PRIORY.soldBy
PROP_SOLD_BY = PRIORY.soldBy
PROP_SOLD_BY_NPC = PRIORY.soldBy
PROP_LOCATED_IN_ZONE = PRIORY.locatedInZone
PROP_LOCATED_IN = PRIORY.locatedInZone
PROP_HAS_PRECURSOR = PRIORY.hasPrecursor
PROP_IS_PRECURSOR_OF = PRIORY.isPrecursorOf
PROP_PRECURSOR_TO = PRIORY.precursorTo
PROP_UPGRADES_TO = PRIORY.upgradesTo
PROP_REWARD_FOR_STEP = PRIORY.rewardForStep
PROP_PART_OF_COLLECTION = PRIORY.partOfCollection
PROP_COLLECTION_TIER = PRIORY.tierNumber
PROP_TIER_NUMBER = PRIORY.tierNumber
PROP_OUTPUT_ITEM = PRIORY.producesItem
PROP_PRODUCES_ITEM = PRIORY.producesItem
PROP_PRODUCED_BY = PRIORY.producedBy
PROP_FORGE_SLOT = PRIORY.forgeSlot
PROP_ACQUISITION_METHOD = PRIORY.acquisitionMethod
PROP_CONFIDENCE = PRIORY.confidenceScore
PROP_CONFIDENCE_SCORE = PRIORY.confidenceScore
PROP_COSTS_CURRENCY = PRIORY.requiresCurrency
PROP_REQUIRES_CURRENCY = PRIORY.requiresCurrency

# Controlled Reference Vocabularies (priory-ref: dimensions)
CONTROLLED_DISCIPLINES = {
    "artificer": DISCIPLINE.artificer,
    "weaponsmith": DISCIPLINE.weaponsmith,
    "huntsman": DISCIPLINE.huntsman,
    "armorsmith": DISCIPLINE.armorsmith,
    "tailor": DISCIPLINE.tailor,
    "leatherworker": DISCIPLINE.leatherworker,
    "chef": DISCIPLINE.chef,
    "jeweler": DISCIPLINE.jeweler,
    "scribe": DISCIPLINE.scribe,
    "mystic_forge": DISCIPLINE.mystic_forge,
}

CONTROLLED_CURRENCIES = {
    "coin": CURRENCY.coin,
    "gold": CURRENCY.gold,
    "karma": CURRENCY.karma,
    "spirit_shard": CURRENCY.spirit_shard,
    "laurel": CURRENCY.laurel,
    "mystic_clover": CURRENCY.mystic_clover,
}

CONTROLLED_RARITIES = {
    "junk": RARITY.junk,
    "basic": RARITY.basic,
    "fine": RARITY.fine,
    "masterwork": RARITY.masterwork,
    "rare": RARITY.rare,
    "exotic": RARITY.exotic,
    "ascended": RARITY.ascended,
    "legendary": RARITY.legendary,
}

CONTROLLED_WEAPONS = {
    "staff": WEAPON.staff,
    "sword": WEAPON.sword,
    "dagger": WEAPON.dagger,
    "greatsword": WEAPON.greatsword,
    "axe": WEAPON.axe,
    "hammer": WEAPON.hammer,
    "mace": WEAPON.mace,
    "shield": WEAPON.shield,
    "scepter": WEAPON.scepter,
    "focus": WEAPON.focus,
    "pistol": WEAPON.pistol,
    "rifle": WEAPON.rifle,
    "short_bow": WEAPON.short_bow,
    "longbow": WEAPON.longbow,
    "torch": WEAPON.torch,
    "warhorn": WEAPON.warhorn,
}

__all__ = [
    "PRIORY",
    "PRIORY_REF",
    "ITEM",
    "RECIPE",
    "RARITY",
    "WEAPON",
    "DISCIPLINE",
    "CURRENCY",
    "ARMOR",
    "SLOT",
    "ITEMTYPE",
    "GAMEMODE",
    "ZONE",
    "VENDOR",
    "DEFAULT_PRIORY_PREFIXES",
    "GW2",
    "GW2RES",
    "SCHEMA",
    "SH",
    "RDF",
    "RDFS",
    "OWL",
    "XSD",
    "SKOS",
    "CLASS_THING",
    "CLASS_ENTITY",
    "CLASS_ITEM",
    "CLASS_EQUIPABLE",
    "CLASS_EQUIPMENT",
    "CLASS_WEAPON",
    "CLASS_ARMOR",
    "CLASS_TRINKET",
    "CLASS_LEGENDARY_WEAPON",
    "CLASS_PRECURSOR_WEAPON",
    "CLASS_COMPONENT_ITEM",
    "CLASS_TROPHY_ITEM",
    "CLASS_CRAFTING_MATERIAL",
    "CLASS_CURATED_COLLECTION",
    "CLASS_COLLECTION_STEP",
    "CLASS_COLLECTION_TIER",
    "CLASS_MYSTIC_FORGE_RECIPE",
    "CLASS_CRAFTING_RECIPE",
    "CLASS_DISCIPLINE_RECIPE",
    "CLASS_CRAFTING_DISCIPLINE",
    "CLASS_NPC_VENDOR",
    "CLASS_ZONE",
    "CLASS_DISCIPLINE_RATING",
    "CLASS_INGREDIENT_QUANTITY",
    "CLASS_CURRENCY",
    "CLASS_DISCIPLINE",
    "CLASS_RARITY",
    "CLASS_COLLECTION_HUNT_PRECURSOR",
    "CLASS_LEGENDARY_STEP",
    "PROP_REQUIRES_INGREDIENT",
    "PROP_REQUIRES_MATERIAL",
    "PROP_INGREDIENT_QUANTITY",
    "PROP_CRAFTED_BY_DISCIPLINE",
    "PROP_HAS_DISCIPLINE",
    "PROP_REQUIRES_DISCIPLINE_RATING",
    "PROP_REQUIRED_RATING",
    "PROP_OBTAINED_FROM_VENDOR",
    "PROP_SOLD_BY",
    "PROP_SOLD_BY_NPC",
    "PROP_LOCATED_IN_ZONE",
    "PROP_LOCATED_IN",
    "PROP_HAS_PRECURSOR",
    "PROP_IS_PRECURSOR_OF",
    "PROP_PRECURSOR_TO",
    "PROP_UPGRADES_TO",
    "PROP_REWARD_FOR_STEP",
    "PROP_PART_OF_COLLECTION",
    "PROP_COLLECTION_TIER",
    "PROP_TIER_NUMBER",
    "PROP_OUTPUT_ITEM",
    "PROP_PRODUCES_ITEM",
    "PROP_PRODUCED_BY",
    "PROP_FORGE_SLOT",
    "PROP_ACQUISITION_METHOD",
    "PROP_CONFIDENCE",
    "PROP_CONFIDENCE_SCORE",
    "PROP_COSTS_CURRENCY",
    "PROP_REQUIRES_CURRENCY",
    "CONTROLLED_DISCIPLINES",
    "CONTROLLED_CURRENCIES",
    "CONTROLLED_RARITIES",
    "CONTROLLED_WEAPONS",
]
