#!/usr/bin/env python3
"""Project Priory — Adversarial Semantic Table Interpretation Dataset Generator.

Generates a dense, challenging tabular benchmark dataset joining two related entities:
1. priory:Item (and priory:Weapon for weapon combat metrics)
2. priory:DisciplineRecipe (artisan crafting recipe requirements)

Injects four distinct categories of adversarial column headers:
- Deceptive / False Friends (e.g. gold_price for required_level, item_rank for vendor_value)
- Colloquial Synonyms (e.g. ping_code for chat_link, artwork_uri for icon_url)
- Opaque Identifiers (e.g. col_02, col_04, col_09, col_14)
- Standard Domain Headers (e.g. item_name, damage_type, crafting_discipline, output_quantity)
"""

import base64
import csv
import json
from pathlib import Path
import random
import struct
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
API_ITEMS_CACHE = REPO_ROOT / "data" / "cache" / "api_items.json"
OUTPUT_CSV = REPO_ROOT / "data" / "sample_tables" / "adversarial_table.csv"
OUTPUT_SCHEMA = REPO_ROOT / "data" / "benchmarks" / "ground_truth_adversarial_schema.json"


def encode_item_chat_link(item_id: int) -> str:
    """Encodes a GW2 item ID into official base64 in-game chat link format: [&Ag...]."""
    payload = bytes([0x02, 0x01]) + struct.pack("<I", item_id)
    return "[&" + base64.b64encode(payload).decode("ascii") + "]"


# 16 Column Definitions and their Adversarial Injection Metadata
COLUMNS_DEF = [
    {
        "internal_name": "item_id",
        "injected_header": "col_02",
        "true_property_uri": "priory:gw2Id",
        "true_subject_class": "priory:Item",
        "header_type": "opaque",
        "deception_explanation": "Opaque identifier: Stripped of semantic meaning, concealing the primary GW2 API item identifier."
    },
    {
        "internal_name": "item_name",
        "injected_header": "item_name",
        "true_property_uri": "rdfs:label",
        "true_subject_class": "priory:Item",
        "header_type": "standard",
        "deception_explanation": "Standard header: In-game display title of the item entity."
    },
    {
        "internal_name": "item_type",
        "injected_header": "category_kind",
        "true_property_uri": "priory:hasItemType",
        "true_subject_class": "priory:Item",
        "header_type": "synonym",
        "deception_explanation": "Colloquial synonym: Informally renames ontology item type classification to category kind."
    },
    {
        "internal_name": "item_rarity",
        "injected_header": "tier_grade",
        "true_property_uri": "priory:hasRarity",
        "true_subject_class": "priory:Item",
        "header_type": "synonym",
        "deception_explanation": "Colloquial synonym: Informal gamer terminology substituting for official item rarity tier."
    },
    {
        "internal_name": "required_level",
        "injected_header": "gold_price",
        "true_property_uri": "priory:requiredLevel",
        "true_subject_class": "priory:Item",
        "header_type": "deceptive",
        "deception_explanation": "False friend: Required character level (integer 0-80) misleadingly labeled as monetary gold price."
    },
    {
        "internal_name": "vendor_value",
        "injected_header": "item_rank",
        "true_property_uri": "priory:hasVendorValue",
        "true_subject_class": "priory:Item",
        "header_type": "deceptive",
        "deception_explanation": "False friend: Merchant coin sell value in copper misleadingly labeled as a competitive item rank."
    },
    {
        "internal_name": "chat_link",
        "injected_header": "ping_code",
        "true_property_uri": "priory:chatCode",
        "true_subject_class": "priory:Item",
        "header_type": "synonym",
        "deception_explanation": "Colloquial synonym: Informal gamer slang for official GW2 chat link protocol format [&...]."
    },
    {
        "internal_name": "icon_url",
        "injected_header": "artwork_uri",
        "true_property_uri": "priory:icon",
        "true_subject_class": "priory:Item",
        "header_type": "synonym",
        "deception_explanation": "Colloquial synonym: Official ArenaNet CDN image render URL labeled as generic artwork URI."
    },
    {
        "internal_name": "item_flags",
        "injected_header": "col_04",
        "true_property_uri": "priory:itemFlags",
        "true_subject_class": "priory:Item",
        "header_type": "opaque",
        "deception_explanation": "Opaque identifier: Stripped of semantic meaning, concealing behavioral item restriction flags."
    },
    {
        "internal_name": "damage_type",
        "injected_header": "damage_type",
        "true_property_uri": "priory:damageType",
        "true_subject_class": "priory:Weapon",
        "header_type": "standard",
        "deception_explanation": "Standard header: In-game combat strike damage classification (Physical, Fire, etc.)."
    },
    {
        "internal_name": "min_power",
        "injected_header": "armor_defense",
        "true_property_uri": "priory:minWeaponPower",
        "true_subject_class": "priory:Weapon",
        "header_type": "deceptive",
        "deception_explanation": "False friend: Minimum weapon offensive attack power misleadingly labeled as defensive armor rating."
    },
    {
        "internal_name": "max_power",
        "injected_header": "col_09",
        "true_property_uri": "priory:maxWeaponPower",
        "true_subject_class": "priory:Weapon",
        "header_type": "opaque",
        "deception_explanation": "Opaque identifier: Stripped of semantic meaning, masking upper bound weapon attack power."
    },
    {
        "internal_name": "recipe_id",
        "injected_header": "tax_code",
        "true_property_uri": "priory:gw2RecipeId",
        "true_subject_class": "priory:DisciplineRecipe",
        "header_type": "deceptive",
        "deception_explanation": "False friend: Crafting recipe identifier misleadingly labeled as a financial tax code."
    },
    {
        "internal_name": "crafting_discipline",
        "injected_header": "crafting_discipline",
        "true_property_uri": "priory:requiresDiscipline",
        "true_subject_class": "priory:DisciplineRecipe",
        "header_type": "standard",
        "deception_explanation": "Standard header: Artisan trade discipline required to execute the recipe."
    },
    {
        "internal_name": "recipe_rating",
        "injected_header": "col_14",
        "true_property_uri": "priory:requiredRating",
        "true_subject_class": "priory:DisciplineRecipe",
        "header_type": "opaque",
        "deception_explanation": "Opaque identifier: Stripped of semantic meaning, masking required crafting skill rating (0-500)."
    },
    {
        "internal_name": "output_quantity",
        "injected_header": "output_quantity",
        "true_property_uri": "priory:outputQuantity",
        "true_subject_class": "priory:DisciplineRecipe",
        "header_type": "standard",
        "deception_explanation": "Standard header: Batch item output quantity produced by recipe execution."
    },
]


