"""Guild Wars 2 RDF Namespaces and Ontology Constants."""

from rdflib import Namespace, RDF, RDFS, OWL, XSD

# GW2 Domain Namespaces
GW2 = Namespace("http://gw2.wiki/ontology/")
GW2_ITEM = Namespace("http://gw2.wiki/item/")
GW2_LEG = Namespace("http://gw2.wiki/legendary/")
GW2_NPC = Namespace("http://gw2.wiki/npc/")
GW2_PET = Namespace("http://gw2.wiki/pet/")
GW2_CURRENCY = Namespace("http://gw2.wiki/currency/")
GW2_RECIPE = Namespace("http://gw2.wiki/recipe/")
GW2_ACHIEVEMENT = Namespace("http://gw2.wiki/achievement/")

# Common Ontology Class IRIs
CLASS_THING = str(OWL.Thing)
CLASS_ITEM = str(GW2.Item)
CLASS_EQUIPMENT = str(GW2.EquipmentItem)
CLASS_WEAPON = str(GW2.Weapon)
CLASS_ARMOR = str(GW2.Armor)
CLASS_MATERIAL = str(GW2.MaterialItem)
CLASS_TROPHY = str(GW2.TrophyItem)
CLASS_CURRENCY = str(GW2.Currency)
CLASS_NPC = str(GW2.NPC)
CLASS_PET = str(GW2.RangerPet)
CLASS_RECIPE = str(GW2.Recipe)
CLASS_LEGENDARY_STEP = str(GW2.LegendaryCraftingStep)
CLASS_PRECURSOR = str(GW2.PrecursorWeapon)
CLASS_LEGENDARY_WEAPON = str(GW2.LegendaryWeapon)

# Common Ontology Property IRIs
PROP_REQUIRES_MATERIAL = str(GW2.requiresMaterial)
PROP_COSTS_CURRENCY = str(GW2.costsCurrency)
PROP_PRODUCES_ITEM = str(GW2.producesItem)
PROP_SOLD_BY_NPC = str(GW2.soldByNPC)
PROP_ACQUIRED_FROM = str(GW2.acquiredFrom)
PROP_UPGRADES_TO = str(GW2.upgradesTo)
PROP_REWARD_FOR_STEP = str(GW2.rewardForStep)
PROP_CRAFTS_PRECURSOR = str(GW2.craftsPrecursor)
PROP_SUB_CLASS_OF = str(RDFS.subClassOf)
PROP_TYPE = str(RDF.type)
PROP_LABEL = str(RDFS.label)
PROP_COMMENT = str(RDFS.comment)
