"""Text Preprocessor, Typo Normalizer, Entity Span Extractor, and Table Grid Parsers.

Supports Markdown, CSV, TSV, HTML, and JSON table formats, plus comprehensive
Guild Wars 2 domain jargon and colloquialism normalization.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from gw2_ume.models import EntitySpan, TableGrid


# ============================================================================
# DICTIONARIES & PATTERNS FOR GW2 DOMAIN
# ============================================================================

# Regex rules for precise multi-word & typo normalizations (pattern, canonical_replacement)
GW2_NORMALIZATION_RULES: List[Tuple[str, str]] = [
    # Legendary Collections & Precursors (Gen 2)
    (r"(?i)\bnevermore\s*(?:1|i|vol\.?\s*1)\b", "Nevermore I: Ravenswood Branch"),
    (r"(?i)\bnevermore\s*(?:2|ii|vol\.?\s*2)\b", "Nevermore II: Ravenswood Staff"),
    (r"(?i)\bnevermore\s*(?:3|iii|vol\.?\s*3)\b", "Nevermore III: The Raven Staff"),
    (r"(?i)\bnevermore\s*(?:4|iv|vol\.?\s*4)\b", "Nevermore IV: The Raven Spirit"),
    (r"(?i)\bthe\s+raven\s+staff\b", "The Raven Staff"),
    (r"(?i)\bravenswood\s+staff\b", "Ravenswood Staff"),
    (r"(?i)\bravenswood\s+branch\b", "Ravenswood Branch"),
    (r"(?i)\bthe\s+raven\s+spirit\b", "The Raven Spirit"),

    (r"(?i)\bastralaria\s*(?:1|i|vol\.?\s*1)\b", "Astralaria I: The Device"),
    (r"(?i)\bastralaria\s*(?:2|ii|vol\.?\s*2)\b", "Astralaria II: The Catalyst"),
    (r"(?i)\bastralaria\s*(?:3|iii|vol\.?\s*3)\b", "Astralaria III: The Mechanism"),
    (r"(?i)\bastralaria\s*(?:4|iv|vol\.?\s*4)\b", "Astralaria IV: The Cosmos"),

    (r"(?i)\bhope\s*(?:1|i|vol\.?\s*1)\b", "H.O.P.E. I: Research"),
    (r"(?i)\bhope\s*(?:2|ii|vol\.?\s*2)\b", "H.O.P.E. II: Development"),
    (r"(?i)\bhope\s*(?:3|iii|vol\.?\s*3)\b", "H.O.P.E. III: Prototype"),
    (r"(?i)\bhope\s*(?:4|iv|vol\.?\s*4)\b", "H.O.P.E. IV: The Catalyst"),

    (r"(?i)\bchuka\s+(?:and\s+champawat\s+)?(?:1|i|vol\.?\s*1)\b", "Chuka and Champawat I: Hunt Begun"),
    (r"(?i)\bchuka\s+(?:and\s+champawat\s+)?(?:2|ii|vol\.?\s*2)\b", "Chuka and Champawat II: Ambush"),
    (r"(?i)\bchuka\s+(?:and\s+champawat\s+)?(?:3|iii|vol\.?\s*3)\b", "Chuka and Champawat III: Tigris"),
    (r"(?i)\bchuka\s+(?:and\s+champawat\s+)?(?:4|iv|vol\.?\s*4)\b", "Chuka and Champawat IV: A Baby Named Chuka"),

    # High-frequency materials & currencies
    (r"(?i)\b(?:spiritwood|spirtwood|spirit\s+wood)(?:\s+planks?)?\b", "Spiritwood Plank"),
    (r"(?i)\bdeldrimor(?:\s+steel)?(?:\s+ingots?)?\b", "Deldrimor Steel Ingot"),
    (r"(?i)\belonian(?:\s+leather)?\s+patch(?:es)?\b", "Elonian Leather Patch"),
    (r"(?i)\belonian(?:\s+leather)?(?:\s+squares?)?\b", "Elonian Leather Square"),
    (r"(?i)\b(?:bolt\s+of\s+)?damask\s+patch(?:es)?\b", "Damask Patch"),
    (r"(?i)\b(?:bolt\s+of\s+)?damask\b", "Bolt of Damask"),
    (r"(?i)\bamalgam(?:s|ated)?(?:\s+gems?(?:tones?)?)?\b", "Amalgamated Gemstone"),
    (r"(?i)\b(?:mystic\s+)?clovers?\b", "Mystic Clover"),
    (r"(?i)\b(?:mystic\s+)?trib(?:s|utes?)?\b", "Mystic Tribute"),
    (r"(?i)\b(?:glob\s+of\s+)?ectos?(?:plasm)?\b", "Glob of Ectoplasm"),
    (r"(?i)\b(?:mystic\s+)?(?:mc|mcs|coins?)\b", "Mystic Coin"),
    (r"(?i)\b(?:antique\s+summoning\s+stones?|a\.s\.s\.|ass(?:es)?)\b", "Antique Summoning Stone"),
    (r"(?i)\b(?:obsi|obi|obsidian)(?:\s+shards?)?\b", "Obsidian Shard"),
    (r"(?i)\bbloodstone(?:\s+shards?)?\b", "Bloodstone Shard"),
    (r"(?i)\b(?:philo\s+stone|philosopher\'?s?\s+stone)s?\b", "Philosopher's Stone"),
    (r"(?i)\bmystic\s+crystals?\b", "Mystic Crystal"),
    (r"(?i)\bjade\s+runestones?\b", "Jade Runestone"),
    (r"(?i)\bcurios?\b", "Jade Runestone"),

    # T6 Materials
    (r"(?i)\b(?:vicious\s+)?fangs?\b", "Vicious Fang"),
    (r"(?i)\b(?:armored\s+)?scales?\b", "Armored Scale"),
    (r"(?i)\b(?:ancient\s+)?bones?\b", "Ancient Bone"),
    (r"(?i)\b(?:vial\s+of\s+)?powerful\s+blood\b", "Vial of Powerful Blood"),
    (r"(?i)\b(?:powerful\s+)?venom(?:\s+sacs?)?\b", "Powerful Venom Sac"),
    (r"(?i)\b(?:elaborate\s+)?totems?\b", "Elaborate Totem"),
    (r"(?i)\b(?:pile\s+of\s+)?crystalline\s+dust\b", "Pile of Crystalline Dust"),
    (r"(?i)\b(?:vicious\s+)?claws?\b", "Vicious Claw"),

    # Intermediate Legendary Gifts
    (r"(?i)\bgift\s+of\s+energy\b", "Gift of Energy"),
    (r"(?i)\bgift\s+of\s+wood\b", "Gift of Wood"),
    (r"(?i)\bgift\s+of\s+metal\b", "Gift of Metal"),
    (r"(?i)\bgift\s+of\s+nevermore\b", "Gift of Nevermore"),
    (r"(?i)\bgift\s+of\s+the\s+mists\b", "Gift of the Mists"),
    (r"(?i)\bgift\s+of\s+mastery\b", "Gift of Mastery"),
    (r"(?i)\bgift\s+of\s+fortune\b", "Gift of Fortune"),
    (r"(?i)\bgift\s+of\s+magic\b", "Gift of Magic"),
    (r"(?i)\bgift\s+of\s+might\b", "Gift of Might"),
    (r"(?i)\bgift\s+of\s+battle\b", "Gift of Battle"),
    (r"(?i)\bgift\s+of\s+exploration\b", "Gift of Exploration"),
    (r"(?i)\bgift\s+of\s+insights\b", "Gift of Insights"),
    (r"(?i)\bgift\s+of\s+aurene\b", "Gift of Aurene"),
    (r"(?i)\bgift\s+of\s+craftsmanship\b", "Gift of Craftsmanship"),
    (r"(?i)\bgift\s+of\s+the\s+rider\b", "Gift of the Rider"),

    # Weapons (Legendaries & Precursors)
    (r"(?i)\bnevermore\b", "Nevermore"),
    (r"(?i)\b(?:the\s+)?bifrost\b", "The Bifrost"),
    (r"(?i)\btwilight\b", "Twilight"),
    (r"(?i)\bsunrise\b", "Sunrise"),
    (r"(?i)\beternity\b", "Eternity"),
    (r"(?i)\bbolt\b", "Bolt"),
    (r"(?i)\bincinerator\b", "Incinerator"),
    (r"(?i)\bkudzu\b", "Kudzu"),
    (r"(?i)\b(?:the\s+)?juggernaut\b", "The Juggernaut"),
    (r"(?i)\bquip\b", "Quip"),
    (r"(?i)\b(?:the\s+)?predator\b", "The Predator"),
    (r"(?i)\bfrostfang\b", "Frostfang"),
    (r"(?i)\brodgort\b", "Rodgort"),
    (r"(?i)\bmeteorlogicus\b", "Meteorlogicus"),
    (r"(?i)\b(?:the\s+)?minstrel\b", "The Minstrel"),
    (r"(?i)\b(?:the\s+)?moot\b", "The Moot"),
    (r"(?i)\b(?:the\s+)?flameseeker\s+prophecies\b", "The Flameseeker Prophecies"),
    (r"(?i)\bastralaria\b", "Astralaria"),
    (r"(?i)\bexordium\b", "Exordium"),
    (r"(?i)\b(?:the\s+)?shining\s+blade\b", "The Shining Blade"),
    (r"(?i)\bclaws\s+of\s+the\s+khan-ur\b", "Claws of the Khan-Ur"),
    (r"(?i)\baurene\'?s\s+bite\b", "Aurene's Bite"),
    (r"(?i)\bdusk\b", "Dusk"),
    (r"(?i)\bdawn\b", "Dawn"),
    (r"(?i)\b(?:the\s+)?legend\b", "The Legend"),
    (r"(?i)\bzap\b", "Zap"),
    (r"(?i)\bspark\b", "Spark"),
    (r"(?i)\b(?:the\s+)?lover\b", "The Lover"),
    (r"(?i)\b(?:the\s+)?colossus\b", "The Colossus"),
    (r"(?i)\btooth\s+of\s+frostfang\b", "Tooth of Frostfang"),
    (r"(?i)\bchaos\s+gun\b", "Chaos Gun"),
    (r"(?i)\b(?:the\s+)?hunter\b", "The Hunter"),
    (r"(?i)\bhowler\b", "Howler"),
    (r"(?i)\bstorm\b", "Storm"),
    (r"(?i)\bleaf\s+of\s+kudzu\b", "Leaf of Kudzu"),

    # Currencies
    (r"(?i)\bgold\b", "Gold"),
    (r"(?i)\bsilver\b", "Silver"),
    (r"(?i)\bcopper\b", "Copper"),
    (r"(?i)\bkarma\b", "Karma"),
    (r"(?i)\bspirit\s+shards?\b", "Spirit Shards"),
    (r"(?i)\b(?:pristine\s+)?fractal\s+relics?\b", "Fractal Relics"),
    (r"(?i)\bunbound\s+magic\b", "Unbound Magic"),
    (r"(?i)\bvolatile\s+magic\b", "Volatile Magic"),
    (r"(?i)\bimperial\s+favor\b", "Imperial Favor"),
    (r"(?i)\bastral\s+acclaim\b", "Astral Acclaim"),
    (r"(?i)\blaurels?\b", "Laurel"),
    (r"(?i)\bbadges?\s+of\s+honor\b", "Badge of Honor"),
    (r"(?i)\b(?:wvw\s+)?skirmish(?:\s+claim)?\s+tickets?\b", "WvW Skirmish Claim Ticket"),
]

# Entity type classification mapping for known entities
KNOWN_ENTITY_TYPES: Dict[str, str] = {
    # Materials
    "Spiritwood Plank": "CraftingMaterial",
    "Deldrimor Steel Ingot": "CraftingMaterial",
    "Bolt of Damask": "CraftingMaterial",
    "Elonian Leather Square": "CraftingMaterial",
    "Damask Patch": "CraftingMaterial",
    "Elonian Leather Patch": "CraftingMaterial",
    "Glob of Ectoplasm": "CraftingMaterial",
    "Mystic Coin": "CraftingMaterial",
    "Amalgamated Gemstone": "CraftingMaterial",
    "Mystic Clover": "CraftingMaterial",
    "Obsidian Shard": "CraftingMaterial",
    "Bloodstone Shard": "CraftingMaterial",
    "Philosopher's Stone": "CraftingMaterial",
    "Mystic Crystal": "CraftingMaterial",
    "Jade Runestone": "CraftingMaterial",
    "Antique Summoning Stone": "CraftingMaterial",
    "Vicious Fang": "CraftingMaterial",
    "Armored Scale": "CraftingMaterial",
    "Ancient Bone": "CraftingMaterial",
    "Vial of Powerful Blood": "CraftingMaterial",
    "Powerful Venom Sac": "CraftingMaterial",
    "Elaborate Totem": "CraftingMaterial",
    "Pile of Crystalline Dust": "CraftingMaterial",
    "Vicious Claw": "CraftingMaterial",

    # Intermediate Legendary Gifts
    "Mystic Tribute": "LegendaryGift",
    "Gift of Energy": "LegendaryGift",
    "Gift of Wood": "LegendaryGift",
    "Gift of Metal": "LegendaryGift",
    "Gift of Nevermore": "LegendaryGift",
    "Gift of the Mists": "LegendaryGift",
    "Gift of Mastery": "LegendaryGift",
    "Gift of Fortune": "LegendaryGift",
    "Gift of Magic": "LegendaryGift",
    "Gift of Might": "LegendaryGift",
    "Gift of Battle": "LegendaryGift",
    "Gift of Exploration": "LegendaryGift",
    "Gift of Insights": "LegendaryGift",
    "Gift of Aurene": "LegendaryGift",
    "Gift of Craftsmanship": "LegendaryGift",
    "Gift of the Rider": "LegendaryGift",

    # Weapons (Legendary & Precursors)
    "Nevermore": "Weapon",
    "The Bifrost": "Weapon",
    "Twilight": "Weapon",
    "Sunrise": "Weapon",
    "Eternity": "Weapon",
    "Bolt": "Weapon",
    "Incinerator": "Weapon",
    "Kudzu": "Weapon",
    "The Juggernaut": "Weapon",
    "Quip": "Weapon",
    "The Predator": "Weapon",
    "Frostfang": "Weapon",
    "Rodgort": "Weapon",
    "Meteorlogicus": "Weapon",
    "The Minstrel": "Weapon",
    "The Moot": "Weapon",
    "The Flameseeker Prophecies": "Weapon",
    "Astralaria": "Weapon",
    "Exordium": "Weapon",
    "The Shining Blade": "Weapon",
    "Claws of the Khan-Ur": "Weapon",
    "Aurene's Bite": "Weapon",
    "The Raven Staff": "Weapon",
    "Ravenswood Staff": "Weapon",
    "Ravenswood Branch": "Weapon",
    "Dusk": "Weapon",
    "Dawn": "Weapon",
    "The Legend": "Weapon",
    "Zap": "Weapon",
    "Spark": "Weapon",
    "The Lover": "Weapon",
    "The Colossus": "Weapon",
    "Tooth of Frostfang": "Weapon",
    "Chaos Gun": "Weapon",
    "The Hunter": "Weapon",
    "Storm": "Weapon",
    "Leaf of Kudzu": "Weapon",

    # Achievements / Recipes / Collections
    "Nevermore I: Ravenswood Branch": "Achievement",
    "Nevermore II: Ravenswood Staff": "Achievement",
    "Nevermore III: The Raven Staff": "Achievement",
    "Nevermore IV: The Raven Spirit": "Achievement",
    "Astralaria I: The Device": "Achievement",
    "Astralaria II: The Catalyst": "Achievement",
    "Astralaria III: The Mechanism": "Achievement",
    "Astralaria IV: The Cosmos": "Achievement",
    "H.O.P.E. I: Research": "Achievement",
    "Chuka and Champawat I: Hunt Begun": "Achievement",

    # Currencies
    "Gold": "Currency",
    "Silver": "Currency",
    "Copper": "Currency",
    "Karma": "Currency",
    "Spirit Shards": "Currency",
    "Fractal Relics": "Currency",
    "Pristine Fractal Relics": "Currency",
    "Unbound Magic": "Currency",
    "Volatile Magic": "Currency",
    "Imperial Favor": "Currency",
    "Astral Acclaim": "Currency",
    "Laurel": "Currency",
    "Badge of Honor": "Currency",
    "WvW Skirmish Claim Ticket": "Currency",
}


# ============================================================================
# DECOMPOSED CELL DATA STRUCTURES
# ============================================================================

class DecomposedDict(dict):
    """Decomposed single compound entity (e.g. discipline+rating, vendor+location).

    Behaves as a dictionary, but also supports list-like indexing [0] for backwards-compatibility
    with list consumers.
    """
    def __getitem__(self, key: Any) -> Any:
        if key == 0:
            return self
        return super().__getitem__(key)


class DecomposedList(list):
    """Decomposed list of sub-entities (e.g. ingredients, mixed currencies).

    Behaves as a list of dictionaries, but allows dictionary-style get/lookup if accessed with string key.
    """
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            for d in self:
                if isinstance(d, dict) and key in d:
                    return d[key]
            raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        for d in self:
            if isinstance(d, dict) and key in d:
                return d[key]
        return default


_DYNAMIC_VOCAB_CACHE: Optional[Dict[str, Set[str]]] = None


def get_dynamic_vocab() -> Dict[str, Set[str]]:
    """Dynamically queries loaded ontology vocabulary for disciplines and currencies without hardcoding."""
    global _DYNAMIC_VOCAB_CACHE
    if _DYNAMIC_VOCAB_CACHE is not None:
        return _DYNAMIC_VOCAB_CACHE

    disciplines: Set[str] = set()
    currencies: Set[str] = set()

    try:
        from gw2_ume.ontology.vocab import CONTROLLED_DISCIPLINES, CONTROLLED_CURRENCIES
        for k in CONTROLLED_DISCIPLINES.keys():
            disciplines.add(k.lower())
            disciplines.add(k.replace("_", " ").lower())
        for k in CONTROLLED_CURRENCIES.keys():
            currencies.add(k.lower())
            currencies.add(k.replace("_", " ").lower())
    except Exception:
        pass

    try:
        from gw2_ume.ontology.loader import OntologyLoader
        from gw2_ume.ontology.vocab import CLASS_CRAFTING_DISCIPLINE, CLASS_CURRENCY
        loader = OntologyLoader(auto_load_defaults=True)
        for ind in loader.list_individuals(CLASS_CRAFTING_DISCIPLINE):
            if ind.label:
                disciplines.add(ind.label.lower())
            for l in ind.alt_labels:
                disciplines.add(l.lower())
        for ind in loader.list_individuals(CLASS_CURRENCY):
            if ind.label:
                currencies.add(ind.label.lower())
            for l in ind.alt_labels:
                currencies.add(l.lower())
    except Exception:
        pass

    _DYNAMIC_VOCAB_CACHE = {
        "disciplines": disciplines,
        "currencies": currencies,
    }
    return _DYNAMIC_VOCAB_CACHE


# ============================================================================
# TEXT CLEANER CLASS
# ============================================================================

class TextCleaner:
    """Text preprocessor, typo normalizer, and entity span extractor."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Strip wiki markup, HTML tags, normalize unicode and whitespace."""
        if not text:
            return ""

        # Normalize unicode (NFKC)
        cleaned = unicodedata.normalize("NFKC", str(text))

        # Unescape HTML entities (&amp;, &nbsp;, etc.)
        cleaned = html.unescape(cleaned)

        # Remove MediaWiki templates e.g. {{Item|Spiritwood Plank}} or {{Cost|10|gold}}
        cleaned = re.sub(r"\{\{[^|}]*\|([^}|]*)(?:\|[^}]*)?\}\}", r"\1", cleaned)
        cleaned = re.sub(r"\{\{[^}]+\}\}", "", cleaned)

        # Remove MediaWiki links e.g. [[Spiritwood Plank|Planks]] -> Planks, [[Nevermore]] -> Nevermore
        cleaned = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", cleaned)

        # Remove HTML tags e.g. <span>...</span>
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)

        # Replace non-breaking spaces and redundant whitespaces
        cleaned = cleaned.replace("\u00a0", " ").replace("\u200b", "")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    @classmethod
    def normalize_typos(cls, text: str) -> str:
        """Replace known game typos, abbreviations, and colloquialisms."""
        cleaned = cls.clean_text(text)
        if not cleaned:
            return ""

        # Check exact known entity match (case-insensitive)
        for canon_name in KNOWN_ENTITY_TYPES.keys():
            if cleaned.lower() == canon_name.lower():
                return canon_name

        # Apply regex normalization rules in sequence
        res = cleaned
        for pattern, replacement in GW2_NORMALIZATION_RULES:
            if re.search(pattern, res):
                res = re.sub(pattern, replacement, res)

        return res

    @classmethod
    def extract_quantity(cls, text: str) -> Tuple[str, Optional[Union[float, int]], Optional[str]]:
        """Extract entity surface name, numerical quantity, and unit from a text mention.

        Examples:
            '250x Spiritwood Plank' -> ('Spiritwood Plank', 250, 'count')
            'Spiritwood Plank x250' -> ('Spiritwood Plank', 250, 'count')
            '10,000 Karma'          -> ('Karma', 10000, 'Karma')
            '500g 20s 15c'          -> ('500g 20s 15c', 500.2015, 'Gold')
            'Qty: 10'               -> ('', 10, 'count')
        """
        cleaned = cls.clean_text(text)
        if not cleaned:
            return "", None, None

        # Check GW2 Currency patterns like 500g 20s 15c
        gw2_money_match = re.match(
            r"^(?:(\d+)\s*g)?\s*(?:(\d+)\s*s)?\s*(?:(\d+)\s*c)?$",
            cleaned,
            re.IGNORECASE,
        )
        if gw2_money_match and any(gw2_money_match.groups()):
            g = int(gw2_money_match.group(1) or 0)
            s = int(gw2_money_match.group(2) or 0)
            c = int(gw2_money_match.group(3) or 0)
            total_copper = g * 10000 + s * 100 + c
            gold_equiv = total_copper / 10000.0
            return cleaned, gold_equiv, "Gold"

        # Prefix quantity: "250x Spiritwood Plank" or "250 Spiritwood Plank" or "250 * Spiritwood Plank"
        prefix_match = re.match(
            r"^(\d+(?:[\.,]\d+)?)\s*(?:x|\*|qty:?|count:?|ea\.?)?\s+(.*)$",
            cleaned,
            re.IGNORECASE,
        )
        if prefix_match:
            raw_num, item_part = prefix_match.groups()
            item_part = item_part.strip()
            num_val = float(raw_num.replace(",", ""))
            if num_val.is_integer():
                num_val = int(num_val)
            norm_item = cls.normalize_typos(item_part)
            unit_type = norm_item if KNOWN_ENTITY_TYPES.get(norm_item) == "Currency" else "count"
            return norm_item, num_val, unit_type

        # Suffix quantity: "Spiritwood Plank x250" or "Spiritwood Plank (250)" or "Spiritwood Plank: 250"
        suffix_match = re.match(
            r"^(.*?)\s*(?:[-:\(]\s*|\s+x|\s+qty:?\s*)(\d+(?:[\.,]\d+)?)\s*\)?$",
            cleaned,
            re.IGNORECASE,
        )
        if suffix_match:
            item_part, raw_num = suffix_match.groups()
            item_part = item_part.strip()
            num_val = float(raw_num.replace(",", ""))
            if num_val.is_integer():
                num_val = int(num_val)
            norm_item = cls.normalize_typos(item_part)
            unit_type = norm_item if KNOWN_ENTITY_TYPES.get(norm_item) == "Currency" else "count"
            return norm_item, num_val, unit_type

        # Standalone numeric value e.g. "250" or "10,000"
        single_num_match = re.match(r"^(\d+(?:[\.,]\d+)?)$", cleaned)
        if single_num_match:
            num_val = float(single_num_match.group(1).replace(",", ""))
            if num_val.is_integer():
                num_val = int(num_val)
            return "", num_val, "count"

        # Currency mention: "10,000 Karma", "50 Spirit Shards"
        currency_match = re.match(
            r"^(\d+(?:[\.,]\d+)?)\s+([a-zA-Z\s]+)$",
            cleaned,
            re.IGNORECASE,
        )
        if currency_match:
            raw_num, curr_name = currency_match.groups()
            num_val = float(raw_num.replace(",", ""))
            if num_val.is_integer():
                num_val = int(num_val)
            norm_curr = cls.normalize_typos(curr_name)
            return norm_curr, num_val, norm_curr

        norm = cls.normalize_typos(cleaned)
        return norm, None, None

    @classmethod
    def decompose_compound_cell(
        cls,
        cell_value: str,
        as_list: bool = False,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Cleanly unrolls compound cell mentions into structured components.

        Supports:
        - Ingredient lists: '3x Spiritwood Plank + 3x Deldrimor Steel Ingot' ->
            [{'quantity': 3, 'name': 'Spiritwood Plank'}, {'quantity': 3, 'name': 'Deldrimor Steel Ingot'}]
        - Discipline & rating: 'Artificer (450)' or 'Weaponsmith 500' ->
            {'discipline': 'Artificer', 'rating': 450}
        - Vendor & location: "Hobbs in Lion's Arch" or "Purchased from Hobbs in Lion's Arch" ->
            {'vendor': 'Hobbs', 'zone': "Lion's Arch"}
        - Mixed currencies: '10g + 500 karma' ->
            [{'amount': 10, 'currency': 'Gold'}, {'amount': 500, 'currency': 'Karma'}]
          '5g 50s' ->
            [{'amount': 5, 'currency': 'Gold'}, {'amount': 50, 'currency': 'Silver'}]
        """
        if not cell_value or not str(cell_value).strip():
            return DecomposedList([]) if as_list else DecomposedList([])

        cleaned = cls.clean_text(str(cell_value))
        if not cleaned:
            return DecomposedList([]) if as_list else DecomposedList([])

        vocab = get_dynamic_vocab()
        known_disciplines = vocab["disciplines"]
        known_currencies = vocab["currencies"]

        # 1. Check for GW2 Coins format: e.g. '5g 50s' or '10g 50s 25c' or '10g'
        coin_full_match = re.match(
            r"^(?:(\d+)\s*g)?\s*(?:(\d+)\s*s)?\s*(?:(\d+)\s*c)?$",
            cleaned,
            re.IGNORECASE,
        )
        if coin_full_match and any(coin_full_match.groups()):
            g_str, s_str, c_str = coin_full_match.groups()
            coins: List[Dict[str, Any]] = []
            if g_str:
                coins.append({"amount": int(g_str), "currency": "Gold"})
            if s_str:
                coins.append({"amount": int(s_str), "currency": "Silver"})
            if c_str:
                coins.append({"amount": int(c_str), "currency": "Copper"})
            if coins:
                return DecomposedList(coins)

        # 2. Check for Mixed Currencies: e.g. '10g + 500 karma'
        curr_delims = r"\s*(?:\+|\band\b|&)\s*"
        curr_chunks = re.split(curr_delims, cleaned, flags=re.IGNORECASE)
        if len(curr_chunks) > 1 or any(c in cleaned.lower() for c in ("karma", "spirit shard", "gold", "silver", "laurel")):
            parsed_currencies: List[Dict[str, Any]] = []
            is_all_currencies = True

            for chunk in curr_chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue

                coin_m = re.match(r"^(\d+(?:[,\.]\d+)?)\s*([gsc]|gold|silver|copper)$", chunk, re.IGNORECASE)
                if coin_m:
                    amt_str, denom = coin_m.groups()
                    amt = float(amt_str.replace(",", ""))
                    if amt.is_integer():
                        amt = int(amt)
                    d_lower = denom.lower()
                    c_name = "Gold" if d_lower in ("g", "gold") else ("Silver" if d_lower in ("s", "silver") else "Copper")
                    parsed_currencies.append({"amount": amt, "currency": c_name})
                    continue

                std_m = re.match(r"^(\d+(?:[,\.]\d+)?)\s*(?:x\s*)?([A-Za-z\s'\-]+)$", chunk, re.IGNORECASE)
                if std_m:
                    amt_str, cand_curr = std_m.groups()
                    cand_clean = cand_curr.strip().lower()
                    matched_curr = None
                    if cand_clean in known_currencies:
                        matched_curr = cand_curr.strip().title()
                    else:
                        cand_sing = cand_clean.rstrip("s")
                        if cand_sing in known_currencies:
                            matched_curr = cand_curr.strip().title()
                        elif any(c in cand_clean for c in ("karma", "spirit shard", "laurel", "relic", "badge", "astral", "favor")):
                            matched_curr = cand_curr.strip().title()

                    if matched_curr:
                        amt = float(amt_str.replace(",", ""))
                        if amt.is_integer():
                            amt = int(amt)
                        if "Karma" in matched_curr:
                            matched_curr = "Karma"
                        elif "Spirit Shard" in matched_curr:
                            matched_curr = "Spirit Shards"
                        elif "Fractal Relic" in matched_curr:
                            matched_curr = "Fractal Relics"
                        elif "Badge" in matched_curr:
                            matched_curr = "Badge of Honor"
                        elif "Laurel" in matched_curr:
                            matched_curr = "Laurel"
                        parsed_currencies.append({"amount": amt, "currency": matched_curr})
                        continue

                is_all_currencies = False
                break

            if is_all_currencies and len(parsed_currencies) > 0:
                return DecomposedList(parsed_currencies)

        # 3. Check for Discipline and Rating: e.g. 'Artificer (450)' or 'Weaponsmith 500'
        disc_pattern = re.match(
            r"^(?:(?:crafted\s+by|crafting|discipline|profession):\s*)?([A-Za-z\s]+?)\s*(?:[\(:]\s*|\s+(?:lvl|level|rating)?\s*)(\d{1,4})\s*\)?$",
            cleaned,
            re.IGNORECASE,
        )
        if disc_pattern:
            cand_name, rating_str = disc_pattern.groups()
            cand_norm = cand_name.strip().lower()
            if cand_norm in known_disciplines or any(cand_norm == d.lower() for d in ("artificer", "weaponsmith", "huntsman", "armorsmith", "tailor", "leatherworker", "chef", "jeweler", "scribe")):
                rating_val = int(rating_str)
                res_dict = DecomposedDict({"discipline": cand_name.strip().title(), "rating": rating_val})
                return [res_dict] if as_list else res_dict

        # 4. Check for Vendor and Location/Zone: e.g. "Hobbs in Lion's Arch" or "Purchased from Hobbs in Lion's Arch"
        vendor_prefix_stripped = re.sub(
            r"^(?:purchased\s+from|bought\s+from|sold\s+by|obtained\s+from|vendor:\s*|merchant:\s*|npc:\s*)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        vendor_pattern = re.match(
            r"^([^\(]+?)\s*(?:\s+in\s+|\s+at\s+|\s+@\s+|\s*-\s*|\s*\()\s*([^)]+)\)?$",
            vendor_prefix_stripped,
            re.IGNORECASE,
        )
        if vendor_pattern:
            cand_vendor, cand_zone = vendor_pattern.groups()
            cand_vendor = cand_vendor.strip()
            cand_zone = cand_zone.strip()
            if not cand_vendor.isdigit() and not cand_zone.isdigit() and len(cand_vendor) > 1 and len(cand_zone) > 1:
                if not any(c in cand_vendor.lower() for c in ("gold", "karma", "silver", "copper")):
                    res_dict = DecomposedDict({"vendor": cand_vendor, "zone": cand_zone})
                    return [res_dict] if as_list else res_dict

        # 5. Check for Ingredient Lists with Quantities: e.g. '3x Spiritwood Plank + 3x Deldrimor Steel Ingot'
        ing_delims = r"\s*(?:\+|\band\b|;|\n)\s*"
        is_delimited = bool(re.search(ing_delims, cleaned, re.IGNORECASE) or ("," in cleaned and re.search(r"\d+x?\s+", cleaned)))
        chunks = re.split(ing_delims, cleaned, flags=re.IGNORECASE) if is_delimited else (re.split(r"\s*,\s*", cleaned) if ("," in cleaned and re.search(r"\d+x?\s+", cleaned)) else [cleaned])

        parsed_ingredients: List[Dict[str, Any]] = []
        has_any_explicit_qty = False

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            p_match = re.match(r"^(\d+(?:[,\.]\d+)?)\s*(?:x|\*|qty:?|count:?|ea\.?)?\s+(.*)$", chunk, re.IGNORECASE)
            s_match = re.match(r"^(.*?)\s*(?:[-:\(]\s*|\s+x|\s+qty:?\s*)(\d+(?:[,\.]\d+)?)\s*\)?$", chunk, re.IGNORECASE)

            if p_match:
                raw_num, raw_name = p_match.groups()
                try:
                    v = float(raw_num.replace(",", ""))
                    q = int(v) if v.is_integer() else v
                    has_any_explicit_qty = True
                    norm_name = cls.normalize_typos(raw_name.strip())
                    parsed_ingredients.append({"quantity": q, "name": norm_name})
                    continue
                except ValueError:
                    pass
            elif s_match:
                raw_name, raw_num = s_match.groups()
                try:
                    v = float(raw_num.replace(",", ""))
                    q = int(v) if v.is_integer() else v
                    has_any_explicit_qty = True
                    norm_name = cls.normalize_typos(raw_name.strip())
                    parsed_ingredients.append({"quantity": q, "name": norm_name})
                    continue
                except ValueError:
                    pass

            norm_name = cls.normalize_typos(chunk.strip())
            parsed_ingredients.append({"quantity": 1, "name": norm_name})

        if len(parsed_ingredients) > 1 or (len(parsed_ingredients) == 1 and has_any_explicit_qty):
            return DecomposedList(parsed_ingredients)

        fallback_item = {"name": cls.normalize_typos(cleaned)}
        return [fallback_item] if as_list else DecomposedDict(fallback_item)

    @classmethod
    def split_sentences(cls, text: str) -> List[str]:
        """Split text into sentences, robust against decimals, abbreviations, and roman numerals."""
        cleaned = cls.clean_text(text)
        if not cleaned:
            return []

        # Mask common abbreviations e.g. "Vol.", "e.g.", "i.e.", "Dr.", "St."
        masked = cleaned
        abbrevs = ["Vol.", "vol.", "e.g.", "i.e.", "vs.", "approx.", "ea.", "No.", "no."]
        for i, ab in enumerate(abbrevs):
            masked = masked.replace(ab, f"__ABBR_{i}__")

        # Split on sentence boundaries: (. ! ? followed by whitespace or end of line)
        parts = re.split(r"(?<=[.!?])\s+", masked)

        sentences = []
        for p in parts:
            p_restored = p
            for i, ab in enumerate(abbrevs):
                p_restored = p_restored.replace(f"__ABBR_{i}__", ab)
            p_restored = p_restored.strip()
            if p_restored:
                sentences.append(p_restored)

        return sentences

    @classmethod
    def extract_entity_spans(cls, text: str) -> List[EntitySpan]:
        """Extract candidate entity spans with positions, normalized names, quantities, and candidate types."""
        cleaned = cls.clean_text(text)
        if not cleaned:
            return []

        sentences = cls.split_sentences(cleaned)
        spans: List[EntitySpan] = []

        global_offset = 0

        for s_idx, sentence in enumerate(sentences):
            s_start = cleaned.find(sentence, global_offset)
            if s_start == -1:
                s_start = global_offset
            global_offset = s_start + len(sentence)

            matched_ranges: List[Tuple[int, int]] = []

            for pattern, canonical_target in GW2_NORMALIZATION_RULES:
                for match in re.finditer(pattern, sentence):
                    p_start, p_end = match.span()
                    # Check for overlap with already extracted longer spans
                    if any(existing_s <= p_start and p_end <= existing_e for existing_s, existing_e in matched_ranges):
                        continue

                    # Check for preceding quantity e.g. "250x " or "250 "
                    preceding = sentence[:p_start]
                    quantity_val = None
                    unit_val = None

                    qty_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:x|\*|qty:?)?\s*$", preceding, re.IGNORECASE)
                    span_start_in_sentence = p_start
                    if qty_match:
                        raw_qty = qty_match.group(1)
                        span_start_in_sentence = qty_match.start(1)
                        try:
                            v = float(raw_qty.replace(",", ""))
                            quantity_val = int(v) if v.is_integer() else v
                            unit_val = "count"
                        except ValueError:
                            pass

                    # Check for trailing quantity e.g. " x250"
                    following = sentence[p_end:]
                    span_end_in_sentence = p_end
                    post_qty_match = re.match(r"^\s*(?:x|\*|qty:?)\s*(\d+(?:[\.,]\d+)?)", following, re.IGNORECASE)
                    if post_qty_match:
                        raw_qty = post_qty_match.group(1)
                        span_end_in_sentence = p_end + post_qty_match.end(1)
                        try:
                            v = float(raw_qty.replace(",", ""))
                            quantity_val = int(v) if v.is_integer() else v
                            unit_val = "count"
                        except ValueError:
                            pass

                    raw_span_text = sentence[span_start_in_sentence:span_end_in_sentence]
                    matched_ranges.append((span_start_in_sentence, span_end_in_sentence))

                    pred_type = KNOWN_ENTITY_TYPES.get(canonical_target, "Item")

                    span = EntitySpan(
                        text=raw_span_text,
                        start_char=s_start + span_start_in_sentence,
                        end_char=s_start + span_end_in_sentence,
                        sentence_idx=s_idx,
                        normalized_text=canonical_target,
                        candidate_types=[pred_type],
                        quantity=quantity_val,
                        unit=unit_val,
                        confidence=0.95,
                    )
                    spans.append(span)

        # Sort spans by start_char
        spans.sort(key=lambda s: s.start_char)
        return spans


# ============================================================================
# TABLE PARSERS (Markdown, CSV, TSV, HTML, JSON)
# ============================================================================

class MarkdownTableParser:
    """Parser for Markdown-formatted table grids."""

    @staticmethod
    def parse(markdown_text: str) -> TableGrid:
        """Parse markdown table text into TableGrid."""
        lines = [line.strip() for line in markdown_text.strip().splitlines() if line.strip()]
        if not lines:
            return TableGrid(headers=[], rows=[], metadata={"source_format": "markdown"})

        # Filter lines that look like table rows
        table_lines = [l for l in lines if l.startswith("|") or "|" in l]
        if not table_lines:
            return TableGrid(headers=[], rows=[], metadata={"source_format": "markdown"})

        def split_row(line: str) -> List[str]:
            # Remove outer pipes if present
            content = line.strip()
            if content.startswith("|"):
                content = content[1:]
            if content.endswith("|"):
                content = content[:-1]
            # Split by non-escaped pipe
            cells = [re.sub(r"\\\|", "|", cell.strip()) for cell in re.split(r"(?<!\\)\|", content)]
            return cells

        headers: List[str] = []
        rows: List[List[str]] = []

        first_row = split_row(table_lines[0])
        start_row_idx = 0

        if len(table_lines) > 1:
            second_row = split_row(table_lines[1])
            is_divider = all(re.match(r"^:?-+:?$", cell.strip()) for cell in second_row if cell.strip())
            if is_divider:
                headers = [TextCleaner.clean_text(h) for h in first_row]
                start_row_idx = 2
            else:
                headers = [TextCleaner.clean_text(h) for h in first_row]
                start_row_idx = 1
        else:
            headers = [TextCleaner.clean_text(h) for h in first_row]
            start_row_idx = 1

        num_cols = len(headers) if headers else (len(first_row) if first_row else 0)

        for line in table_lines[start_row_idx:]:
            row_cells = split_row(line)
            if all(re.match(r"^:?-+:?$", cell.strip()) for cell in row_cells if cell.strip()):
                continue
            cleaned_row = [TextCleaner.clean_text(c) for c in row_cells]
            if num_cols > 0:
                if len(cleaned_row) < num_cols:
                    cleaned_row.extend([""] * (num_cols - len(cleaned_row)))
                elif len(cleaned_row) > num_cols and not headers:
                    num_cols = len(cleaned_row)
            rows.append(cleaned_row)

        return TableGrid(headers=headers, rows=rows, metadata={"source_format": "markdown"})


class CSVTableParser:
    """Parser for comma-separated table data."""

    @staticmethod
    def parse(csv_text: str, delimiter: Optional[str] = None) -> TableGrid:
        """Parse CSV text into TableGrid."""
        cleaned_text = csv_text.strip()
        if not cleaned_text:
            return TableGrid(headers=[], rows=[], metadata={"source_format": "csv"})

        if delimiter is None:
            sample = cleaned_text[:2048]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

        reader = csv.reader(io.StringIO(cleaned_text), delimiter=delimiter)
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not raw_rows:
            return TableGrid(headers=[], rows=[], metadata={"source_format": "csv"})

        headers = [TextCleaner.clean_text(h) for h in raw_rows[0]]
        rows = [[TextCleaner.clean_text(c) for c in r] for r in raw_rows[1:]]

        return TableGrid(headers=headers, rows=rows, metadata={"source_format": "csv", "delimiter": delimiter})


class TSVTableParser:
    """Parser for tab-separated table data."""

    @staticmethod
    def parse(tsv_text: str) -> TableGrid:
        """Parse TSV text into TableGrid."""
        return CSVTableParser.parse(tsv_text, delimiter="\t")


class _HTMLTableExtractor(HTMLParser):
    """Internal HTML parser to extract tables cleanly."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: List[Dict[str, Any]] = []
        self._current_table: Optional[Dict[str, Any]] = None
        self._current_row: Optional[List[str]] = None
        self._current_cell: Optional[List[str]] = None
        self._is_th = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self._current_table = {"headers": [], "rows": [], "has_th": False}
        elif tag_lower == "tr":
            if self._current_table is not None:
                self._current_row = []
        elif tag_lower in ("th", "td"):
            self._is_th = (tag_lower == "th")
            if self._current_table is not None:
                self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = None
        elif tag_lower == "tr":
            if self._current_table is not None and self._current_row is not None:
                if self._current_table.get("has_th") and not self._current_table["headers"]:
                    self._current_table["headers"] = self._current_row
                else:
                    self._current_table["rows"].append(self._current_row)
                self._current_row = None
        elif tag_lower in ("th", "td"):
            if self._current_cell is not None and self._current_row is not None:
                cell_text = "".join(self._current_cell).strip()
                self._current_row.append(cell_text)
                if self._is_th and self._current_table is not None:
                    self._current_table["has_th"] = True
                self._current_cell = None

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


class HTMLTableParser:
    """Parser for HTML tables."""

    @staticmethod
    def parse(html_text: str) -> TableGrid:
        """Parse HTML string into TableGrid."""
        extractor = _HTMLTableExtractor()
        extractor.feed(html_text)
        if not extractor.tables:
            return TableGrid(headers=[], rows=[], metadata={"source_format": "html"})

        primary = extractor.tables[0]
        headers = [TextCleaner.clean_text(h) for h in primary.get("headers", [])]
        rows = [[TextCleaner.clean_text(c) for c in r] for r in primary.get("rows", [])]

        if not headers and rows:
            headers = rows[0]
            rows = rows[1:]

        return TableGrid(headers=headers, rows=rows, metadata={"source_format": "html"})


class JSONTableParser:
    """Parser for JSON table representations."""

    @staticmethod
    def parse(json_data: Union[str, List[Any], Dict[str, Any]]) -> TableGrid:
        """Parse JSON data (str, list of dicts, dict with headers/rows) into TableGrid."""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        if isinstance(data, list):
            if not data:
                return TableGrid(headers=[], rows=[], metadata={"source_format": "json"})

            if isinstance(data[0], dict):
                header_keys: List[str] = []
                for item in data:
                    if isinstance(item, dict):
                        for k in item.keys():
                            if k not in header_keys:
                                header_keys.append(k)

                rows: List[List[str]] = []
                for item in data:
                    if isinstance(item, dict):
                        row = [TextCleaner.clean_text(str(item.get(k, ""))) for k in header_keys]
                        rows.append(row)

                return TableGrid(headers=header_keys, rows=rows, metadata={"source_format": "json_records"})

            elif isinstance(data[0], list):
                headers = [TextCleaner.clean_text(str(c)) for c in data[0]]
                rows = [[TextCleaner.clean_text(str(c)) for c in r] for r in data[1:]]
                return TableGrid(headers=headers, rows=rows, metadata={"source_format": "json_arrays"})

        elif isinstance(data, dict):
            if "headers" in data and "rows" in data:
                headers = [TextCleaner.clean_text(str(h)) for h in data["headers"]]
                rows = [[TextCleaner.clean_text(str(c)) for c in r] for r in data["rows"]]
                return TableGrid(headers=headers, rows=rows, metadata={"source_format": "json_schema"})
            elif "columns" in data and "data" in data:
                headers = [TextCleaner.clean_text(str(h)) for h in data["columns"]]
                rows = [[TextCleaner.clean_text(str(c)) for c in r] for r in data["data"]]
                return TableGrid(headers=headers, rows=rows, metadata={"source_format": "json_schema"})
            elif all(isinstance(v, list) for v in data.values()):
                headers = list(data.keys())
                max_len = max((len(v) for v in data.values()), default=0)
                rows = []
                for i in range(max_len):
                    row = [TextCleaner.clean_text(str(data[k][i])) if i < len(data[k]) else "" for k in headers]
                    rows.append(row)
                return TableGrid(headers=headers, rows=rows, metadata={"source_format": "json_columns"})

        return TableGrid(headers=[], rows=[], metadata={"source_format": "json_unknown"})


# ============================================================================
# MASTER PARSING & NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_text(text: str) -> str:
    """Clean and normalize a text string with GW2 typos and abbreviations resolved."""
    return TextCleaner.normalize_typos(text)


def extract_entity_spans(text: str) -> List[EntitySpan]:
    """Extract candidate entity spans from unstructured text."""
    return TextCleaner.extract_entity_spans(text)


def decompose_compound_cell(cell_str: str, as_list: bool = False) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Cleanly unpacks compound cell mentions into structured components."""
    return TextCleaner.decompose_compound_cell(cell_str, as_list=as_list)


def parse_table(raw_input: Union[str, List[Any], Dict[str, Any], TableGrid], format_hint: Optional[str] = None) -> TableGrid:
    """Parse raw table inputs in Markdown, CSV, TSV, HTML, or JSON format into TableGrid."""
    if isinstance(raw_input, TableGrid):
        return raw_input

    if isinstance(raw_input, (list, dict)):
        return JSONTableParser.parse(raw_input)

    raw_str = str(raw_input).strip()
    if not raw_str:
        return TableGrid(headers=[], rows=[])

    hint = (format_hint or "").lower()

    if hint in ("markdown", "md"):
        return MarkdownTableParser.parse(raw_str)
    elif hint == "csv":
        return CSVTableParser.parse(raw_str)
    elif hint == "tsv":
        return TSVTableParser.parse(raw_str)
    elif hint == "html":
        return HTMLTableParser.parse(raw_str)
    elif hint == "json":
        return JSONTableParser.parse(raw_str)

    if raw_str.startswith("{") or raw_str.startswith("["):
        try:
            return JSONTableParser.parse(raw_str)
        except Exception:
            pass

    if "<table" in raw_str.lower():
        return HTMLTableParser.parse(raw_str)

    if "|" in raw_str and "\n" in raw_str:
        lines = [l.strip() for l in raw_str.splitlines() if l.strip()]
        pipe_count = sum(1 for l in lines if "|" in l)
        if pipe_count >= len(lines) * 0.5:
            return MarkdownTableParser.parse(raw_str)

    if "\t" in raw_str:
        return TSVTableParser.parse(raw_str)

    return CSVTableParser.parse(raw_str)


__all__ = [
    "GW2_NORMALIZATION_RULES",
    "KNOWN_ENTITY_TYPES",
    "TextCleaner",
    "MarkdownTableParser",
    "CSVTableParser",
    "TSVTableParser",
    "HTMLTableParser",
    "JSONTableParser",
    "normalize_text",
    "extract_entity_spans",
    "decompose_compound_cell",
    "DecomposedDict",
    "DecomposedList",
    "parse_table",
]
