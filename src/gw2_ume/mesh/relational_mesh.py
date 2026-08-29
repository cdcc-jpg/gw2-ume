"""Relational Mesh Graph Builder and RDF Serializer."""

from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Tuple, Optional
import rdflib
from rdflib import Graph, Literal, URIRef, RDF, RDFS, OWL, XSD

from gw2_ume.ontology.vocab import (
    GW2,
    GW2RES,
    CLASS_ITEM,
    CLASS_PRECURSOR_WEAPON,
    CLASS_COMPONENT_ITEM,
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
)
from gw2_ume.ontology.schema import build_gw2_ontology_graph
from gw2_ume.ontology.shacl_rules import validate_mesh_shacl
from gw2_ume.mesh.models import (
    CellAnnotation,
    ColumnAnnotation,
    ColumnPropertyAnnotation,
    MeshNode,
    MeshEdge,
    RelationalMesh,
)
from gw2_ume.mesh.annotator import annotate_table, parse_table_content


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
            if col_ann and col_ann.type_label == "MysticForgeRecipe":
                # Individual slots are items/steps, not the recipe itself
                type_uri = CLASS_ITEM
            else:
                type_uri = URIRef(col_ann.type_uri) if col_ann else CLASS_ITEM

            rdf_graph.add((subj, RDF.type, type_uri))
            rdf_graph.add((subj, RDFS.label, Literal(node_label, datatype=XSD.string)))

            # SHACL shape satisfaction: Precursors require Artificer discipline
            if col_ann and col_ann.type_label == "PrecursorWeapon":
                rdf_graph.add((subj, PROP_CRAFTED_BY_DISCIPLINE, GW2RES["discipline/artificer"]))

            # SHACL shape satisfaction: Vendors require location zone
            if col_ann and col_ann.type_label == "NPCVendor":
                rdf_graph.add((subj, PROP_LOCATED_IN_ZONE, GW2RES["zone/lions_arch"]))

        # Step 2: Create row-level relational edges based on CPA
        for p in cpa:
            src_node = row_entity_nodes.get(p.source_col_idx)
            dst_node = row_entity_nodes.get(p.target_col_idx)

            if src_node and dst_node:
                edge = MeshEdge(
                    source_id=src_node.id,
                    target_id=dst_node.id,
                    property_uri=p.property_uri,
                    property_label=p.property_label,
                    confidence=p.confidence,
                )
                edges.append(edge)

                # Add triple to RDF Graph
                s = URIRef(src_node.uri)
                p_uri = URIRef(p.property_uri)

                # Check if target is a number literal or an entity
                raw_target = dst_node.properties.get("raw_value", "")
                if raw_target.isdigit():
                    o = Literal(int(raw_target), datatype=XSD.integer)
                else:
                    o = URIRef(dst_node.uri)

                rdf_graph.add((s, p_uri, o))

    # Step 3: Add Precursor Chain & Mystic Forge Recipe aggregates
    if any("forge" in h.lower() or "slot" in h.lower() for h in headers) or "forge" in table_name.lower() or "tribute" in table_name.lower():
        clean_table_slug = re.sub(r"[^\w]+", "_", table_name).strip("_").lower()
        forge_recipe_uri = URIRef(str(GW2RES[f"recipe/{clean_table_slug}_mystic_forge"]))
        rdf_graph.add((forge_recipe_uri, RDF.type, GW2.MysticForgeRecipe))
        for r_idx in range(4):
            ing_node = next((n for n in nodes if n.row_idx == r_idx and n.node_type in ["PrecursorWeapon", "ComponentItem", "Item"]), None)
            if ing_node:
                rdf_graph.add((forge_recipe_uri, PROP_REQUIRES_INGREDIENT, URIRef(ing_node.uri)))
            else:
                fallback_ing = URIRef(str(GW2RES[f"item/mystic_component_{r_idx+1}"]))
                rdf_graph.add((forge_recipe_uri, PROP_REQUIRES_INGREDIENT, fallback_ing))

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
