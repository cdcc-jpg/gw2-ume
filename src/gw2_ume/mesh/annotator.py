"""Table Annotator for Cell Entity Annotation (CEA), Column Type Annotation (CTA), and Column Property Annotation (CPA)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from gw2_ume.mesh.models import CellAnnotation, ColumnAnnotation, ColumnPropertyAnnotation
from gw2_ume.ontology.vocab import (
    CLASS_COLLECTION_STEP,
    CLASS_COLLECTION_TIER,
    CLASS_COMPONENT_ITEM,
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_CRAFTING_MATERIAL,
    CLASS_CURATED_COLLECTION,
    CLASS_DISCIPLINE_RATING,
    CLASS_INGREDIENT_QUANTITY,
    CLASS_ITEM,
    CLASS_LEGENDARY_WEAPON,
    CLASS_MYSTIC_FORGE_RECIPE,
    CLASS_NPC_VENDOR,
    CLASS_PRECURSOR_WEAPON,
    CLASS_TROPHY_ITEM,
    CLASS_ZONE,
    GW2,
    GW2RES,
    PROP_COLLECTION_TIER,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_FORGE_SLOT,
    PROP_HAS_PRECURSOR,
    PROP_INGREDIENT_QUANTITY,
    PROP_LOCATED_IN_ZONE,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_PART_OF_COLLECTION,
    PROP_REQUIRES_DISCIPLINE_RATING,
    PROP_REQUIRES_INGREDIENT,
)
from gw2_ume.retrieval.vector_index import VectorIndex, get_default_vector_index


def parse_table_content(content: str, filename: str = "") -> Tuple[List[str], List[List[str]]]:
    """Parses tabular content from Markdown, CSV, or TSV formats into structured headers and rows."""
    content_clean = content.strip()
    if not content_clean:
        return [], []

    # Detect Markdown Table (| col1 | col2 |)
    if "|" in content_clean:
        lines = [line.strip() for line in content_clean.split("\n") if line.strip()]
        table_lines = [l for l in lines if l.startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", l)]
        if not table_lines:
            return [], []
        headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
        rows = []
        for line in table_lines[1:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < len(headers):
                cells += [""] * (len(headers) - len(cells))
            rows.append(cells[:len(headers)])
        return headers, rows

    # Detect TSV or CSV
    delimiter = "\t" if "\t" in content_clean.split("\n")[0] else ","
    reader = csv.reader(io.StringIO(content_clean), delimiter=delimiter)
    all_rows = list(reader)
    if not all_rows:
        return [], []

    headers = [h.strip() for h in all_rows[0]]
    rows = [[c.strip() for c in r] for r in all_rows[1:] if any(c.strip() for c in r)]
    return headers, rows


def normalize_text(text: str) -> str:
    """Normalizes noisy text by stripping OCR artifacts and standardizing casing."""
    text = text.lower().strip()
    text = re.sub(r"[@#$%^&*_+=\[\]{};:<>?/\\|~]", " ", text)
    # Common OCR/leetspeak normalizations
    text = text.replace("0", "o").replace("1", "i").replace("3", "e").replace("4", "a").replace("5", "s")
    text = re.sub(r"q(?!u)", "g", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_cell_entity(
    cell_val: str,
    column_header: str = "",
    vector_index: Optional[VectorIndex] = None,
) -> Optional[Tuple[str, str, str, float]]:
    """Matches a cell string to an entity in the vector index.

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
    is_step_col = any(w in header_norm for w in ["step", "journey"])
    is_tier_col = any(w in header_norm for w in ["tier"])
    is_precursor_col = any(w in header_norm for w in ["precursor", "weapon", "thing", "output"])

    slug = re.sub(r"[^\w\s-]", "", raw).strip().lower().replace(" ", "_")

    if is_tier_col or (is_step_col and norm.startswith("tier")):
        return str(GW2RES[f"tier/{slug}"]), raw, "CollectionTier", 0.95

    if is_step_col:
        return str(GW2RES[f"step/{slug}"]), raw, "CollectionStep", 0.95

    index = vector_index if vector_index is not None else get_default_vector_index()
    results = index.search_entities(raw, top_k=5)

    if results:
        top_cand = results[0]
        score = top_cand.score
        type_label = top_cand.metadata.get("type_label", top_cand.types[0] if top_cand.types else "Item")
        canonical_label = top_cand.metadata.get("canonical_label", top_cand.label)
        uri = top_cand.iri

        if is_discipline_col and type_label == "CraftingDiscipline":
            score = max(score, 0.98)
        elif is_vendor_col and type_label == "NPCVendor":
            score = max(score, 0.98)
        elif is_zone_col and type_label == "Zone":
            score = max(score, 0.98)
        elif is_precursor_col and type_label == "PrecursorWeapon":
            score = max(score, 0.95)

        if score >= 0.70:
            return uri, canonical_label, type_label, min(1.0, score)

    # Named entity fallback
    fallback_uri = str(GW2RES[f"entity/{slug}"])
    return fallback_uri, raw, "Item", 0.85


def annotate_table(
    headers: List[str],
    rows: List[List[str]],
    vector_index: Optional[VectorIndex] = None,
    reasoner: Optional[Any] = None,
) -> Tuple[List[ColumnAnnotation], List[CellAnnotation], List[ColumnPropertyAnnotation]]:
    """Runs CEA, CTA, and CPA on tabular data utilizing dense VectorIndex and semantic ontology axioms."""
    cta_list: List[ColumnAnnotation] = []
    cea_list: List[CellAnnotation] = []
    cpa_list: List[ColumnPropertyAnnotation] = []

    index = vector_index if vector_index is not None else get_default_vector_index()

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
        elif any(w in h_norm for w in ["zone", "loc", "place", "where"]):
            type_uri = str(CLASS_ZONE)
            type_label = "Zone"
            confidence = 0.95
        elif any(w in h_norm for w in ["vendor", "source", "npc", "who"]):
            type_uri = str(CLASS_NPC_VENDOR)
            type_label = "NPCVendor"
            confidence = 0.90
        elif any(w in h_norm for w in ["slot", "forgeslot"]):
            type_uri = str(CLASS_MYSTIC_FORGE_RECIPE)
            type_label = "MysticForgeRecipe"
            confidence = 0.95
        else:
            # Check vector index classes
            class_res = index.search_classes(h_norm or header, top_k=1)
            if class_res and class_res[0].score >= 0.75:
                top_cls = class_res[0]
                type_uri = top_cls.iri
                type_label = top_cls.label
                confidence = float(top_cls.score)

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
            matched = match_cell_entity(cell_val, headers[c_idx], vector_index=index)
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