def load_api_items() -> Dict[str, Any]:
    if API_ITEMS_CACHE.exists():
        with open(API_ITEMS_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    sibling_cache = REPO_ROOT.parent / "gw2-priory-def" / "data" / "cache" / "api_items.json"
    if sibling_cache.exists():
        with open(sibling_cache, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError(
        f"Could not find api_items.json at {API_ITEMS_CACHE} or {sibling_cache}"
    )


def build_dataset_rows(api_items: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    # 1. 24 Weapons: 2 from api_items.json + 22 from ontology graph instances
    graph_weapons = [
        # (id, name, type, rarity, level, vendor_value, chat_link, icon_url, flags, damage_type, min_power, max_power, recipe_id, discipline, rating, qty)
        (30689, "Eternity", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30689), "https://render.guildwars2.com/file/5D565011C537BC79EC6BF5FB5E7D7374BAEE5C8F/455799.png", "AccountBound, NoSalvage", "Physical", 1045, 1155, 4512, "Weaponsmith", 500, 1),
        (30703, "Sunrise", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30703), "https://render.guildwars2.com/file/2D1C1BDBEBFCE76A2BBFDE9DB5228DDA392B742D/455813.png", "AccountBound, NoSalvage", "Physical", 1045, 1155, 4520, "Weaponsmith", 500, 1),
        (30704, "Twilight", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30704), "https://render.guildwars2.com/file/6BBD1F0E70BD6DF9262C64D3F3FAAB52F2EAE757/455814.png", "AccountBound, NoSalvage", "Physical", 1045, 1155, 4521, "Weaponsmith", 500, 1),
        (30699, "Bolt", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30699), "https://render.guildwars2.com/file/07D3ECA97CE20E67FFBD747CC638DEFE8196AE15/455809.png", "AccountBound, NoSalvage", "Physical", 950, 1050, 4516, "Weaponsmith", 500, 1),
        (30684, "Frostfang", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30684), "https://render.guildwars2.com/file/5BB4B2D19D6F3BD09E5C5642AE9462A6B48EAC30/455794.png", "AccountBound, NoSalvage", "Physical", 900, 1100, 4501, "Weaponsmith", 500, 1),
        (30685, "Kudzu", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30685), "https://render.guildwars2.com/file/6B431D0A87A1BCFDF0ED4C8BE6CE9713DF50C19B/455795.png", "AccountBound, NoSalvage", "Physical", 966, 1134, 4502, "Huntsman", 500, 1),
        (30686, "The Dreamer", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30686), "https://render.guildwars2.com/file/E58F4FE568CD79FBE166F313CEEB951EDDC8F389/455796.png", "AccountBound, NoSalvage", "Physical", 955, 1045, 4503, "Huntsman", 500, 1),
        (30687, "Incinerator", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30687), "https://render.guildwars2.com/file/C71F7E9CE6FA49D104764835948C7F72D0B2E158/455797.png", "AccountBound, NoSalvage", "Physical", 970, 1030, 4504, "Weaponsmith", 500, 1),
        (30688, "The Minstrel", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30688), "https://render.guildwars2.com/file/DE132CA6BE5FB6FDEAC9F2BCEF5C7C351D9BFF58/455798.png", "AccountBound, NoSalvage", "Physical", 852, 888, 4505, "Artificer", 500, 1),
        (30690, "The Juggernaut", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30690), "https://render.guildwars2.com/file/1BC25287EF6509618B0DF866297BA7FB2A0DC814/455800.png", "AccountBound, NoSalvage", "Physical", 1035, 1165, 4506, "Weaponsmith", 500, 1),
        (30691, "Kamohoali'i Kotaki", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30691), "https://render.guildwars2.com/file/F40BCE73347C85C53CD5CE57D8B9EF31AEBFE774/455801.png", "AccountBound, NoSalvage", "Physical", 1045, 1155, 4507, "Weaponsmith", 500, 1),
        (30692, "The Moot", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30692), "https://render.guildwars2.com/file/F868772322FE13DF8CE534571A37EC21D95513A1/455802.png", "AccountBound, NoSalvage", "Physical", 940, 1060, 4508, "Weaponsmith", 500, 1),
        (30693, "Quip", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30693), "https://render.guildwars2.com/file/09A15F33CEAAACCE38FBCBAAC457F896CCFF435E/455803.png", "AccountBound, NoSalvage", "Physical", 885, 1015, 4509, "Huntsman", 500, 1),
        (30694, "The Predator", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30694), "https://render.guildwars2.com/file/32CFDF9B172B7EEA283EDECFDE77ACBEF38992CA/455804.png", "AccountBound, NoSalvage", "Physical", 1035, 1165, 4510, "Huntsman", 500, 1),
        (30695, "Meteorlogicus", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30695), "https://render.guildwars2.com/file/BA4A68DF21528652D746CF1B2EF41846A6667B80/455805.png", "AccountBound, NoSalvage", "Physical", 896, 1004, 4511, "Artificer", 500, 1),
        (30696, "The Flameseeker Prophecies", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30696), "https://render.guildwars2.com/file/39B31D8180E1CBE95B5B5EAE60C62AC51897C473/455806.png", "AccountBound, NoSalvage", "Physical", 852, 888, 4513, "Armorsmith", 500, 1),
        (30697, "Frenzy", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30697), "https://render.guildwars2.com/file/6B6006BFCEAAEDEF6DF403D5DA70EB97BE8A4BD3/455807.png", "AccountBound, NoSalvage", "Physical", 1035, 1165, 4514, "Huntsman", 500, 1),
        (30698, "The Bifrost", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30698), "https://render.guildwars2.com/file/31032338DF4A983D5BA4A3D1DEAF9D0D8CFB2332/455808.png", "AccountBound, NoSalvage", "Physical", 985, 1205, 4515, "Artificer", 500, 1),
        (30700, "Rodgort", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30700), "https://render.guildwars2.com/file/D187A9A321B0D85A7E24F7540DCA776E085A8A4C/455810.png", "AccountBound, NoSalvage", "Fire", 828, 912, 4517, "Huntsman", 500, 1),
        (30701, "Kraitkin", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30701), "https://render.guildwars2.com/file/C8BD2296068EFB3D0FFC6ED535EFCDFE9A97EB13/455811.png", "AccountBound, NoSalvage", "Physical", 985, 1205, 4518, "Artificer", 500, 1),
        (30702, "Howler", "Weapon", "Legendary", 80, 100000, encode_item_chat_link(30702), "https://render.guildwars2.com/file/99C3D65F3480B1F3465134FBEBEECBC176C6EF88/455812.png", "AccountBound, NoSalvage", "Physical", 828, 912, 4519, "Huntsman", 500, 1),
        (29185, "Dusk", "Weapon", "Precursor", 80, 50000, encode_item_chat_link(29185), "https://render.guildwars2.com/file/7A942F559C3814B5A69FFFBFEBC3F6BEB4B5FF68/340096.png", "AccountBound, NoSalvage", "Physical", 955, 1055, 6850, "Weaponsmith", 500, 1),
    ]

    for w in graph_weapons:
        rows.append({
            "item_id": w[0],
            "item_name": w[1],
            "item_type": w[2],
            "item_rarity": w[3],
            "required_level": w[4],
            "vendor_value": w[5],
            "chat_link": w[6],
            "icon_url": w[7],
            "item_flags": w[8],
            "damage_type": w[9],
            "min_power": w[10],
            "max_power": w[11],
            "recipe_id": w[12],
            "crafting_discipline": w[13],
            "recipe_rating": w[14],
            "output_quantity": w[15],
        })

    # Add 2 weapons from api_items.json
    api_weapons = [
        (26220, 1205, "Weaponsmith", 375, 1),
        (46971, 7380, "Weaponsmith", 500, 1),
    ]
    for iid, r_id, disc, rat, q in api_weapons:
        it = api_items[str(iid)]
        dtls = it.get("details", {})
        rows.append({
            "item_id": it["id"],
            "item_name": it["name"],
            "item_type": it["type"],
            "item_rarity": it["rarity"],
            "required_level": it["level"],
            "vendor_value": it["vendor_value"],
            "chat_link": it.get("chat_link", encode_item_chat_link(it["id"])),
            "icon_url": it.get("icon", ""),
            "item_flags": ", ".join(it.get("flags", [])),
            "damage_type": dtls.get("damage_type", "Physical"),
            "min_power": dtls.get("min_power", 0),
            "max_power": dtls.get("max_power", 0),
            "recipe_id": r_id,
            "crafting_discipline": disc,
            "recipe_rating": rat,
            "output_quantity": q,
        })

    # 2. 16 Armor Pieces: Envoy Armor from ontology graph instances
    graph_armors = [
        (80258, "Perfected Envoy Breastplate", "Armor", "Ascended", 80, 12000, encode_item_chat_link(80258), "https://render.guildwars2.com/file/17CE478B8BF50920CD3E156D121B66D606C71D22/1633971.png", "AccountBound, NoSalvage", "", 0, 0, 9011, "Armorsmith", 500, 1),
        (80435, "Perfected Envoy Pauldrons", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80435), "https://render.guildwars2.com/file/8181657FBE2D86CF5E34988FBE2CEAC511E73CE7/1633972.png", "AccountBound, NoSalvage", "", 0, 0, 9012, "Armorsmith", 500, 1),
        (80384, "Perfected Envoy Helm", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80384), "https://render.guildwars2.com/file/76D5EDEF70273760CEB379058DCDA071E567FE76/1633970.png", "AccountBound, NoSalvage", "", 0, 0, 9013, "Armorsmith", 500, 1),
        (80145, "Perfected Envoy Gauntlets", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80145), "https://render.guildwars2.com/file/AC26BE82FB499AC5B4D086A8D0FE7D619F0238C9/1633969.png", "AccountBound, NoSalvage", "", 0, 0, 9014, "Armorsmith", 500, 1),
        (80161, "Perfected Envoy Tassets", "Armor", "Ascended", 80, 10000, encode_item_chat_link(80161), "https://render.guildwars2.com/file/EE2B2F44AEFF0BC36AC390A7D3C6A2E44855BA96/1633973.png", "AccountBound, NoSalvage", "", 0, 0, 9015, "Armorsmith", 500, 1),
        (80248, "Perfected Envoy Greaves", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80248), "https://render.guildwars2.com/file/DDC032DC3671239561E8D5041C0667C33D063A48/1633968.png", "AccountBound, NoSalvage", "", 0, 0, 9016, "Armorsmith", 500, 1),
        (80277, "Perfected Envoy Jerkin", "Armor", "Ascended", 80, 12000, encode_item_chat_link(80277), "https://render.guildwars2.com/file/5DE0621375EFDE7E951E93541BD386561B313054/1633977.png", "AccountBound, NoSalvage", "", 0, 0, 9021, "Leatherworker", 500, 1),
        (80190, "Perfected Envoy Shoulderguards", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80190), "https://render.guildwars2.com/file/6438D9BA769D9FA2870F4D2024BD13F10839C293/1633978.png", "AccountBound, NoSalvage", "", 0, 0, 9022, "Leatherworker", 500, 1),
        (80296, "Perfected Envoy Mask", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80296), "https://render.guildwars2.com/file/9BC68D37E63EF05BA6D7A04D4E88FCEB1D3BF329/1633976.png", "AccountBound, NoSalvage", "", 0, 0, 9023, "Leatherworker", 500, 1),
        (80252, "Perfected Envoy Vambraces", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80252), "https://render.guildwars2.com/file/98ACF5A3AEB9A59AC8835A1333C29158FF49841B/1633975.png", "AccountBound, NoSalvage", "", 0, 0, 9024, "Leatherworker", 500, 1),
        (80281, "Perfected Envoy Leggings", "Armor", "Ascended", 80, 10000, encode_item_chat_link(80281), "https://render.guildwars2.com/file/46D932FDF804E1E49C5D0CD0CD3178ACBDC8D67F/1633979.png", "AccountBound, NoSalvage", "", 0, 0, 9025, "Leatherworker", 500, 1),
        (80557, "Perfected Envoy Boots", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80557), "https://render.guildwars2.com/file/D6A6498F8BE96409605AE5792945DDA2D1DE64C4/1633974.png", "AccountBound, NoSalvage", "", 0, 0, 9026, "Leatherworker", 500, 1),
        (80131, "Perfected Envoy Vestments", "Armor", "Ascended", 80, 12000, encode_item_chat_link(80131), "https://render.guildwars2.com/file/EBE61F1A73E477F5BBE4D8E287D0937CEAE1458A/1633983.png", "AccountBound, NoSalvage", "", 0, 0, 9031, "Tailor", 500, 1),
        (80356, "Perfected Envoy Mantle", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80356), "https://render.guildwars2.com/file/48E8D5CEAAED02D0E6C54EE32DDA3B5192135061/1633984.png", "AccountBound, NoSalvage", "", 0, 0, 9032, "Tailor", 500, 1),
        (80200, "Perfected Envoy Hood", "Armor", "Ascended", 80, 8000, encode_item_chat_link(80200), "https://render.guildwars2.com/file/F5C9DA6FE46BFD367E44243C9A6F72750868A783/1633982.png", "AccountBound, NoSalvage", "", 0, 0, 9033, "Tailor", 500, 1),
        (80196, "Perfected Envoy Pants", "Armor", "Ascended", 80, 10000, encode_item_chat_link(80196), "https://render.guildwars2.com/file/20696CA0CD69E1C8770F3410C5CE732386E3C0FF/1633985.png", "AccountBound, NoSalvage", "", 0, 0, 9035, "Tailor", 500, 1),
    ]
    for a in graph_armors:
        rows.append({
            "item_id": a[0],
            "item_name": a[1],
            "item_type": a[2],
            "item_rarity": a[3],
            "required_level": a[4],
            "vendor_value": a[5],
            "chat_link": a[6],
            "icon_url": a[7],
            "item_flags": a[8],
            "damage_type": a[9],
            "min_power": a[10],
            "max_power": a[11],
            "recipe_id": a[12],
            "crafting_discipline": a[13],
            "recipe_rating": a[14],
            "output_quantity": a[15],
        })

    # 3. 15 Trinkets from api_items.json
    trinket_ids = [
        49405, 39554, 37077, 39231, 49416, 39605, 103023, 39596,
        49409, 39609, 37085, 49419, 37075, 39230, 39612
    ]
    for idx, iid in enumerate(trinket_ids):
        it = api_items[str(iid)]
        rows.append({
            "item_id": it["id"],
            "item_name": it["name"],
            "item_type": it["type"],
            "item_rarity": it["rarity"],
            "required_level": it["level"],
            "vendor_value": it["vendor_value"],
            "chat_link": it.get("chat_link", encode_item_chat_link(it["id"])),
            "icon_url": it.get("icon", ""),
            "item_flags": ", ".join(it.get("flags", [])),
            "damage_type": "",
            "min_power": 0,
            "max_power": 0,
            "recipe_id": 5001 + idx,
            "crafting_discipline": "Jeweler",
            "recipe_rating": 500 if it["rarity"] == "Ascended" else 400,
            "output_quantity": 1,
        })

    # 4. 15 Consumables from api_items.json
    consumable_configs = [
        (71659, 3301, "Artificer", 400, 1),
        (75427, 3302, "Artificer", 400, 1),
        (73070, 3303, "Artificer", 400, 1),
        (74185, 3304, "Artificer", 400, 1),
        (70596, 3305, "Artificer", 400, 1),
        (74426, 3306, "Artificer", 400, 1),
        (76150, 3307, "Artificer", 400, 1),
        (45178, 3401, "Artificer", 400, 1),
        (45177, 3402, "Artificer", 300, 1),
        (48308, 8065, "Leatherworker", 500, 1),
        (48284, 8232, "Tailor", 500, 1),
        (45316, 7389, "Artificer", 500, 1),
        (48289, 8196, "Leatherworker", 500, 1),
        (48291, 8088, "Leatherworker", 500, 1),
        (48290, 8064, "Leatherworker", 500, 1),
    ]
    for iid, r_id, disc, rat, q in consumable_configs:
        it = api_items[str(iid)]
        rows.append({
            "item_id": it["id"],
            "item_name": it["name"],
            "item_type": it["type"],
            "item_rarity": it["rarity"],
            "required_level": it["level"],
            "vendor_value": it["vendor_value"],
            "chat_link": it.get("chat_link", encode_item_chat_link(it["id"])),
            "icon_url": it.get("icon", ""),
            "item_flags": ", ".join(it.get("flags", [])),
            "damage_type": "",
            "min_power": 0,
            "max_power": 0,
            "recipe_id": r_id,
            "crafting_discipline": disc,
            "recipe_rating": rat,
            "output_quantity": q,
        })

    # 5. 15 Upgrade Components from api_items.json
    upgrade_configs = [
        (49432, 2209, "Artificer", 500, 1),
        (39333, 2210, "Artificer", 400, 1),
        (24534, 2301, "Jeweler", 0, 1),
        (24464, 2302, "Jeweler", 0, 1),
        (24466, 2303, "Jeweler", 0, 1),
        (24500, 2304, "Jeweler", 0, 1),
        (24465, 2305, "Jeweler", 0, 1),
        (24501, 2306, "Jeweler", 75, 1),
        (24469, 2307, "Jeweler", 75, 1),
        (24470, 2308, "Jeweler", 75, 1),
        (24468, 2309, "Jeweler", 75, 1),
        (24889, 2310, "Jeweler", 75, 1),
        (24471, 2311, "Jeweler", 75, 1),
        (24535, 2312, "Jeweler", 75, 1),
        (24527, 2313, "Jeweler", 150, 1),
    ]
    for iid, r_id, disc, rat, q in upgrade_configs:
        it = api_items[str(iid)]
        rows.append({
            "item_id": it["id"],
            "item_name": it["name"],
            "item_type": it["type"],
            "item_rarity": it["rarity"],
            "required_level": it["level"],
            "vendor_value": it["vendor_value"],
            "chat_link": it.get("chat_link", encode_item_chat_link(it["id"])),
            "icon_url": it.get("icon", ""),
            "item_flags": ", ".join(it.get("flags", [])),
            "damage_type": "",
            "min_power": 0,
            "max_power": 0,
            "recipe_id": r_id,
            "crafting_discipline": disc,
            "recipe_rating": rat,
            "output_quantity": q,
        })

    # 6. 15 Crafting Materials & Refinements from api_items.json
    material_configs = [
        (19680, 1, "Weaponsmith", 0, 1),
        (19683, 2, "Weaponsmith", 75, 1),
        (19688, 3, "Weaponsmith", 150, 1),
        (19681, 4, "Weaponsmith", 225, 1),
        (19684, 5, "Weaponsmith", 300, 1),
        (19685, 6, "Weaponsmith", 400, 1),
        (19687, 7, "Jeweler", 75, 1),
        (19682, 8, "Jeweler", 150, 1),
        (19686, 9, "Jeweler", 225, 1),
        (19710, 10, "Huntsman", 0, 1),
        (19713, 11, "Huntsman", 75, 1),
        (19709, 14, "Huntsman", 300, 1),
        (19712, 15, "Huntsman", 400, 1),
        (19720, 22, "Tailor", 0, 1),
        (19701, 6, "Weaponsmith", 400, 1),
    ]
    for iid, r_id, disc, rat, q in material_configs:
        it = api_items[str(iid)]
        rows.append({
            "item_id": it["id"],
            "item_name": it["name"],
            "item_type": it["type"],
            "item_rarity": it["rarity"],
            "required_level": it["level"],
            "vendor_value": it["vendor_value"],
            "chat_link": it.get("chat_link", encode_item_chat_link(it["id"])),
            "icon_url": it.get("icon", ""),
            "item_flags": ", ".join(it.get("flags", [])),
            "damage_type": "",
            "min_power": 0,
            "max_power": 0,
            "recipe_id": r_id,
            "crafting_discipline": disc,
            "recipe_rating": rat,
            "output_quantity": q,
        })

    return rows


