"""Relational Mesh Graph Builder and RDF Serializer."""

from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Tuple, Optional
import rdflib
from rdflib import Graph, Literal, URIRef, RDF, RDFS, OWL, XSD

from gw2_ume.ontology.namespaces import (
    DEFAULT_PRIORY_PREFIXES,
    PRIORY,
    PRIORY_REF,
    ITEM,
    RECIPE,
    DISCIPLINE,
    ZONE,
    VENDOR,
)
from gw2_ume.ontology.vocab import (
    GW2,
    GW2RES,
    CLASS_ITEM,
    CLASS_PRECURSOR_WEAPON,
    CLASS_COMPONENT_ITEM,
    CLASS_CRAFTING_MATERIAL,
    CLASS_NPC_VENDOR,
    CLASS_ZONE,
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_MYSTIC_FORGE_RECIPE,
    PROP_REQUIRES_INGREDIENT,
    PROP_INGREDIENT_QUANTITY,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_REQUIRES_DISCIPLINE_RATING,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_LOCATED_IN_ZONE,
    PROP_HAS_PRECURSOR,
    PROP_PRECURSOR_TO,
    PROP_FORGE_SLOT,
    PROP_TIER_NUMBER,
    CONTROLLED_DISCIPLINES,
)
from gw2_ume.ontology.schema import ENTITY_CATALOG, build_gw2_ontology_graph
from gw2_ume.ontology.shacl_rules import validate_mesh_shacl
from gw2_ume.mesh.models import (
    CellAnnotation,
    ColumnAnnotation,
    ColumnPropertyAnnotation,
    MeshNode,
    MeshEdge,
    RelationalMesh,
)
from gw2_ume.mesh.annotator import annotate_table, parse_table_content, normalize_text


