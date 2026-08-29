"""Unstructured text entity and relation extractor for GW2 guides."""

from __future__ import annotations
import re
import json
from typing import List, Dict, Any, Tuple, Optional
import rdflib
from rdflib import Graph, Literal, URIRef, RDF, RDFS, XSD

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
    PROP_REQUIRES_INGREDIENT,
    PROP_INGREDIENT_QUANTITY,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_LOCATED_IN_ZONE,
    PROP_PRECURSOR_TO,
)
from gw2_ume.ontology.schema import ENTITY_CATALOG, build_gw2_ontology_graph
from gw2_ume.ontology.shacl_rules import validate_mesh_shacl


class TextEntityRelationExtractor:
    """Extracts entities and relational triples from unstructured text guides."""

    def __init__(self):
        self.catalog = ENTITY_CATALOG

    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """Extracts entities and relation triples from text and builds an RDF graph."""
        text_lower = text.lower()
        extracted_entities = []
        seen_uris = set()

        # Step 1: Find all entity mentions from catalog aliases
        for key, entity in self.catalog.items():
            for alias in entity["aliases"]:
                # Match word boundary
                pattern = r"\b" + re.escape(alias) + r"\b"
                matches = list(re.finditer(pattern, text_lower))
                if matches:
                    uri_str = str(entity["uri"])
                    if uri_str not in seen_uris:
                        seen_uris.add(uri_str)
                        extracted_entities.append({
                            "key": key,
                            "label": entity["label"],
                            "uri": uri_str,
                            "type_label": entity["type_label"],
                            "matched_alias": alias,
                            "occurrences": len(matches),
                        })
                    break

        # Step 2: Build RDF Graph
        g = build_gw2_ontology_graph()
        for ent in extracted_entities:
            s = URIRef(ent["uri"])
            type_uri = URIRef(str(GW2[ent["type_label"]]))
            g.add((s, RDF.type, type_uri))
            g.add((s, RDFS.label, Literal(ent["label"], datatype=XSD.string)))

        # Step 3: Extract Relations using co-occurrence & domain knowledge
        triples_extracted = []

        # Connect Precursors (Ravenswood Branch -> Ravenswood Staff -> The Raven Spirit -> The Living Ravens)
        precursors = ["ravenswood_branch", "ravenswood_staff", "the_raven_spirit", "the_living_ravens"]
        present_precursors = [p for p in precursors if str(self.catalog[p]["uri"]) in seen_uris]
        for i in range(len(present_precursors) - 1):
            s_uri = str(self.catalog[present_precursors[i]]["uri"])
            t_uri = str(self.catalog[present_precursors[i + 1]]["uri"])
            g.add((URIRef(s_uri), PROP_PRECURSOR_TO, URIRef(t_uri)))
            triples_extracted.append((self.catalog[present_precursors[i]]["label"], "precursorTo", self.catalog[present_precursors[i + 1]]["label"]))

        # Connect Vendors to Zones
        vendors_in_text = [e for e in extracted_entities if e["type_label"] == "NPCVendor"]
        for v in vendors_in_text:
            v_key = v["key"]
            zone_name = self.catalog[v_key].get("zone")
            if zone_name:
                zone_slug = zone_name.lower().replace("'", "").replace(" ", "_")
                zone_uri = str(GW2RES[f"zone/{zone_slug}"])
                g.add((URIRef(v["uri"]), PROP_LOCATED_IN_ZONE, URIRef(zone_uri)))
                triples_extracted.append((v["label"], "locatedInZone", zone_name))

        # Connect Precursor / Components to Ingredients and Disciplines
        if "ravenswood_branch" in seen_uris or any(e["key"] == "ravenswood_branch" for e in extracted_entities):
            branch_uri = URIRef(str(self.catalog["ravenswood_branch"]["uri"]))
            # Ingredients mentioned in guide
            for ing_key in ["spiritwood_plank", "deldrimor_steel_ingot", "elonian_leather_square", "bolt_of_damask", "essence_of_the_raven"]:
                if any(e["key"] == ing_key for e in extracted_entities):
                    ing_uri = URIRef(str(self.catalog[ing_key]["uri"]))
                    g.add((branch_uri, PROP_REQUIRES_INGREDIENT, ing_uri))
                    triples_extracted.append(("Ravenswood Branch", "requiresIngredient", self.catalog[ing_key]["label"]))

        # Connect Mystic Forge Recipe
        if any(e["key"] == "nevermore" for e in extracted_entities):
            forge_recipe_uri = URIRef(str(GW2RES["recipe/nevermore_mystic_forge"]))
            g.add((forge_recipe_uri, RDF.type, GW2.MysticForgeRecipe))
            for ing_key in ["the_living_ravens", "gift_of_nevermore", "mystic_tribute", "gift_of_mastery"]:
                if any(e["key"] == ing_key for e in extracted_entities):
                    ing_uri = URIRef(str(self.catalog[ing_key]["uri"]))
                    g.add((forge_recipe_uri, PROP_REQUIRES_INGREDIENT, ing_uri))
                    triples_extracted.append(("Mystic Forge Nevermore", "requiresIngredient", self.catalog[ing_key]["label"]))

        # Serialize
        turtle_str = g.serialize(format="turtle")
        json_ld_str = g.serialize(format="json-ld")
        json_ld_dict = json.loads(json_ld_str) if json_ld_str else {}

        return {
            "entities_found": extracted_entities,
            "entity_count": len(extracted_entities),
            "triples": triples_extracted,
            "triple_count": len(triples_extracted),
            "turtle": turtle_str,
            "json_ld": json_ld_dict,
        }


__all__ = ["TextEntityRelationExtractor"]