def generate_dataset() -> None:
    print("[+] Loading cached API items...")
    api_items = load_api_items()

    print("[+] Assembling 100 diverse multi-entity rows...")
    raw_rows = build_dataset_rows(api_items)
    if len(raw_rows) != 100:
        raise ValueError(f"Expected exactly 100 rows, got {len(raw_rows)}")

    # Deterministic column shuffling
    rng = random.Random(42)
    columns_shuffled = list(COLUMNS_DEF)
    rng.shuffle(columns_shuffled)

    # Assign column_index to each column in its shuffled position
    ground_truth_schema = {
        "metadata": {
            "dataset_name": "Adversarial Semantic Table Interpretation (ASTI-GW2)",
            "row_count": len(raw_rows),
            "column_count": len(columns_shuffled),
            "entities": ["priory:Item", "priory:Weapon", "priory:DisciplineRecipe"],
            "random_seed": 42
        },
        "columns": []
    }

    injected_headers = []
    internal_keys = []

    for idx, col in enumerate(columns_shuffled):
        injected_headers.append(col["injected_header"])
        internal_keys.append(col["internal_name"])
        ground_truth_schema["columns"].append({
            "column_index": idx,
            "injected_header": col["injected_header"],
            "true_property_uri": col["true_property_uri"],
            "true_subject_class": col["true_subject_class"],
            "header_type": col["header_type"],
            "deception_explanation": col["deception_explanation"]
        })

    # Write CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(injected_headers)
        for row in raw_rows:
            csv_row = [row[key] for key in internal_keys]
            writer.writerow(csv_row)

    print(f"[+] Wrote {len(raw_rows)} rows and {len(injected_headers)} columns to {OUTPUT_CSV}")

    # Write JSON Schema
    OUTPUT_SCHEMA.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SCHEMA, "w", encoding="utf-8") as f:
        json.dump(ground_truth_schema, f, indent=2)

    print(f"[+] Wrote ground truth schema to {OUTPUT_SCHEMA}")


if __name__ == "__main__":
    generate_dataset()
