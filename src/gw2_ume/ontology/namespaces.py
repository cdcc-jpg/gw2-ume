"""Official Priory RDF Namespaces and Ontology Constants for Guild Wars 2.

Corresponds directly to https://github.com/cdcc-jpg/gw2-priory-def and
https://github.com/cdcc-jpg/gw2-priory-ref.
"""

from rdflib import Namespace, RDF, RDFS, OWL, XSD, SKOS

# Official Priory Namespaces
PRIORY = Namespace("https://priory.gw2/def/")
PRIORY_REF = Namespace("https://priory.gw2/ref/")
ITEM = Namespace("https://priory.gw2/id/item/")
RECIPE = Namespace("https://priory.gw2/id/recipe/")
RARITY = Namespace("https://priory.gw2/ref/rarity/")
WEAPON = Namespace("https://priory.gw2/ref/weapon/")
DISCIPLINE = Namespace("https://priory.gw2/ref/discipline/")
CURRENCY = Namespace("https://priory.gw2/ref/currency/")
ARMOR = Namespace("https://priory.gw2/ref/armor/")
SLOT = Namespace("https://priory.gw2/ref/slot/")
ITEMTYPE = Namespace("https://priory.gw2/ref/itemtype/")
GAMEMODE = Namespace("https://priory.gw2/ref/gamemode/")

# Legacy / Alias Namespaces for backwards compatibility
GW2 = PRIORY
GW2_ITEM = ITEM
GW2_LEG = PRIORY
GW2_RECIPE = RECIPE
GW2_CURRENCY = CURRENCY
GW2_NPC = Namespace("https://priory.gw2/def/npc/")
GW2_PET = Namespace("https://priory.gw2/def/pet/")
GW2_ACHIEVEMENT = Namespace("https://priory.gw2/def/achievement/")

DEFAULT_PRIORY_PREFIXES = {
    "priory": PRIORY,
    "priory-ref": PRIORY_REF,
    "item": ITEM,
    "recipe": RECIPE,
    "rarity": RARITY,
    "weapon": WEAPON,
    "discipline": DISCIPLINE,
    "currency": CURRENCY,
    "armor": ARMOR,
    "slot": SLOT,
    "itemtype": ITEMTYPE,
    "gamemode": GAMEMODE,
    "rdfs": RDFS,
    "owl": OWL,
    "skos": SKOS,
    "rdf": RDF,
    "xsd": XSD,
}

# Priory Core Ontology Class IRIs
CLASS_THING = str(OWL.Thing)
CLASS_ENTITY = str(PRIORY.Entity)
CLASS_ITEM = str(PRIORY.Item)
CLASS_EQUIPABLE = str(PRIORY.EquipableItem)
CLASS_EQUIPMENT = str(PRIORY.EquipableItem)
CLASS_WEAPON = str(PRIORY.Weapon)
CLASS_ARMOR = str(PRIORY.Armor)
CLASS_MATERIAL = str(PRIORY.CraftingMaterial)
CLASS_GIFT = str(PRIORY.GiftItem)
CLASS_TROPHY = str(PRIORY.Item)
CLASS_CURRENCY = str(PRIORY.Currency)
CLASS_NPC = str(PRIORY.Entity)
CLASS_PET = str(PRIORY.Entity)
CLASS_RECIPE = str(PRIORY.Recipe)
CLASS_MYSTIC_FORGE_RECIPE = str(PRIORY.MysticForgeRecipe)
CLASS_DISCIPLINE_RECIPE = str(PRIORY.DisciplineRecipe)
CLASS_LEGENDARY_STEP = str(PRIORY.CollectionHuntPrecursor)
CLASS_PRECURSOR = str(PRIORY.PrecursorWeapon)
CLASS_LEGENDARY_WEAPON = str(PRIORY.LegendaryWeapon)
CLASS_LEGENDARY_ITEM = str(PRIORY.LegendaryItem)
CLASS_COLLECTION_PRECURSOR = str(PRIORY.CollectionHuntPrecursor)

# Priory Core Property IRIs
PROP_REQUIRES_INGREDIENT = str(PRIORY.requiresIngredient)
PROP_REQUIRES_MATERIAL = str(PRIORY.requiresIngredient)
PROP_COSTS_CURRENCY = str(PRIORY.requiresCurrency)
PROP_PRODUCED_BY = str(PRIORY.producedBy)
PROP_PRODUCES_ITEM = str(PRIORY.producesItem)
PROP_SOLD_BY_NPC = str(PRIORY.soldBy)
PROP_ACQUIRED_FROM = str(PRIORY.acquiredFrom)
PROP_UPGRADES_TO = str(PRIORY.upgradesTo)
PROP_REWARD_FOR_STEP = str(PRIORY.rewardForStep)
PROP_CRAFTS_PRECURSOR = str(PRIORY.craftsPrecursor)
PROP_HAS_RARITY = str(PRIORY.hasRarity)
PROP_HAS_WEAPON_TYPE = str(PRIORY.hasWeaponType)
PROP_HAS_PRECURSOR_TYPE = str(PRIORY.hasPrecursorType)
PROP_GW2_ID = str(PRIORY.gw2Id)
PROP_IS_ACCOUNT_BOUND = str(PRIORY.isAccountBound)
PROP_OUTPUT_QUANTITY = str(PRIORY.outputQuantity)
PROP_INGREDIENT_QUANTITY = str(PRIORY.ingredientQuantity)
PROP_SUB_CLASS_OF = str(RDFS.subClassOf)
PROP_TYPE = str(RDF.type)
PROP_LABEL = str(RDFS.label)
PROP_ALT_LABEL = str(SKOS.altLabel)
PROP_PREF_LABEL = str(SKOS.prefLabel)
PROP_COMMENT = str(RDFS.comment)
