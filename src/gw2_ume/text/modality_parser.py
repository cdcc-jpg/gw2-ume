"""Dynamic Modality Parser and Discourse Clause Classifier for GW2-UME.

Implements discourse clause segmentation, 4-way modal logic classification:
- DEONTIC_RULE (□): Invariant game mechanics (must, requires, cannot, always, unlocked by)
- EPISTEMIC_ESTIMATE (◇): Probability/cost estimates (likely, around, approx, drop rate)
- HYPOTHETICAL (⇒): Conditional contexts (if, unless, when crafting X, in case)
- BOULETIC_FLUFF (⚡): Subjective author commentary (I realized, in my opinion, super long post) -> Filtered/pruned!

Extracts DynamicSemanticFrame and SemanticSlot objects dynamically without hardcoded topic lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import rdflib
from rdflib import Graph, Literal, URIRef, RDF, RDFS, XSD

from gw2_ume.ontology.namespaces import (
    PRIORY,
    PRIORY_REF,
    ITEM,
    RECIPE,
    DISCIPLINE,
    ZONE,
    VENDOR,
    CURRENCY,
)
from gw2_ume.ontology.vocab import (
    GW2,
    GW2RES,
    CLASS_ITEM,
    CLASS_PRECURSOR_WEAPON,
    CLASS_COMPONENT_ITEM,
    CLASS_TROPHY_ITEM,
    CLASS_CRAFTING_MATERIAL,
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_NPC_VENDOR,
    CLASS_ZONE,
    CLASS_MYSTIC_FORGE_RECIPE,
    PROP_REQUIRES_INGREDIENT,
    PROP_REQUIRES_MATERIAL,
    PROP_INGREDIENT_QUANTITY,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_REQUIRES_DISCIPLINE_RATING,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_LOCATED_IN_ZONE,
    PROP_PRECURSOR_TO,
    PROP_UPGRADES_TO,
    PROP_HAS_PRECURSOR,
    CONTROLLED_DISCIPLINES,
)
from gw2_ume.ontology.schema import ENTITY_CATALOG, build_gw2_ontology_graph
from gw2_ume.retrieval.vector_index import VectorIndex, get_default_vector_index


class ModalityType(str, Enum):
    """4-way modal logic classification types."""
    DEONTIC_RULE = "DEONTIC_RULE"          # □ Invariant game mechanics (must, requires, cannot, always, unlocked by)
    EPISTEMIC_ESTIMATE = "EPISTEMIC_ESTIMATE"  # ◇ Probability/cost estimates (likely, around, approx, drop rate)
    HYPOTHETICAL = "HYPOTHETICAL"          # ⇒ Conditional contexts (if, unless, when crafting X)
    BOULETIC_FLUFF = "BOULETIC_FLUFF"      # ⚡ Subjective author commentary (I realized, in my opinion, super long post)

    @property
    def symbol(self) -> str:
        """Returns mathematical modal logic symbol."""
        symbols = {
            ModalityType.DEONTIC_RULE: "□",
            ModalityType.EPISTEMIC_ESTIMATE: "◇",
            ModalityType.HYPOTHETICAL: "⇒",
            ModalityType.BOULETIC_FLUFF: "⚡",
        }
        return symbols.get(self, "•")

    @property
    def badge(self) -> str:
        """Returns colored badge representation for CLI/UI."""
        badges = {
            ModalityType.DEONTIC_RULE: "[bold green]□ DEONTIC_RULE[/]",
            ModalityType.EPISTEMIC_ESTIMATE: "[bold yellow]◇ EPISTEMIC_ESTIMATE[/]",
            ModalityType.HYPOTHETICAL: "[bold cyan]⇒ HYPOTHETICAL[/]",
            ModalityType.BOULETIC_FLUFF: "[dim red]⚡ BOULETIC_FLUFF (pruned)[/]",
        }
        return badges.get(self, str(self.value))


@dataclass
class SemanticSlot:
    """A semantic dimension extracted from a discourse clause."""
    name: str  # e.g., "subject", "relation", "target", "quantity", "discipline", "min_rating", "vendor", "zone", "cost", "condition"
    value: Any  # Extracted value (string, number, entity info)
    slot_type: str  # "entity", "numeric", "concept", "currency", "condition", "relation"
    confidence: float = 1.0
    raw_text: Optional[str] = None
    entity_uri: Optional[str] = None
    entity_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "slot_type": self.slot_type,
            "confidence": round(self.confidence, 4),
            "raw_text": self.raw_text,
            "entity_uri": self.entity_uri,
            "entity_type": self.entity_type,
        }


@dataclass
class DynamicSemanticFrame:
    """A semantic frame representing an invariant rule, estimate, or condition in text."""
    frame_id: str
    clause_text: str
    modality: ModalityType
    confidence: float
    slots: List[SemanticSlot] = field(default_factory=list)
    anchor_entity: Optional[str] = None
    anchor_uri: Optional[str] = None
    anchor_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_slot_value(self, name: str) -> Optional[Any]:
        """Returns the first slot value matching name."""
        for slot in self.slots:
            if slot.name == name:
                return slot.value
        return None

    def get_slots_by_type(self, slot_type: str) -> List[SemanticSlot]:
        """Returns all slots of a given type."""
        return [s for s in self.slots if s.slot_type == slot_type]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "clause_text": self.clause_text,
            "modality": self.modality.value,
            "modality_symbol": self.modality.symbol,
            "confidence": round(self.confidence, 4),
            "anchor_entity": self.anchor_entity,
            "anchor_uri": self.anchor_uri,
            "anchor_type": self.anchor_type,
            "slots": [s.to_dict() for s in self.slots],
            "metadata": self.metadata,
        }


@dataclass
class DiscourseClause:
    """A segmented discourse clause with modal classification."""
    index: int
    text: str
    sentence_idx: int
    modality: ModalityType
    confidence: float
    cues_matched: List[str] = field(default_factory=list)
    is_fluff: bool = False
    frame: Optional[DynamicSemanticFrame] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "sentence_idx": self.sentence_idx,
            "text": self.text,
            "modality": self.modality.value,
            "modality_symbol": self.modality.symbol,
            "confidence": round(self.confidence, 4),
            "cues_matched": self.cues_matched,
            "is_fluff": self.is_fluff,
            "frame": self.frame.to_dict() if self.frame else None,
        }


@dataclass
class ModalityParseResult:
    """Aggregate result of discourse segmentation and modal classification."""
    total_clauses: int
    active_frames: List[DynamicSemanticFrame]
    pruned_fluff_clauses: List[DiscourseClause]
    all_clauses: List[DiscourseClause]
    modality_counts: Dict[str, int]
    entities_extracted: List[Dict[str, Any]]
    triples_extracted: List[Tuple[str, str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_clauses": self.total_clauses,
            "active_frames_count": len(self.active_frames),
            "pruned_fluff_count": len(self.pruned_fluff_clauses),
            "modality_counts": self.modality_counts,
            "active_frames": [f.to_dict() for f in self.active_frames],
            "pruned_fluff": [c.to_dict() for c in self.pruned_fluff_clauses],
            "entities_count": len(self.entities_extracted),
            "triples_count": len(self.triples_extracted),
            "entities": self.entities_extracted,
            "triples": [list(t) for t in self.triples_extracted],
        }


class ModalityParser:
    """Discourse clause segmenter, modal logic classifier, and dynamic semantic frame extractor."""

    # Words that must match case-sensitively or with strict bounds if short/common
    SHORT_COMMON_WORDS: Set[str] = {
        "hope", "the", "rod", "gift", "shard", "bolt", "leaf", "stick", "wood", "water",
        "fire", "air", "earth", "spirit", "branch", "staff", "star", "sun", "moon",
        "gold", "silver", "iron", "steel", "bone", "claw", "fang", "scale", "totem",
        "vial", "blood", "dust", "ore", "ingot", "plank", "silk", "leather",
    }

    # Lexical Cues for 4-way modal logic classification
    BOULETIC_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(i (was mulling|realized|realised|wanted|feel|think|believe|prefer|hope|wish|suggest|recommend|find|mean|guess|suppose|suspect|doubt|reckon|myself don't|don't own))\b", re.IGNORECASE),
        re.compile(r"\b(in my opinion|in my experience|imo|imho|fwiw|tbh|to be honest|honestly|personally|for me|my advice|my goal|my recommendation)\b", re.IGNORECASE),
        re.compile(r"\b(super long post|long post|can't be bothered|feel free to|let me know|thank you|thanks for reading|welcome to my guide|alright squad|dirty guide|bam!)\b", re.IGNORECASE),
        re.compile(r"\b(note from author|author's note|just for fun|i hope this|please let me know)\b", re.IGNORECASE),
    ]

    HYPOTHETICAL_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(if you (are|want|choose|have|need|plan|intend|own|decide|do not|don't)|if you're|if you've)\b", re.IGNORECASE),
        re.compile(r"\b(when (crafting|making|creating|gearing|levelling|leveling|starting|doing)|when you (craft|make|create|reach|level))\b", re.IGNORECASE),
        re.compile(r"\b(unless|assuming|provided that|in case|whenever|upon (crafting|completing|reaching|finishing|acquiring))\b", re.IGNORECASE),
        re.compile(r"\b(whether|as long as|should you|supposing)\b", re.IGNORECASE),
    ]

    EPISTEMIC_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(likely|unlikely|around|approx|approximately|drop rate|chance|estimated|probably|roughly|maybe|seems to)\b", re.IGNORECASE),
        re.compile(r"\b(about\s+\d+|~\s*\d+|\d+\s*-\s*\d+\s*(gold|g|silver|s|copper|c|%|percent|infusions|planks|relics))\b", re.IGNORECASE),
        re.compile(r"\b(frequently|rarely|sometimes|uncertain|optimal circumstances|price difference|relative to the price)\b", re.IGNORECASE),
        re.compile(r"\b(cost (around|about|somewhere|typically)|will cost around|typically around)\b", re.IGNORECASE),
    ]

    DEONTIC_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(must|requires?|requiring|required|cannot|can't|always|unlocked by|prerequisite|needed for|mandatory|essential|strictly)\b", re.IGNORECASE),
        re.compile(r"\b(has to|have to|only|requires level|requires rating|bound|account-bound|soulbound|never|impossible)\b", re.IGNORECASE),
        re.compile(r"\b(recipe is sold|obtained from|crafted at|crafted by|throw .* into|combine .* with|talk to .* at|grab .* from)\b", re.IGNORECASE),
        re.compile(r"\b(you (gotta|need to|have to|must|will need)|you get the actual|throw everything into)\b", re.IGNORECASE),
    ]

    def __init__(
        self,
        vector_index: Optional[VectorIndex] = None,
        ontology_graph: Optional[Graph] = None,
    ):
        self.vector_index = vector_index or get_default_vector_index()
        self.ontology_graph = ontology_graph or build_gw2_ontology_graph()
        self.catalog = ENTITY_CATALOG
        self._entity_candidates = self._build_entity_candidates()

    def _build_entity_candidates(self) -> Dict[str, Dict[str, Any]]:
        """Dynamically indexes known entities from catalog and vector index."""
        candidates: Dict[str, Dict[str, Any]] = {}

        # 1. From declarative catalog
        for key, entity in self.catalog.items():
            uri_str = str(entity["uri"])
            raw_aliases = list(entity.get("aliases", [])) + [entity["label"]]
            candidates[uri_str] = {
                "key": key,
                "label": entity["label"],
                "uri": uri_str,
                "type_label": entity.get("type_label", "Item"),
                "aliases": raw_aliases,
                "tier": entity.get("tier"),
                "discipline": entity.get("discipline"),
                "min_rating": entity.get("min_rating"),
                "zone": entity.get("zone"),
            }

        # 2. From vector index
        for uri, idx_ent in self.vector_index.entities.items():
            if uri not in candidates:
                etype = idx_ent.types[0] if idx_ent.types else "Item"
                key = uri.split("/")[-1].split("#")[-1].lower()
                candidates[uri] = {
                    "key": key,
                    "label": idx_ent.label,
                    "uri": uri,
                    "type_label": etype,
                    "aliases": list(idx_ent.aliases) + [idx_ent.label],
                    "tier": idx_ent.metadata.get("tier"),
                    "discipline": idx_ent.metadata.get("discipline"),
                    "min_rating": idx_ent.metadata.get("min_rating"),
                    "zone": idx_ent.metadata.get("zone"),
                }

        return candidates

    def segment_discourse_clauses(self, text: str) -> List[Tuple[int, str, int]]:
        """Segments text into discourse clauses while preserving sentence indices.

        Returns list of (clause_index, clause_text, sentence_index).
        """
        # Split into sentences (by periods, exclamation marks, question marks, newlines)
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        clauses: List[Tuple[int, str, int]] = []
        clause_idx = 0

        # Sub-clause delimiters: semicolons, em dashes, parenthetical notes, conjunctions
        clause_delimiters = re.compile(
            r"(?:;\s*|—\s*|--\s*|\s+-\s+|,\s*(?=(?:and|but|while|however|because|whereas|whereafter|once|so|as well as|or you can't|or you cannot)\b))"
        )

        for sent_idx, sentence in enumerate(raw_sentences):
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue

            # Split sentence into clauses
            sub_clauses = clause_delimiters.split(sentence_clean)
            for sub in sub_clauses:
                sub_clean = sub.strip()
                # Remove leading/trailing bullet points or numbering
                sub_clean = re.sub(r"^[\d]+[\.\)]\s*", "", sub_clean)
                sub_clean = re.sub(r"^[\*\-•]\s*", "", sub_clean).strip()

                if len(sub_clean) >= 3:
                    clauses.append((clause_idx, sub_clean, sent_idx))
                    clause_idx += 1

        return clauses

    def classify_modality(self, clause_text: str) -> Tuple[ModalityType, float, List[str]]:
        """Classifies the modal logic of a discourse clause.

        Returns (ModalityType, confidence, matched_cues).
        """
        cues_matched: List[str] = []

        # 1. Check for BOULETIC_FLUFF
        for pat in self.BOULETIC_PATTERNS:
            m = pat.findall(clause_text)
            if m:
                for match_item in m:
                    cue_str = match_item[0] if isinstance(match_item, tuple) else match_item
                    cues_matched.append(f"fluff:{cue_str}")

        if cues_matched:
            # Check if there is an overriding strong deontic game rule in the same clause
            # (e.g. "I realized that you must talk to Hobbs")
            has_strong_deontic = any(
                re.search(pat, clause_text) for pat in [
                    r"\bmust\b", r"\brequires?\b", r"\bcrafted by\b", r"\bobtained from\b", r"\bprecursor\b"
                ]
            )
            if not has_strong_deontic:
                return ModalityType.BOULETIC_FLUFF, 0.95, cues_matched

        # 2. Check for HYPOTHETICAL
        hypo_cues = []
        for pat in self.HYPOTHETICAL_PATTERNS:
            m = pat.findall(clause_text)
            if m:
                for match_item in m:
                    cue_str = match_item[0] if isinstance(match_item, tuple) else match_item
                    hypo_cues.append(f"hypo:{cue_str}")

        if hypo_cues:
            return ModalityType.HYPOTHETICAL, 0.90, hypo_cues

        # 3. Check for EPISTEMIC_ESTIMATE
        epistemic_cues = []
        for pat in self.EPISTEMIC_PATTERNS:
            m = pat.findall(clause_text)
            if m:
                for match_item in m:
                    cue_str = match_item[0] if isinstance(match_item, tuple) else match_item
                    epistemic_cues.append(f"epistemic:{cue_str}")

        if epistemic_cues:
            return ModalityType.EPISTEMIC_ESTIMATE, 0.88, epistemic_cues

        # 4. Check for DEONTIC_RULE
        deontic_cues = []
        for pat in self.DEONTIC_PATTERNS:
            m = pat.findall(clause_text)
            if m:
                for match_item in m:
                    cue_str = match_item[0] if isinstance(match_item, tuple) else match_item
                    deontic_cues.append(f"deontic:{cue_str}")

        if deontic_cues:
            return ModalityType.DEONTIC_RULE, 0.92, deontic_cues

        # 5. Default: Informative declarative clause -> DEONTIC_RULE
        return ModalityType.DEONTIC_RULE, 0.75, ["default:declarative"]

    def _match_entity_in_text(self, text: str, alias: str) -> bool:
        """Matches an entity alias in text, enforcing strict case-sensitivity for short/common tokens."""
        alias_clean = alias.strip()
        if not alias_clean or len(alias_clean) < 2:
            return False

        alias_lower = alias_clean.lower()
        is_short_common = (
            alias_lower in self.SHORT_COMMON_WORDS
            or len(alias_clean) <= 4
            or alias_clean.isupper()
            or "." in alias_clean
        )

        escaped = re.escape(alias_clean)
        # Use negative lookbehind and lookahead for word characters to properly handle trailing punctuation (e.g. H.O.P.E.)
        pattern = r"(?<!\w)" + escaped + r"(?!\w)"

        if is_short_common:
            # Case-sensitive exact word or acronym match
            return bool(re.search(pattern, text))
        else:
            # Case-insensitive word boundary match
            return bool(re.search(pattern, text, re.IGNORECASE))

    def extract_semantic_slots(
        self,
        clause_text: str,
        modality: ModalityType,
    ) -> Tuple[List[SemanticSlot], Optional[str], Optional[str], Optional[str]]:
        """Extracts dynamic semantic slots and discovers primary anchor entity from a clause.

        Returns (slots, anchor_label, anchor_uri, anchor_type).
        """
        slots: List[SemanticSlot] = []
        found_entities: List[Dict[str, Any]] = []

        # 1. Match ontology entities dynamically
        for uri, ent in self._entity_candidates.items():
            matched_aliases = []
            for alias in ent["aliases"]:
                if self._match_entity_in_text(clause_text, alias):
                    matched_aliases.append(alias)

            if matched_aliases:
                best_alias = max(matched_aliases, key=len)
                found_entities.append({
                    "uri": uri,
                    "label": ent["label"],
                    "type_label": ent["type_label"],
                    "matched_alias": best_alias,
                    "tier": ent.get("tier"),
                    "discipline": ent.get("discipline"),
                    "min_rating": ent.get("min_rating"),
                    "zone": ent.get("zone"),
                })

        # Sort entities by length of matched alias descending (longest first)
        found_entities.sort(key=lambda x: len(x["matched_alias"]), reverse=True)

        # 2. Extract numeric quantities (e.g. "3 Spiritwood Planks", "250 Mystic Coins")
        qty_pattern = re.compile(r"\b(\d+)\s+([A-Za-z][A-Za-z\s'\-]{2,30})\b")
        for m in qty_pattern.finditer(clause_text):
            num_val = int(m.group(1))
            item_phrase = m.group(2).strip()
            # Check if phrase corresponds to an entity
            matching_ent = next((e for e in found_entities if e["matched_alias"].lower() in item_phrase.lower() or item_phrase.lower() in e["matched_alias"].lower()), None)
            if matching_ent:
                slots.append(SemanticSlot(
                    name="quantity",
                    value=num_val,
                    slot_type="numeric",
                    confidence=0.95,
                    raw_text=m.group(0),
                    entity_uri=matching_ent["uri"],
                    entity_type=matching_ent["type_label"],
                ))

        # 3. Extract Crafting Discipline & Rating
        for disc_key, disc_uri in CONTROLLED_DISCIPLINES.items():
            disc_title = disc_key.title()
            disc_match = re.search(r"\b" + re.escape(disc_title) + r"(?:\s+(\d{3}))?\b", clause_text, re.IGNORECASE)
            if disc_match:
                slots.append(SemanticSlot(
                    name="discipline",
                    value=disc_title,
                    slot_type="concept",
                    confidence=0.95,
                    raw_text=disc_match.group(0),
                    entity_uri=str(disc_uri),
                    entity_type="CraftingDiscipline",
                ))
                if disc_match.group(1):
                    slots.append(SemanticSlot(
                        name="min_rating",
                        value=int(disc_match.group(1)),
                        slot_type="numeric",
                        confidence=0.95,
                        raw_text=disc_match.group(1),
                    ))

        # Standalone rating check (e.g. "requires level 500", "450 maxed out")
        rating_match = re.search(r"\b(?:rating|level|crafting)\s*(\d{3})\b|\b(\d{3})\s*maxed out\b", clause_text, re.IGNORECASE)
        if rating_match and not any(s.name == "min_rating" for s in slots):
            r_val = int(rating_match.group(1) or rating_match.group(2))
            slots.append(SemanticSlot(
                name="min_rating",
                value=r_val,
                slot_type="numeric",
                confidence=0.90,
                raw_text=rating_match.group(0),
            ))

        # 4. Extract Costs & Currencies (e.g. "250-300 gold", "30 gold", "10 pristine fractal relics", "5 laurels and 3 gold")
        cost_matches = re.findall(
            r"(\d+(?:\s*-\s*\d+)?\s*(?:gold|silver|copper|laurels?|badges of honor|unbound magic|volatile magic|winterberries|fractal relics|pristine fractal relics|magnetite shards|spirit shards?|ectoplasm|coins?|g|s|c))\b",
            clause_text,
            re.IGNORECASE,
        )
        for cost_str in cost_matches:
            slots.append(SemanticSlot(
                name="cost",
                value=cost_str.strip(),
                slot_type="currency",
                confidence=0.90,
                raw_text=cost_str.strip(),
            ))

        # 5. Extract Relations & Predicates
        if re.search(r"\b(precursor to|upgrades to|crafted into|tier \d+ is)\b", clause_text, re.IGNORECASE):
            slots.append(SemanticSlot(name="relation", value="precursorTo", slot_type="relation", confidence=0.90))
        elif re.search(r"\b(requires?|need|combine|add|throw .* into)\b", clause_text, re.IGNORECASE):
            slots.append(SemanticSlot(name="relation", value="requiresIngredient", slot_type="relation", confidence=0.90))
        elif re.search(r"\b(talk to|bought from|vendor|sold by|from)\b", clause_text, re.IGNORECASE):
            slots.append(SemanticSlot(name="relation", value="obtainedFromVendor", slot_type="relation", confidence=0.90))
        elif re.search(r"\b(located in|in|at)\b", clause_text, re.IGNORECASE):
            slots.append(SemanticSlot(name="relation", value="locatedInZone", slot_type="relation", confidence=0.90))

        # 6. Add Entity Slots
        anchor_label: Optional[str] = None
        anchor_uri: Optional[str] = None
        anchor_type: Optional[str] = None

        # Anchor selection heuristic:
        # Prioritize PrecursorWeapon > LegendaryWeapon > Item > NPCVendor > Zone > Discipline
        type_priority = {
            "PrecursorWeapon": 5,
            "LegendaryWeapon": 4,
            "Item": 3,
            "ComponentItem": 2,
            "TrophyItem": 2,
            "CraftingMaterial": 2,
            "NPCVendor": 1,
            "Zone": 0,
            "CraftingDiscipline": 0,
        }

        if found_entities:
            sorted_by_type = sorted(
                found_entities,
                key=lambda x: type_priority.get(x["type_label"], 1),
                reverse=True,
            )
            anchor = sorted_by_type[0]
            anchor_label = anchor["label"]
            anchor_uri = anchor["uri"]
            anchor_type = anchor["type_label"]

            for ent in found_entities:
                slot_role = "anchor_entity" if ent["uri"] == anchor_uri else "entity"
                slots.append(SemanticSlot(
                    name=slot_role,
                    value=ent["label"],
                    slot_type="entity",
                    confidence=0.95,
                    raw_text=ent["matched_alias"],
                    entity_uri=ent["uri"],
                    entity_type=ent["type_label"],
                ))
                # Add specific entity attributes as slots if present
                if ent.get("zone"):
                    slots.append(SemanticSlot(
                        name="zone",
                        value=ent["zone"],
                        slot_type="concept",
                        confidence=0.95,
                        raw_text=ent["zone"],
                    ))
                if ent.get("vendor"):
                    slots.append(SemanticSlot(
                        name="vendor",
                        value=ent["vendor"],
                        slot_type="concept",
                        confidence=0.95,
                        raw_text=ent["vendor"],
                    ))

        return slots, anchor_label, anchor_uri, anchor_type

    def parse(self, text: str, filter_fluff: bool = True) -> ModalityParseResult:
        """Parses text into discourse clauses, classifies modality, and constructs semantic frames."""
        raw_clauses = self.segment_discourse_clauses(text)
        all_discourse_clauses: List[DiscourseClause] = []
        active_frames: List[DynamicSemanticFrame] = []
        pruned_fluff: List[DiscourseClause] = []
        modality_counts: Dict[str, int] = {
            ModalityType.DEONTIC_RULE.value: 0,
            ModalityType.EPISTEMIC_ESTIMATE.value: 0,
            ModalityType.HYPOTHETICAL.value: 0,
            ModalityType.BOULETIC_FLUFF.value: 0,
        }

        extracted_entities_map: Dict[str, Dict[str, Any]] = {}
        extracted_triples: List[Tuple[str, str, str]] = []
        seen_triples: Set[Tuple[str, str, str]] = set()

        for c_idx, c_text, s_idx in raw_clauses:
            modality, conf, cues = self.classify_modality(c_text)
            modality_counts[modality.value] += 1
            is_fluff = (modality == ModalityType.BOULETIC_FLUFF)

            d_clause = DiscourseClause(
                index=c_idx,
                text=c_text,
                sentence_idx=s_idx,
                modality=modality,
                confidence=conf,
                cues_matched=cues,
                is_fluff=is_fluff,
            )

            if is_fluff and filter_fluff:
                pruned_fluff.append(d_clause)
                all_discourse_clauses.append(d_clause)
                continue

            # Extract semantic slots and anchor entity
            slots, a_label, a_uri, a_type = self.extract_semantic_slots(c_text, modality)

            frame = DynamicSemanticFrame(
                frame_id=f"frame_{c_idx:03d}",
                clause_text=c_text,
                modality=modality,
                confidence=conf,
                slots=slots,
                anchor_entity=a_label,
                anchor_uri=a_uri,
                anchor_type=a_type,
                metadata={"sentence_idx": s_idx, "cues": cues},
            )
            d_clause.frame = frame
            active_frames.append(frame)
            all_discourse_clauses.append(d_clause)

            # Collect grounded entities
            for slot in slots:
                if slot.slot_type == "entity" and slot.entity_uri:
                    if slot.entity_uri not in extracted_entities_map:
                        extracted_entities_map[slot.entity_uri] = {
                            "uri": slot.entity_uri,
                            "label": str(slot.value),
                            "type_label": slot.entity_type or "Item",
                            "occurrences": 1,
                        }
                    else:
                        extracted_entities_map[slot.entity_uri]["occurrences"] += 1

            # Synthesize relational triples from frame slots
            if a_label and a_uri:
                for slot in slots:
                    if slot.name == "entity" and slot.entity_uri != a_uri:
                        # Candidate relation: (Anchor) -> (Slot Entity)
                        rel_name = "requiresIngredient"
                        if any(s.name == "relation" and s.value == "precursorTo" for s in slots):
                            rel_name = "precursorTo"
                        elif slot.entity_type == "NPCVendor":
                            rel_name = "obtainedFromVendor"
                        elif slot.entity_type == "Zone":
                            rel_name = "locatedInZone"

                        t_tuple = (a_label, rel_name, str(slot.value))
                        if t_tuple not in seen_triples:
                            seen_triples.add(t_tuple)
                            extracted_triples.append(t_tuple)

                    elif slot.name == "discipline":
                        t_tuple = (a_label, "craftedByDiscipline", str(slot.value))
                        if t_tuple not in seen_triples:
                            seen_triples.add(t_tuple)
                            extracted_triples.append(t_tuple)

                    elif slot.name == "zone":
                        t_tuple = (a_label, "locatedInZone", str(slot.value))
                        if t_tuple not in seen_triples:
                            seen_triples.add(t_tuple)
                            extracted_triples.append(t_tuple)

                    elif slot.name == "vendor":
                        t_tuple = (a_label, "obtainedFromVendor", str(slot.value))
                        if t_tuple not in seen_triples:
                            seen_triples.add(t_tuple)
                            extracted_triples.append(t_tuple)

        return ModalityParseResult(
            total_clauses=len(raw_clauses),
            active_frames=active_frames,
            pruned_fluff_clauses=pruned_fluff,
            all_clauses=all_discourse_clauses,
            modality_counts=modality_counts,
            entities_extracted=list(extracted_entities_map.values()),
            triples_extracted=extracted_triples,
        )


__all__ = [
    "ModalityType",
    "SemanticSlot",
    "DynamicSemanticFrame",
    "DiscourseClause",
    "ModalityParseResult",
    "ModalityParser",
]
