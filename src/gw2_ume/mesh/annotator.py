"""Table Annotator for Cell Entity Annotation (CEA), Column Type Annotation (CTA), and Column Property Annotation (CPA)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

from gw2_ume.mesh.models import CellAnnotation, ColumnAnnotation, ColumnPropertyAnnotation
from gw2_ume.ontology.namespaces import DEFAULT_PRIORY_PREFIXES
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
    CLASS_CURRENCY,
    CLASS_ATTRIBUTE_COMBINATION,
    CLASS_ATTRIBUTE,
    CLASS_EXPANSION_RELEASE,
    CLASS_ENTITY,
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
    PROP_REQUIRES_CURRENCY,
    PROP_COSTS_CURRENCY,
    PROP_HAS_ATTRIBUTE,
    PROP_HAS_PRIMARY_ATTRIBUTE,
    PROP_HAS_SECONDARY_ATTRIBUTE,
    PROP_HAS_ATTRIBUTE_COMBINATION,
    PROP_RELEASED_IN_EXPANSION,
    PROP_REWARD_FOR_STEP,
)
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner
from gw2_ume.retrieval.vector_index import VectorIndex, _lexical_similarity, get_default_vector_index


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
    # Common OCR/leetspeak normalizations
    text = text.replace("@", "a").replace("0", "o").replace("3", "e").replace("4", "a").replace("5", "s")
    text = text.replace("s1ot", "slot").replace("siot", "slot")
    text = re.sub(r"[#$%^&*_+=\[\]{};:<>?/\\|~]", " ", text)
    text = text.replace("1", "i")
    text = re.sub(r"q(?!u)", "g", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_cell_entity(
    cell_val: str,
    column_header: str = "",
    vector_index: Optional[VectorIndex] = None,
    reasoner: Optional[SymbolicAxiomReasoner] = None,
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
    try:
        float(raw)
        return None
    except ValueError:
        pass

    norm = normalize_text(raw)
    header_norm = normalize_text(column_header)

    if any(k in header_norm for k in ["qty", "quant", "cost", "count", "amount", "rating", "minrating", "level", "mass", "weight"]) and any(c.isdigit() for c in raw):
        return None

    slug = re.sub(r"[^\w\s-]", "", raw).strip().lower().replace(" ", "_")

    if any(w in header_norm for w in ["tier"]) or norm.startswith("tier"):
        return str(GW2RES[f"tier/{slug}"]), raw, "CollectionTier", 0.95

    if any(w in header_norm for w in ["step", "journey"]):
        return str(GW2RES[f"step/{slug}"]), raw, "CollectionStep", 0.95

    index = vector_index if vector_index is not None else get_default_vector_index()
    results = index.search_entities(raw, top_k=5)

    if results:
        top_cand = results[0]
        score = top_cand.score
        type_label = top_cand.metadata.get("type_label", top_cand.types[0] if top_cand.types else "Item")
        canonical_label = top_cand.metadata.get("canonical_label", top_cand.label)
        uri = top_cand.iri

        # Contextual boost if header semantic type aligns with candidate type
        if header_norm:
            cand_type_norm = type_label.lower()
            if any(w in header_norm for w in ["vendor", "npc", "merchant", "source"]) and ("vendor" in cand_type_norm or "npc" in cand_type_norm):
                score = max(score, 0.95)
            elif any(w in header_norm for w in ["discipline", "craft", "prof"]) and "discipline" in cand_type_norm:
                score = max(score, 0.95)
            elif any(w in header_norm for w in ["zone", "loc", "place", "where", "zn"]) and "zone" in cand_type_norm:
                score = max(score, 0.95)
            elif any(w in header_norm for w in ["precursor", "weapon"]) and "precursor" in cand_type_norm:
                score = max(score, 0.95)
            elif any(w in header_norm for w in ["currency", "token", "coin", "karma"]) and "currency" in cand_type_norm:
                score = max(score, 0.95)
            elif any(w in header_norm for w in ["attribute", "stat", "prefix"]) and ("attribute" in cand_type_norm or "combination" in cand_type_norm):
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
    reasoner: Optional[SymbolicAxiomReasoner] = None,
) -> Tuple[List[ColumnAnnotation], List[CellAnnotation], List[ColumnPropertyAnnotation]]:
    """Runs CEA, CTA, and CPA on tabular data utilizing dense VectorIndex, LCS reasoning, and semantic ontology axioms."""
    cta_list: List[ColumnAnnotation] = []
    cea_list: List[CellAnnotation] = []
    cpa_list: List[ColumnPropertyAnnotation] = []

    index = vector_index if vector_index is not None else get_default_vector_index()
    reasoner_inst = reasoner if reasoner is not None else SymbolicAxiomReasoner()

    # 1. CEA: Cell Entity Annotation (Tentative resolution for cell typing)
    col_cell_matches: Dict[int, List[Tuple[int, Tuple[str, str, str, float]]]] = {}
    for r_idx, row in enumerate(rows):
        for c_idx, cell_val in enumerate(row):
            if not cell_val.strip():
                continue
            header_name = headers[c_idx] if c_idx < len(headers) else ""
            matched = match_cell_entity(cell_val, header_name, vector_index=index, reasoner=reasoner_inst)
            if matched:
                uri, label, type_label, conf = matched
                cea_ann = CellAnnotation(
                    row_idx=r_idx,
                    col_idx=c_idx,
                    raw_value=cell_val,
                    entity_uri=uri,
                    label=label,
                    entity_type=type_label,
                    confidence=conf,
                )
                cea_list.append(cea_ann)
                col_cell_matches.setdefault(c_idx, []).append((r_idx, matched))

    # 2. CTA: Column Type Annotation using Least Common Subsumer (LCS) and Ontology Introspection
    for col_idx, header in enumerate(headers):
        h_norm = normalize_text(header)
        col_values = [rows[r][col_idx] for r in range(len(rows)) if col_idx < len(rows[r])]
        sample_vals = [v for v in col_values if v.strip()][:5]

        # Semantic column header introspection
        if any(w in h_norm for w in ["tier"]):
            type_uri = str(CLASS_COLLECTION_TIER)
            type_label = "CollectionTier"
            confidence = 0.95
        elif any(w in h_norm for w in ["step", "journey", "stepname", "collection"]):
            type_uri = str(CLASS_COLLECTION_STEP)
            type_label = "CollectionStep"
            confidence = 0.95
        elif any(w in h_norm for w in ["qty", "quant", "cost", "count", "amount", "mass", "weight"]):
            type_uri = str(CLASS_INGREDIENT_QUANTITY)
            type_label = "IngredientQuantity"
            confidence = 0.95
        elif any(w in h_norm for w in ["rating", "level", "skill", "minrating", "purity", "grade"]):
            type_uri = str(CLASS_DISCIPLINE_RATING)
            type_label = "DisciplineRating"
            confidence = 0.95
        elif any(w in h_norm for w in ["slot", "forgeslot", "forge_slot"]):
            type_uri = str(CLASS_MYSTIC_FORGE_RECIPE)
            type_label = "MysticForgeRecipe"
            confidence = 0.95
        elif any(w in h_norm for w in ["discipline", "craft", "prof"]):
            type_uri = str(CLASS_CRAFTING_DISCIPLINE)
            type_label = "CraftingDiscipline"
            confidence = 0.95
        elif any(w in h_norm for w in ["zone", "loc", "place", "where", "zn"]):
            type_uri = str(CLASS_ZONE)
            type_label = "Zone"
            confidence = 0.95
        elif any(w in h_norm for w in ["vendor", "source", "npc", "who", "supplier", "merchant"]) and not any(w in h_norm for w in ["zone", "zn"]):
            type_uri = str(CLASS_NPC_VENDOR)
            type_label = "NPCVendor"
            confidence = 0.95
        elif any(w in h_norm for w in ["hope", "bifrost", "nevermore", "astralaria", "precursor"]):
            type_uri = str(CLASS_PRECURSOR_WEAPON)
            type_label = "PrecursorWeapon"
            confidence = 0.95
        elif any(w in h_norm for w in ["prototype", "experimental", "component", "ingredient", "sub_ingredient", "subingredients", "sub_ingredients"]):
            type_uri = str(CLASS_COMPONENT_ITEM)
            type_label = "ComponentItem"
            confidence = 0.90
        elif any(w in h_norm for w in ["currency", "token"]):
            type_uri = str(CLASS_CURRENCY)
            type_label = "Currency"
            confidence = 0.95
        elif any(w in h_norm for w in ["attribute", "stat", "prefix"]):
            type_uri = str(CLASS_ATTRIBUTE_COMBINATION)
            type_label = "AttributeCombination"
            confidence = 0.95
        else:
            # Infer column type dynamically using Least Common Subsumer (LCS) of cell entities
            cell_types: List[str] = []
            matches = col_cell_matches.get(col_idx, [])
            for _, (_, _, t_label, _) in matches:
                if t_label:
                    cell_types.append(t_label)

            lcs_candidate = reasoner_inst.find_least_common_subsumer(cell_types) if cell_types else None
            if lcs_candidate and str(lcs_candidate) not in ("http://www.w3.org/2002/07/owl#Thing", "owl:Thing", str(CLASS_ITEM), str(CLASS_ENTITY)):
                lcs_uri_str = str(lcs_candidate)
                lcs_label = lcs_uri_str.split("#")[-1].split("/")[-1]
                if lcs_label == "MapZone":
                    lcs_label = "Zone"
                    lcs_uri_str = str(CLASS_ZONE)
                elif lcs_label == "Vendor":
                    lcs_label = "NPCVendor"
                    lcs_uri_str = str(CLASS_NPC_VENDOR)
                type_uri = lcs_uri_str
                type_label = lcs_label
                confidence = 0.92
            elif cell_types and any(t != "Item" for t in cell_types):
                non_item_types = [t for t in cell_types if t != "Item"]
                top_type_name = Counter(non_item_types).most_common(1)[0][0]
                if top_type_name == "MapZone":
                    top_type_name = "Zone"
                elif top_type_name == "Vendor":
                    top_type_name = "NPCVendor"
                resolved_t = reasoner_inst.loader.resolve_iri(top_type_name)
                type_uri = str(resolved_t)
                type_label = top_type_name
                confidence = 0.90
            else:
                header_class_cands = index.search_classes(h_norm or header, top_k=1) if header.strip() else []
                if header_class_cands and header_class_cands[0].score >= 0.70:
                    top_header_cls = header_class_cands[0]
                    type_uri = top_header_cls.iri
                    hdr_label = top_header_cls.label
                    if hdr_label == "MapZone":
                        hdr_label = "Zone"
                    elif hdr_label == "Vendor":
                        hdr_label = "NPCVendor"
                    type_label = hdr_label
                    confidence = float(top_header_cls.score)
                else:
                    type_uri = str(CLASS_ITEM)
                    type_label = "Item"
                    confidence = 0.85

        cta_list.append(ColumnAnnotation(
            col_idx=col_idx,
            col_name=header,
            type_uri=type_uri,
            type_label=type_label,
            confidence=confidence,
            sample_values=sample_vals,
        ))

    # 3. CPA: Column Property Annotation using Reasoner Domain/Range Axioms
    for i, c_src in enumerate(cta_list):
        for j, c_dst in enumerate(cta_list):
            if i == j:
                continue
            if not c_src.col_name.strip() or not c_dst.col_name.strip():
                continue

            prop_uri = None
            prop_label = None
            cpa_conf = 0.0

            is_src_item = (
                "item" in c_src.type_label.lower()
                or "weapon" in c_src.type_label.lower()
                or "component" in c_src.type_label.lower()
                or "material" in c_src.type_label.lower()
                or "tribute" in c_src.type_label.lower()
                or "gift" in c_src.type_label.lower()
                or c_src.type_label in ("Item", "PrecursorWeapon", "ComponentItem", "CraftingMaterial", "Weapon", "Armor", "Trinket", "LegendaryWeapon", "EquipableItem", "GiftItem", "TrophyItem", "GiftComponent", "AscendedMaterial")
            )
            is_dst_item = (
                "item" in c_dst.type_label.lower()
                or "weapon" in c_dst.type_label.lower()
                or "component" in c_dst.type_label.lower()
                or "material" in c_dst.type_label.lower()
                or "tribute" in c_dst.type_label.lower()
                or "gift" in c_dst.type_label.lower()
                or c_dst.type_label in ("Item", "PrecursorWeapon", "ComponentItem", "CraftingMaterial", "Weapon", "Armor", "Trinket", "LegendaryWeapon", "EquipableItem", "GiftItem", "TrophyItem", "GiftComponent", "AscendedMaterial")
            )
            is_src_vendor = "vendor" in c_src.type_label.lower() or c_src.type_label in ("NPCVendor", "Vendor")
            is_dst_vendor = "vendor" in c_dst.type_label.lower() or c_dst.type_label in ("NPCVendor", "Vendor")
            is_dst_zone = "zone" in c_dst.type_label.lower() or c_dst.type_label in ("Zone", "MapZone")
            is_dst_disc = "discipline" in c_dst.type_label.lower() or c_dst.type_label == "CraftingDiscipline"

            is_precursor_or_primary = (
                c_src.type_label in ("PrecursorWeapon", "LegendaryWeapon", "Item")
                or "precursor" in c_src.col_name.lower()
                or "item" in c_src.col_name.lower()
                or "hope" in c_src.col_name.lower()
                or "bifrost" in c_src.col_name.lower()
                or "ingred" in c_src.col_name.lower()
            )

            # Special Datatype and Structural Column Annotations
            if is_src_item and c_dst.type_label in ("IngredientQuantity", "Ingredient Quantity"):
                # Quantity is associated with the closest preceding component/item
                if c_src.col_idx < c_dst.col_idx and (c_dst.col_idx - c_src.col_idx <= 2):
                    prop_uri = str(PROP_INGREDIENT_QUANTITY)
                    prop_label = "ingredientQuantity"
                    cpa_conf = 0.95
            elif is_precursor_or_primary and is_dst_item and c_src.col_idx < c_dst.col_idx:
                prop_uri = str(PROP_REQUIRES_INGREDIENT)
                prop_label = "requiresIngredient"
                cpa_conf = 0.92
            elif is_precursor_or_primary and c_dst.type_label == "CollectionStep" and c_src.col_idx < c_dst.col_idx:
                prop_uri = str(PROP_REQUIRES_INGREDIENT)
                prop_label = "requiresIngredient"
                cpa_conf = 0.90
            elif is_precursor_or_primary and is_dst_disc:
                prop_uri = str(PROP_CRAFTED_BY_DISCIPLINE)
                prop_label = "craftedByDiscipline"
                cpa_conf = 0.95
            elif is_precursor_or_primary and is_dst_vendor:
                prop_uri = str(PROP_OBTAINED_FROM_VENDOR)
                prop_label = "obtainedFromVendor"
                cpa_conf = 0.92
            elif is_src_vendor and is_dst_zone:
                prop_uri = str(PROP_LOCATED_IN_ZONE)
                prop_label = "locatedInZone"
                cpa_conf = 0.98
            elif is_src_item and c_dst.type_label == "Currency":
                prop_uri = str(PROP_REQUIRES_CURRENCY)
                prop_label = "requiresCurrency"
                cpa_conf = 0.92
            else:
                # Dynamic Reasoner Domain/Range Axiom Discovery
                compatible_props = reasoner_inst.get_compatible_properties(c_src.type_uri, c_dst.type_uri)
                if compatible_props:
                    query_text = f"{c_src.col_name} {c_dst.col_name}".lower()
                    best_prop = compatible_props[0]
                    best_sim = -1.0
                    for p in compatible_props:
                        sim = max((_lexical_similarity(query_text, l) for l in [p.label or "", p.pref_label or ""]), default=0.0)
                        if sim > best_sim:
                            best_sim = sim
                            best_prop = p

                    prop_uri = str(best_prop.iri)
                    prop_label = best_prop.pref_label or best_prop.label or prop_uri.split("#")[-1].split("/")[-1]
                    cpa_conf = 0.92 if best_sim > 0.3 else 0.88

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