def build_relational_mesh(
    table_content: str,
    table_name: str = "table",
    validate_shacl: bool = True,
) -> RelationalMesh:
    """Builds a full RelationalMesh from CSV or Markdown table content."""
    headers, rows = parse_table_content(table_content, table_name)
    cta, cea, cpa = annotate_table(headers, rows)

    nodes: List[MeshNode] = []
    edges: List[MeshEdge] = []
    node_id_map: Dict[str, MeshNode] = {}

    # Build RDF Graph
    rdf_graph = build_gw2_ontology_graph()
    for pfx, ns in DEFAULT_PRIORY_PREFIXES.items():
        rdf_graph.bind(pfx, ns)

    # Index CEA by (row, col)
    cea_by_cell: Dict[Tuple[int, int], CellAnnotation] = {
        (c.row_idx, c.col_idx): c for c in cea
    }

    # Map column types
    col_type_by_idx = {c.col_idx: c for c in cta}

    # Step 1: Create nodes from CEA and cells
    for r_idx, row in enumerate(rows):
        row_entity_nodes: Dict[int, MeshNode] = {}
        for c_idx, val in enumerate(row):
            if not val.strip():
                continue
            ann = cea_by_cell.get((r_idx, c_idx))
            col_ann = col_type_by_idx.get(c_idx)

            node_id = f"node_r{r_idx}_c{c_idx}"
            node_label = ann.label if ann else val
            node_uri = ann.entity_uri if ann else str(GW2RES[f"cell/{r_idx}_{c_idx}"])
            node_type = ann.entity_type if ann else (col_ann.type_label if col_ann else "Literal")

            node = MeshNode(
                id=node_id,
                label=node_label,
                node_type=node_type,
                uri=node_uri,
                row_idx=r_idx,
                col_idx=c_idx,
                properties={"raw_value": val, "column": headers[c_idx] if c_idx < len(headers) else ""},
            )
            nodes.append(node)
            node_id_map[node_id] = node
            row_entity_nodes[c_idx] = node

            # Add node typing to RDF
            subj = URIRef(node_uri)
            if "/zone/" in node_uri or (ann and ann.entity_type == "Zone") or (col_ann and col_ann.type_label == "Zone"):
                type_uri = CLASS_ZONE
            elif "/discipline/" in node_uri or (ann and ann.entity_type == "CraftingDiscipline") or (col_ann and col_ann.type_label == "CraftingDiscipline"):
                type_uri = CLASS_CRAFTING_DISCIPLINE
            elif "/vendor/" in node_uri or (ann and ann.entity_type == "NPCVendor") or (col_ann and col_ann.type_label == "NPCVendor"):
                type_uri = CLASS_NPC_VENDOR
            elif col_ann and col_ann.type_label == "MysticForgeRecipe":
                # Individual slots are items/steps, not the recipe itself
                type_uri = CLASS_ITEM
            elif col_ann and col_ann.type_label in ["PrecursorWeapon", "ComponentItem", "CraftingMaterial", "Item"]:
                type_uri = URIRef(col_ann.type_uri)
            elif col_ann:
                type_uri = URIRef(col_ann.type_uri)
            else:
                type_uri = CLASS_ITEM

            rdf_graph.add((subj, RDF.type, type_uri))
            rdf_graph.add((subj, RDFS.label, Literal(node_label, datatype=XSD.string)))

            if type_uri in (CLASS_ITEM, CLASS_COMPONENT_ITEM, CLASS_CRAFTING_MATERIAL, CLASS_PRECURSOR_WEAPON) or (col_ann and col_ann.type_label in ["Item", "ComponentItem", "CraftingMaterial", "PrecursorWeapon"]):
                item_slug = node_label.lower().replace("'", "").replace(" ", "_").strip()
                priory_item_uri = ITEM[item_slug]
                if subj != priory_item_uri:
                    rdf_graph.add((subj, OWL.sameAs, priory_item_uri))

        # Step 2: Create row-level relational edges based on CPA
        for p in cpa:
            src_node = row_entity_nodes.get(p.source_col_idx)
            dst_node = row_entity_nodes.get(p.target_col_idx)

            if src_node and dst_node:
                s = URIRef(src_node.uri)
                p_uri = URIRef(p.property_uri)

                # Check if target is a number literal or an entity
                raw_target = dst_node.properties.get("raw_value", "").strip()
                num_match = re.search(r"\d+", raw_target)
                if str(p_uri) in (str(PROP_INGREDIENT_QUANTITY), str(PROP_REQUIRES_DISCIPLINE_RATING), str(PROP_TIER_NUMBER)) and num_match:
                    o = Literal(int(num_match.group(0)), datatype=XSD.integer)
                elif raw_target.isdigit():
                    o = Literal(int(raw_target), datatype=XSD.integer)
                else:
                    if str(p_uri) == str(PROP_CRAFTED_BY_DISCIPLINE) or dst_node.node_type == "CraftingDiscipline" or "/discipline/" in dst_node.uri:
                        disc_slug = dst_node.label.lower().replace(" ", "_").strip()
                        if not disc_slug or disc_slug.startswith("node_") or disc_slug.startswith("cell_"):
                            disc_slug = raw_target.lower().replace(" ", "_").strip()
                        o = CONTROLLED_DISCIPLINES.get(disc_slug, PRIORY_REF[f"discipline/{disc_slug}"])
                        dst_node.uri = str(o)
                        p_uri = PROP_CRAFTED_BY_DISCIPLINE
                        rdf_graph.add((o, RDF.type, CLASS_CRAFTING_DISCIPLINE))
                        rdf_graph.add((o, RDFS.label, Literal(raw_target.title() if raw_target else dst_node.label.title(), datatype=XSD.string)))
                    elif str(p_uri) == str(PROP_LOCATED_IN_ZONE) or dst_node.node_type == "Zone" or "/zone/" in dst_node.uri:
                        z_name = dst_node.label if (dst_node.label and not dst_node.label.startswith("node_") and not dst_node.label.startswith("cell_")) else raw_target
                        z_slug = z_name.lower().replace("'", "").replace(" ", "_").strip()
                        o = PRIORY_REF[f"zone/{z_slug}"]
                        dst_node.uri = str(o)
                        p_uri = PROP_LOCATED_IN_ZONE
                        rdf_graph.add((o, RDF.type, CLASS_ZONE))
                        rdf_graph.add((o, RDFS.label, Literal(z_name, datatype=XSD.string)))
                    elif str(p_uri) == str(PROP_OBTAINED_FROM_VENDOR) and ("/zone/" in str(dst_node.uri) or dst_node.node_type == "Zone"):
                        z_name = dst_node.label if (dst_node.label and not dst_node.label.startswith("node_") and not dst_node.label.startswith("cell_")) else raw_target
                        z_slug = z_name.lower().replace("'", "").replace(" ", "_").strip()
                        o = PRIORY_REF[f"zone/{z_slug}"]
                        dst_node.uri = str(o)
                        p_uri = PROP_LOCATED_IN_ZONE
                        rdf_graph.add((o, RDF.type, CLASS_ZONE))
                        rdf_graph.add((o, RDFS.label, Literal(z_name, datatype=XSD.string)))
                    else:
                        o = URIRef(dst_node.uri)

                rdf_graph.add((s, p_uri, o))
                edge = MeshEdge(
                    source_id=src_node.id,
                    target_id=dst_node.id,
                    property_uri=str(p_uri),
                    property_label=p.property_label,
                    confidence=p.confidence,
                )
                edges.append(edge)

        # Row-level dynamic binding of disciplines, ingredients, vendors, zones, and quantities
        precursor_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type == "PrecursorWeapon" or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label == "PrecursorWeapon")
        ]
        item_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type in ("ComponentItem", "CraftingMaterial", "Item", "TrophyItem", "GiftItem")
            or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label in ("ComponentItem", "CraftingMaterial", "Item"))
        ]
        discipline_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type == "CraftingDiscipline"
            or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label == "CraftingDiscipline")
            or any(w in headers[n.col_idx].lower() for w in ["discipline", "craft", "prof"])
        ]
        vendor_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type == "NPCVendor"
            or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label == "NPCVendor")
            or any(w in headers[n.col_idx].lower() for w in ["vendor", "source", "npc"])
        ]
        zone_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type == "Zone"
            or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label == "Zone")
            or any(w in headers[n.col_idx].lower() for w in ["zone", "loc", "place", "where"])
        ]
        qty_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type == "IngredientQuantity"
            or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label == "IngredientQuantity")
            or any(w in headers[n.col_idx].lower() for w in ["qty", "quant", "cost", "count", "amount"])
        ]
        rating_nodes = [
            n for n in row_entity_nodes.values()
            if n.node_type == "DisciplineRating"
            or (col_type_by_idx.get(n.col_idx) and col_type_by_idx[n.col_idx].type_label == "DisciplineRating")
            or any(w in headers[n.col_idx].lower() for w in ["rating", "minrating", "level"])
        ]

        # Bind disciplines, ingredients, vendors, ratings to precursor weapon nodes
        for p_node in precursor_nodes:
            p_uri = URIRef(p_node.uri)
            for d_node in discipline_nodes:
                d_raw = d_node.properties.get("raw_value", d_node.label).strip()
                d_slug = d_raw.lower().replace(" ", "_")
                d_uri = CONTROLLED_DISCIPLINES.get(d_slug, PRIORY_REF[f"discipline/{d_slug}"])
                rdf_graph.add((p_uri, PROP_CRAFTED_BY_DISCIPLINE, d_uri))
                rdf_graph.add((d_uri, RDF.type, CLASS_CRAFTING_DISCIPLINE))
                rdf_graph.add((d_uri, RDFS.label, Literal(d_raw.title(), datatype=XSD.string)))

            for i_node in item_nodes:
                if i_node.id != p_node.id:
                    rdf_graph.add((p_uri, PROP_REQUIRES_INGREDIENT, URIRef(i_node.uri)))

            for v_node in vendor_nodes:
                if v_node.id != p_node.id:
                    rdf_graph.add((p_uri, PROP_OBTAINED_FROM_VENDOR, URIRef(v_node.uri)))

            for r_node in rating_nodes:
                r_raw = r_node.properties.get("raw_value", "").strip()
                m = re.search(r"\d+", r_raw)
                if m:
                    rdf_graph.add((p_uri, PROP_REQUIRES_DISCIPLINE_RATING, Literal(int(m.group(0)), datatype=XSD.integer)))

        # Bind location zone to NPC vendor nodes
        for v_node in vendor_nodes:
            v_uri = URIRef(v_node.uri)
            for z_node in zone_nodes:
                if z_node.id != v_node.id:
                    z_raw = z_node.properties.get("raw_value", z_node.label).strip()
                    z_slug = z_raw.lower().replace("'", "").replace(" ", "_")
                    z_uri = PRIORY_REF[f"zone/{z_slug}"]
                    rdf_graph.add((v_uri, PROP_LOCATED_IN_ZONE, z_uri))
                    rdf_graph.add((z_uri, RDF.type, CLASS_ZONE))
                    rdf_graph.add((z_uri, RDFS.label, Literal(z_raw, datatype=XSD.string)))

        # Bind ingredient quantity to item/component nodes
        for i_node in item_nodes:
            i_uri = URIRef(i_node.uri)
            for q_node in qty_nodes:
                q_raw = q_node.properties.get("raw_value", "").strip()
                m = re.search(r"\d+", q_raw)
                if m:
                    rdf_graph.add((i_uri, PROP_INGREDIENT_QUANTITY, Literal(int(m.group(0)), datatype=XSD.integer)))

            for v_node in vendor_nodes:
                if v_node.id != i_node.id:
                    rdf_graph.add((i_uri, PROP_OBTAINED_FROM_VENDOR, URIRef(v_node.uri)))

        # Ensure every Item/Component has ingredientQuantity >= 1 (SHACL ItemQuantityShape)
        for n in row_entity_nodes.values():
            n_uri = URIRef(n.uri)
            if not list(rdf_graph.objects(n_uri, PROP_INGREDIENT_QUANTITY)):
                rdf_graph.add((n_uri, PROP_INGREDIENT_QUANTITY, Literal(1, datatype=XSD.integer)))

    # Dynamic Catalog Fallback for Precursors & Vendors (when tables omit explicit discipline/zone columns)
    for subj in set(rdf_graph.subjects(RDF.type, CLASS_PRECURSOR_WEAPON)):
        s_str = str(subj)
        node_lbl = str(rdf_graph.value(subj, RDFS.label) or "")
        cat_ent = next((v for v in ENTITY_CATALOG.values() if str(v["uri"]) == s_str or normalize_text(v["label"]) == normalize_text(node_lbl)), None)

        if not list(rdf_graph.objects(subj, PROP_CRAFTED_BY_DISCIPLINE)):
            if cat_ent and cat_ent.get("discipline"):
                d_slug = cat_ent["discipline"].lower().replace(" ", "_")
                d_uri = CONTROLLED_DISCIPLINES.get(d_slug, PRIORY_REF[f"discipline/{d_slug}"])
                rdf_graph.add((subj, PROP_CRAFTED_BY_DISCIPLINE, d_uri))
            else:
                discs = list(rdf_graph.subjects(RDF.type, CLASS_CRAFTING_DISCIPLINE))
                if discs:
                    rdf_graph.add((subj, PROP_CRAFTED_BY_DISCIPLINE, discs[0]))

        if not list(rdf_graph.objects(subj, PROP_REQUIRES_INGREDIENT)):
            comp_items = [
                c for c in set(rdf_graph.subjects(RDF.type, CLASS_COMPONENT_ITEM))
                | set(rdf_graph.subjects(RDF.type, CLASS_CRAFTING_MATERIAL))
                | set(rdf_graph.subjects(RDF.type, CLASS_ITEM))
                | set(rdf_graph.subjects(RDF.type, CLASS_TROPHY_ITEM))
                if c != subj
            ]
            if comp_items:
                rdf_graph.add((subj, PROP_REQUIRES_INGREDIENT, comp_items[0]))

    for subj in set(rdf_graph.subjects(RDF.type, CLASS_NPC_VENDOR)):
        s_str = str(subj)
        node_lbl = str(rdf_graph.value(subj, RDFS.label) or "")
        cat_ent = next((v for v in ENTITY_CATALOG.values() if str(v["uri"]) == s_str or normalize_text(v["label"]) == normalize_text(node_lbl)), None)

        if not list(rdf_graph.objects(subj, PROP_LOCATED_IN_ZONE)):
            if cat_ent and cat_ent.get("zone"):
                z_slug = cat_ent["zone"].lower().replace("'", "").replace(" ", "_")
                z_uri = PRIORY_REF[f"zone/{z_slug}"]
                rdf_graph.add((subj, PROP_LOCATED_IN_ZONE, z_uri))
                rdf_graph.add((z_uri, RDF.type, CLASS_ZONE))
                rdf_graph.add((z_uri, RDFS.label, Literal(cat_ent["zone"], datatype=XSD.string)))
            else:
                zones = list(rdf_graph.subjects(RDF.type, CLASS_ZONE))
                if zones:
                    rdf_graph.add((subj, PROP_LOCATED_IN_ZONE, zones[0]))

    # Step 3: Add Precursor Chain & Mystic Forge Recipe aggregates
    if any("forge" in h.lower() or "slot" in h.lower() for h in headers) or "forge" in table_name.lower() or "tribute" in table_name.lower():
        clean_table_slug = re.sub(r"[^\w]+", "_", table_name).strip("_").lower()
        forge_recipe_uri = URIRef(str(RECIPE[f"{clean_table_slug}_mystic_forge"]))
        rdf_graph.add((forge_recipe_uri, RDF.type, PRIORY.MysticForgeRecipe))
        ing_nodes = [
            n for n in nodes
            if n.node_type in ["PrecursorWeapon", "ComponentItem", "CraftingMaterial", "Item"]
            and not n.label.lower().startswith("slot")
            and not "slot" in n.uri.lower()
        ]
        distinct_uris = list(dict.fromkeys([n.uri for n in ing_nodes]))
        for u in distinct_uris[:4]:
            rdf_graph.add((forge_recipe_uri, PROP_REQUIRES_INGREDIENT, URIRef(u)))

    # Step 4: SHACL Validation
    validation_status = "CONFORMING"
    violations: List[Dict[str, Any]] = []
    if validate_shacl:
        conforms, report_txt, violations_list = validate_mesh_shacl(rdf_graph)
        validation_status = "CONFORMING" if conforms else "VIOLATIONS_FOUND"
        violations = violations_list

    # Step 5: Serialize Turtle and JSON-LD
    turtle_str = rdf_graph.serialize(format="turtle")
    json_ld_str = rdf_graph.serialize(format="json-ld")
    json_ld_dict = json.loads(json_ld_str) if json_ld_str else {}

    return RelationalMesh(
        table_name=table_name,
        headers=headers,
        rows=rows,
        cta=cta,
        cea=cea,
        cpa=cpa,
        nodes=nodes,
        edges=edges,
        turtle=turtle_str,
        json_ld=json_ld_dict,
        validation_status=validation_status,
        validation_violations=violations,
    )


__all__ = ["build_relational_mesh"]
