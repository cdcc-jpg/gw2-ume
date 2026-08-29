"""Table Annotator for Cell Entity Annotation (CEA), Column Type Annotation (CTA), and Column Property Annotation (CPA)."""

from __future__ import annotations
import csv
import io
import re
import difflib
from typing import List, Dict, Any, Tuple, Optional
from gw2_ume.ontology.vocab import (
    GW2,
    GW2RES,
    CLASS_ITEM,
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
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_NPC_VENDOR,
    CLASS_ZONE,
    CLASS_DISCIPLINE_RATING,
    CLASS_INGREDIENT_QUANTITY,
    PROP_REQUIRES_INGREDIENT,
    PROP_INGREDIENT_QUANTITY,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_REQUIRES_DISCIPLINE_RATING,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_LOCATED_IN_ZONE,
    PROP_HAS_PRECURSOR,
    PROP_PART_OF_COLLECTION,
    PROP_COLLECTION_TIER,
    PROP_FORGE_SLOT,
)
from gw2_ume.ontology.schema import ENTITY_CATALOG
from gw2_ume.mesh.models import CellAnnotation, ColumnAnnotation, ColumnPropertyAnnotation


def parse_table_content(content: str, filename: str = "") -> Tuple[List[str], List[List[str]]]:
    """Parses CSV or Markdown formatted table content into headers and rows."""
    content = content.strip()
    if not content:
        return [], []

    # Markdown table detection
    if "|" in content and ("---" in content or content.startswith("|")):
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        table_lines = [l for l in lines if "|" in l and not re.match(r"^\|?\s*[-:]+\s*(\|\s*[-:]+\s*)+\|?$", l)]
        if not table_lines:
            return [], []
        headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
        rows = []
        for line in table_lines[1:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            # pad or truncate cells to header length
            if len(cells) < len(headers):
                cells += [""] * (len(headers) - len(cells))
            rows.append(cells[:len(headers)])
        return headers, rows

    # CSV parsing
    reader = csv.reader(io.StringIO(content))
    all_rows = list(reader)
    if not all_rows:
        return [], []
    headers = [h.strip() for h in all_rows[0]]
    rows = []
    for r in all_rows[1:]:
        if not r or all(c.strip() == "" for c in r):
            continue
        cells = [c.strip() for c in r]
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        rows.append(cells[:len(headers)])
    return headers, rows


def normalize_text(text: str) -> str:
    """Normalizes noisy text by stripping OCR artifacts and standardizing casing."""
    text = text.lower().strip()
    text = re.sub(r"[@#$%^&*_+=\[\]{};:<>?/\\|~]", " ", text)
    # Common OCR/leetspeak normalizations
    text = text.replace("0", "o").replace("1", "i").replace("3", "e").replace("4", "a").replace("5", "s").replace("q", "g")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_cell_entity(cell_val: str, column_header: str = "") -> Optional[Tuple[str, str, str, float]]:
    """Matches a cell string to an entity in ENTITY_CATALOG.

    Returns:
        (entity_uri, canonical_label, entity_type_label, confidence) or None
    """
    if not cell_val or cell_val.strip() == "":
        return None

    raw = cell_val.strip()
    # Numeric literals are not entities
    if raw.isdigit():
        return None

    norm = normalize_text(raw)

    header_norm = normalize_text(column_header)
    if any(k in header_norm for k in ["qty", "quant", "cost", "count", "amount", "rating", "minrating", "level"]) and any(c.isdigit() for c in raw):
        return None

    is_discipline_col = any(w in header_norm for w in ["discipline", "craft", "prof"])
    is_vendor_col = any(w in header_norm for w in ["vendor", "source", "npc", "who"])
    is_zone_col = any(w in header_norm for w in ["zone", "loc", "place", "where"])
    is_step_col = any(w in header_norm for w in ["step", "tier"])

    best_match: Optional[Tuple[str, str, str, float]] = None
    best_score = 0.0

    for key, item in ENTITY_CATALOG.items():
        canonical_label = item["label"]
        uri = str(item["uri"])
        type_label = item["type_label"]
        aliases = item.get("aliases", [])

        # Check exact label match
        if raw.lower() == canonical_label.lower():
            return uri, canonical_label, type_label, 1.0

        # Check aliases
        for alias in aliases:
            norm_alias = normalize_text(alias)
            if norm == norm_alias:
                score = 0.98
                if is_vendor_col and type_label == "NPCVendor":
                    score = 1.0
                elif is_discipline_col and type_label == "CraftingDiscipline":
                    score = 1.0
                elif is_zone_col and type_label == "Zone":
                    score = 1.0
                return uri, canonical_label, type_label, score

            # Fuzzy match
            ratio = difflib.SequenceMatcher(None, norm, norm_alias).ratio()
            if ratio > 0.70 and ratio > best_score:
                adjusted_score = ratio
                if is_discipline_col and type_label != "CraftingDiscipline":
                    adjusted_score -= 0.15
                elif is_vendor_col and type_label != "NPCVendor":
                    adjusted_score -= 0.15
                elif is_zone_col and type_label != "Zone":
                    adjusted_score -= 0.15

                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_match = (uri, canonical_label, type_label, adjusted_score)

    if best_match and best_score >= 0.70:
        return best_match

    # Named entity fallback
    slug = re.sub(r"[^\w\s-]", "", raw).strip().lower().replace(" ", "_")
    fallback_uri = str(GW2RES[f"entity/{slug}"])
    return fallback_uri, raw, "Item", 0.85


def annotate_table(headers: List[str], rows: List[List[str]]) -> Tuple[List[ColumnAnnotation], List[CellAnnotation], List[ColumnPropertyAnnotation]]:
    """Runs CEA, CTA, and CPA on tabular data."""
    cta_list: List[ColumnAnnotation] = []
    cea_list: List[CellAnnotation] = []
    cpa_list: List[ColumnPropertyAnnotation] = []

    num_cols = len(headers)

    # 1. CTA: Column Type Annotation
    col_type_map: Dict[int, str] = {}
    for col_idx, header in enumerate(headers):
        h_norm = normalize_text(header)
        col_values = [rows[r][col_idx] for r in range(len(rows)) if col_idx < len(rows[r])]
        sample_vals = [v for v in col_values if v.strip()][:5]

        type_uri = str(CLASS_ITEM)
        type_label = "Item"
        confidence = 0.85

        if any(w in h_norm for w in ["tier"]):
            type_uri = str(CLASS_COLLECTION_TIER)
            type_label = "CollectionTier"
            confidence = 0.95
        elif any(w in h_norm for w in ["step", "journey"]):
            type_uri = str(CLASS_COLLECTION_STEP)
            type_label = "CollectionStep"
            confidence = 0.95
        elif any(w in h_norm for w in ["precursor", "weapon", "thing", "output"]):
            # Inspect values to determine if precursor or component
            is_precursor = any("raven" in v.lower() or "branch" in v.lower() or "staff" in v.lower() for v in sample_vals)
            if is_precursor:
                type_uri = str(CLASS_PRECURSOR_WEAPON)
                type_label = "PrecursorWeapon"
            else:
                type_uri = str(CLASS_COMPONENT_ITEM)
                type_label = "ComponentItem"
            confidence = 0.90
        elif any(w in h_norm for w in ["component", "mat", "ingredient", "sub_ingredient", "subingredients"]):
            type_uri = str(CLASS_COMPONENT_ITEM)
            type_label = "ComponentItem"
            confidence = 0.90
        elif any(w in h_norm for w in ["qty", "quant", "cost", "count", "amount"]):
            type_uri = str(CLASS_INGREDIENT_QUANTITY)
            type_label = "IngredientQuantity"
            confidence = 0.95
        elif any(w in h_norm for w in ["discipline", "craft", "prof"]):
            type_uri = str(CLASS_CRAFTING_DISCIPLINE)
            type_label = "CraftingDiscipline"
            confidence = 0.95
        elif any(w in h_norm for w in ["rating", "level", "skill", "minrating"]):
            type_uri = str(CLASS_DISCIPLINE_RATING)
            type_label = "DisciplineRating"
            confidence = 0.95
        elif any(w in h_norm for w in ["vendor", "source", "npc", "who"]):
            type_uri = str(CLASS_NPC_VENDOR)
            type_label = "NPCVendor"
            confidence = 0.90
        elif any(w in h_norm for w in ["zone", "loc", "place", "where"]):
            type_uri = str(CLASS_ZONE)
            type_label = "Zone"
            confidence = 0.95
        elif any(w in h_norm for w in ["slot", "forgeslot"]):
            type_uri = str(CLASS_MYSTIC_FORGE_RECIPE)
            type_label = "MysticForgeRecipe"
            confidence = 0.95

        col_type_map[col_idx] = type_label
        cta_list.append(ColumnAnnotation(
            col_idx=col_idx,
            col_name=header,
            type_uri=type_uri,
            type_label=type_label,
            confidence=confidence,
            sample_values=sample_vals,
        ))

    # 2. CEA: Cell Entity Annotation
    for r_idx, row in enumerate(rows):
        for c_idx, cell_val in enumerate(row):
            if not cell_val.strip():
                continue
            matched = match_cell_entity(cell_val, headers[c_idx])
            if matched:
                uri, label, type_label, conf = matched
                cea_list.append(CellAnnotation(
                    row_idx=r_idx,
                    col_idx=c_idx,
                    raw_value=cell_val,
                    entity_uri=uri,
                    label=label,
                    entity_type=type_label,
                    confidence=conf,
                ))

    # 3. CPA: Column Property Annotation
    # Determine relationships between column pairs using semantic domain/range compatibility
    for i, c_src in enumerate(cta_list):
        for j, c_dst in enumerate(cta_list):
            if i == j:
                continue
            prop_uri = None
            prop_label = None
            cpa_conf = 0.0

            # PrecursorWeapon / ComponentItem -> ComponentItem (requiresIngredient)
            if c_src.type_label in ["PrecursorWeapon", "ComponentItem", "Item"] and c_dst.type_label in ["ComponentItem", "CraftingMaterial"]:
                prop_uri = str(PROP_REQUIRES_INGREDIENT)
                prop_label = "requiresIngredient"
                cpa_conf = 0.92
            # Item / Precursor -> CraftingDiscipline (craftedByDiscipline)
            elif c_src.type_label in ["PrecursorWeapon", "ComponentItem", "Item"] and c_dst.type_label == "CraftingDiscipline":
                prop_uri = str(PROP_CRAFTED_BY_DISCIPLINE)
                prop_label = "craftedByDiscipline"
                cpa_conf = 0.95
            # Item -> NPCVendor (obtainedFromVendor)
            elif c_src.type_label in ["PrecursorWeapon", "ComponentItem", "Item"] and c_dst.type_label == "NPCVendor":
                prop_uri = str(PROP_OBTAINED_FROM_VENDOR)
                prop_label = "obtainedFromVendor"
                cpa_conf = 0.90
            # NPCVendor -> Zone (locatedInZone)
            elif c_src.type_label == "NPCVendor" and c_dst.type_label == "Zone":
                prop_uri = str(PROP_LOCATED_IN_ZONE)
                prop_label = "locatedInZone"
                cpa_conf = 0.98
            # Item / Component -> IngredientQuantity (ingredientQuantity)
            elif c_src.type_label in ["PrecursorWeapon", "ComponentItem", "Item"] and c_dst.type_label == "IngredientQuantity":
                prop_uri = str(PROP_INGREDIENT_QUANTITY)
                prop_label = "ingredientQuantity"
                cpa_conf = 0.92
            # Item -> DisciplineRating (requiresDisciplineRating)
            elif c_src.type_label in ["PrecursorWeapon", "ComponentItem", "Item"] and c_dst.type_label == "DisciplineRating":
                prop_uri = str(PROP_REQUIRES_DISCIPLINE_RATING)
                prop_label = "requiresDisciplineRating"
                cpa_conf = 0.94
            # Item -> CollectionTier (tierNumber)
            elif c_src.type_label in ["PrecursorWeapon", "ComponentItem", "Item"] and c_dst.type_label == "CollectionTier":
                prop_uri = str(PROP_COLLECTION_TIER)
                prop_label = "tierNumber"
                cpa_conf = 0.90

            if prop_uri and cpa_conf > 0.0:
                cpa_list.append(ColumnPropertyAnnotation(
                    source_col_idx=i,
                    target_col_idx=j,
                    source_col=c_src.col_name,
                    target_col=c_dst.col_name,
                    property_uri=prop_uri,
                    property_label=prop_label,
                    confidence=cpa_conf,
                ))

    return cta_list, cea_list, cpa_list


__all__ = ["parse_table_content", "normalize_text", "match_cell_entity", "annotate_table"]
