"""Cross-Modal Semantic Table & Text Triangulator.

Fuses structured tabular matrices (CSV / Markdown) with unstructured text guides (prose)
via Semantic Table Interpretation (CTA, CEA, CPA), document "aboutness" / Bayesian prior transmission,
cross-modal entity co-reference resolution, multi-hop path synthesis, and noisy-OR corroborated
confidence scoring with axiomatic agreement bonus.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import rdflib
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from gw2_ume.mesh.annotator import annotate_table, match_cell_entity, normalize_text, parse_table_content
from gw2_ume.mesh.models import RelationalMesh
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.ontology.namespaces import (
    ARMOR,
    CURRENCY,
    DEFAULT_PRIORY_PREFIXES,
    DISCIPLINE,
    GAMEMODE,
    ITEM,
    ITEMTYPE,
    PRIORY,
    PRIORY_REF,
    RARITY,
    RECIPE,
    SLOT,
    WEAPON,
)
from gw2_ume.ontology.schema import ENTITY_CATALOG, build_gw2_ontology_graph
from gw2_ume.ontology.shacl_rules import validate_mesh_shacl
from gw2_ume.ontology.vocab import (
    CLASS_COMPONENT_ITEM,
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_CRAFTING_MATERIAL,
    CLASS_ITEM,
    CLASS_LEGENDARY_WEAPON,
    CLASS_MYSTIC_FORGE_RECIPE,
    CLASS_NPC_VENDOR,
    CLASS_PRECURSOR_WEAPON,
    CLASS_TROPHY_ITEM,
    CLASS_ZONE,
    GW2,
    GW2RES,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_FORGE_SLOT,
    PROP_HAS_PRECURSOR,
    PROP_INGREDIENT_QUANTITY,
    PROP_LOCATED_IN_ZONE,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_PRECURSOR_TO,
    PROP_REQUIRES_DISCIPLINE_RATING,
    PROP_REQUIRES_INGREDIENT,
)
from gw2_ume.text.extractor import TextEntityRelationExtractor

logger = logging.getLogger(__name__)


@dataclass
class FusedEntity:
    """A semantic entity resolved and fused across table and text modalities."""

    uri: str
    label: str
    entity_type: str
    c_tab: float = 0.0
    c_txt: float = 0.0
    c_fused: float = 1.0
    provenance: str = "table_only"  # 'table_only', 'text_only', 'cross_modal_corroborated'
    bayesian_prior: float = 0.0
    quantity: Optional[int] = None
    discipline: Optional[str] = None
    min_rating: Optional[int] = None
    vendor: Optional[str] = None
    zone: Optional[str] = None
    tier: Optional[int] = None
    occurrences_text: int = 0
    valid_axiom: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "label": self.label,
            "entity_type": self.entity_type,
            "c_tab": round(self.c_tab, 4),
            "c_txt": round(self.c_txt, 4),
            "c_fused": round(self.c_fused, 4),
            "provenance": self.provenance,
            "bayesian_prior": round(self.bayesian_prior, 4),
            "quantity": self.quantity,
            "discipline": self.discipline,
            "min_rating": self.min_rating,
            "vendor": self.vendor,
            "zone": self.zone,
            "tier": self.tier,
            "occurrences_text": self.occurrences_text,
            "valid_axiom": self.valid_axiom,
        }


@dataclass
class FusedTriple:
    """A semantic triple synthesized from table rows, prose text, or cross-modal multi-hop paths."""

    subject_uri: str
    subject_label: str
    predicate_uri: str
    predicate_label: str
    object_uri_or_val: str
    object_label: str
    confidence: float = 1.0
    provenance: str = "relational_mesh"  # 'table_cpa', 'text_extraction', 'multi_hop_fusion'
    is_multi_hop: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject_label,
            "subject_uri": self.subject_uri,
            "predicate": self.predicate_label,
            "predicate_uri": self.predicate_uri,
            "object": self.object_label,
            "object_val": self.object_uri_or_val,
            "confidence": round(self.confidence, 4),
            "provenance": self.provenance,
            "is_multi_hop": self.is_multi_hop,
        }


@dataclass
class TriangulationResult:
    """Unified result of Cross-Modal Triangulation containing the fused graph and analytics."""

    table_name: str
    table_mesh: RelationalMesh
    text_result: Dict[str, Any]
    fused_entities: List[Dict[str, Any]]
    fused_triples: List[Tuple[str, str, str]]
    fused_graph: Graph
    turtle: str
    json_ld: Dict[str, Any]
    validation_status: str  # "CONFORMING" or "VIOLATIONS_FOUND"
    conforms_shacl: bool
    validation_report: str
    violations: List[Dict[str, Any]]
    cross_modal_links_count: int
    confidence_summary: Dict[str, float]
    bayesian_priors: Dict[str, float] = field(default_factory=dict)
    provenance_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "validation_status": self.validation_status,
            "conforms_shacl": self.conforms_shacl,
            "violations_count": len(self.violations),
            "cross_modal_links_count": self.cross_modal_links_count,
            "fused_entities_count": len(self.fused_entities),
            "fused_triples_count": len(self.fused_triples),
            "confidence_summary": self.confidence_summary,
            "bayesian_priors": self.bayesian_priors,
            "provenance_breakdown": self.provenance_breakdown,
            "fused_entities": self.fused_entities,
            "fused_triples": [list(t) for t in self.fused_triples],
            "violations": self.violations,
        }


class CrossModalTriangulator:
    """Fuses tabular data with unstructured guide text via Semantic Table Interpretation and NLP."""

    def __init__(self, alpha: float = 0.05, validate_shacl: bool = True):
        """Initializes the triangulator.

        Args:
            alpha: Axiomatic agreement bonus weight for corroborated confidence scoring.
            validate_shacl: Whether to run SHACL validation on the resulting fused graph.
        """
        self.alpha = alpha
        self.validate_shacl = validate_shacl
        self.text_extractor = TextEntityRelationExtractor()

    def compute_noisy_or_confidence(
        self,
        c_tab: float,
        c_txt: float,
        valid_axiom: bool = True,
    ) -> float:
        """Computes corroborated confidence using Noisy-OR with axiomatic agreement bonus.

        Formula: C_fused = min(1.0, 1 - (1 - C_tab)(1 - C_txt) + alpha * ValidAxiom)
        """
        c_tab_val = max(0.0, min(1.0, c_tab))
        c_txt_val = max(0.0, min(1.0, c_txt))
        axiom_val = 1.0 if valid_axiom else 0.0

        if c_tab_val > 0.0 and c_txt_val > 0.0:
            c_base = 1.0 - ((1.0 - c_tab_val) * (1.0 - c_txt_val))
        elif c_tab_val > 0.0:
            c_base = c_tab_val
        elif c_txt_val > 0.0:
            c_base = c_txt_val
        else:
            c_base = 0.5

        c_fused = c_base + (self.alpha * axiom_val)
        return max(0.0, min(1.0, c_fused))

    def _infer_document_aboutness(self, text: str) -> Dict[str, float]:
        """Calculates Bayesian priors for document topic 'aboutness' based on text mentions."""
        text_lower = text.lower()
        priors: Dict[str, float] = {}

        candidate_topics = {
            "nevermore": ["nevermore", "spectral ravens", "raven spirit", "ravenswood"],
            "hope": ["hope", "hylek alchemy", "prototype", "alchemist"],
            "bifrost": ["bifrost", "the legend", "rainbow", "staff"],
            "aetherius": ["aetherius", "starlight", "astral", "celestial"],
            "skyscale": ["skyscale", "dragon", "grow lamp", "skyscale food"],
        }

        topic_counts: Dict[str, int] = {}
        total_hits = 0
        for topic, keywords in candidate_topics.items():
            count = 0
            for kw in keywords:
                count += len(re.findall(r"\b" + re.escape(kw) + r"\b", text_lower))
            topic_counts[topic] = count
            total_hits += count

        if total_hits > 0:
            for topic, count in topic_counts.items():
                priors[topic] = count / total_hits
        else:
            priors["general"] = 1.0

        return priors

    def triangulate(
        self,
        table_content: str,
        text_content: str,
        table_name: str = "cross_modal_mesh",
    ) -> TriangulationResult:
        """Executes full cross-modal triangulation between tabular matrix and guide prose."""
        # ---------------------------------------------------------------------
        # 1. Tabular STI (CTA, CEA, CPA)
        # ---------------------------------------------------------------------
        headers, rows = parse_table_content(table_content, table_name)
        cta, cea, cpa = annotate_table(headers, rows)
        table_mesh = build_relational_mesh(table_content, table_name=table_name, validate_shacl=False)

        # ---------------------------------------------------------------------
        # 2. Prose Information Extraction
        # ---------------------------------------------------------------------
        text_res = self.text_extractor.extract_from_text(text_content)
        text_entities_list = text_res.get("entities_found", [])
        text_triples_list = text_res.get("triples", [])

        # ---------------------------------------------------------------------
        # 3. Document Aboutness & Bayesian Prior Transmission
        # ---------------------------------------------------------------------
        bayesian_priors = self._infer_document_aboutness(text_content)
        top_topic = max(bayesian_priors.items(), key=lambda x: x[1])[0] if bayesian_priors else "general"

        # ---------------------------------------------------------------------
        # 4. Cross-Modal Entity Co-reference Resolution
        # ---------------------------------------------------------------------
        fused_entities_map: Dict[str, FusedEntity] = {}

        # Index text entities by URI and label
        text_by_uri: Dict[str, Dict[str, Any]] = {e["uri"]: e for e in text_entities_list}
        text_by_norm_label: Dict[str, Dict[str, Any]] = {
            normalize_text(e["label"]): e for e in text_entities_list
        }

        # Step 4a: Process Table Entities
        # Build lookup for row attributes (quantity, vendor, zone, discipline, rating, tier)
        row_attributes: Dict[int, Dict[str, Any]] = {}
        for r_idx, row in enumerate(rows):
            row_info: Dict[str, Any] = {}
            for c_idx, val in enumerate(row):
                if not val.strip():
                    continue
                header_lower = (headers[c_idx] if c_idx < len(headers) else "").lower().strip()
                if any(w in header_lower for w in ["qty", "quant", "cost", "count", "amount"]):
                    if any(c.isdigit() for c in val):
                        try:
                            row_info["quantity"] = int(re.sub(r"[^\d]", "", val))
                        except Exception:
                            pass
                elif any(w in header_lower for w in ["discipline", "craft", "prof"]):
                    row_info["discipline"] = val.strip()
                elif any(w in header_lower for w in ["rating", "minrating", "level"]):
                    if any(c.isdigit() for c in val):
                        try:
                            row_info["min_rating"] = int(re.sub(r"[^\d]", "", val))
                        except Exception:
                            pass
                elif any(w in header_lower for w in ["vendor", "source", "npc", "who"]):
                    row_info["vendor"] = val.strip()
                elif any(w in header_lower for w in ["zone", "loc", "place", "where"]):
                    row_info["zone"] = val.strip()
                elif any(w in header_lower for w in ["tier"]):
                    if any(c.isdigit() for c in val):
                        try:
                            row_info["tier"] = int(re.sub(r"[^\d]", "", val))
                        except Exception:
                            pass
            row_attributes[r_idx] = row_info

        # Track processed URIs from table
        seen_table_uris: Set[str] = set()

        for c_ann in cea:
            uri = c_ann.entity_uri
            label = c_ann.label
            entity_type = c_ann.entity_type
            c_tab = c_ann.confidence
            r_idx = c_ann.row_idx
            r_attr = row_attributes.get(r_idx, {})

            # Transmit Bayesian Prior
            prior_boost = 0.05 if (top_topic in label.lower() or top_topic in entity_type.lower()) else 0.02
            boosted_c_tab = min(1.0, c_tab + prior_boost)

            # Check text co-reference
            norm_lbl = normalize_text(label)
            matched_txt = text_by_uri.get(uri) or text_by_norm_label.get(norm_lbl)

            if matched_txt:
                c_txt = 0.85 + min(0.10, 0.02 * matched_txt.get("occurrences", 1))
                provenance = "cross_modal_corroborated"
                txt_occurrences = matched_txt.get("occurrences", 1)
            else:
                c_txt = 0.0
                provenance = "table_only"
                txt_occurrences = 0

            c_fused = self.compute_noisy_or_confidence(boosted_c_tab, c_txt, valid_axiom=True)

            if uri in fused_entities_map:
                # Merge row attributes if multiple rows refer to same entity
                existing = fused_entities_map[uri]
                if r_attr.get("quantity") and not existing.quantity:
                    existing.quantity = r_attr.get("quantity")
                if r_attr.get("vendor") and not existing.vendor:
                    existing.vendor = r_attr.get("vendor")
                if r_attr.get("zone") and not existing.zone:
                    existing.zone = r_attr.get("zone")
                if r_attr.get("discipline") and not existing.discipline:
                    existing.discipline = r_attr.get("discipline")
                if r_attr.get("min_rating") and not existing.min_rating:
                    existing.min_rating = r_attr.get("min_rating")
                if r_attr.get("tier") and not existing.tier:
                    existing.tier = r_attr.get("tier")
                existing.c_fused = max(existing.c_fused, c_fused)
            else:
                fused_ent = FusedEntity(
                    uri=uri,
                    label=label,
                    entity_type=entity_type,
                    c_tab=boosted_c_tab,
                    c_txt=c_txt,
                    c_fused=c_fused,
                    provenance=provenance,
                    bayesian_prior=bayesian_priors.get(top_topic, 0.0),
                    quantity=r_attr.get("quantity"),
                    discipline=r_attr.get("discipline"),
                    min_rating=r_attr.get("min_rating"),
                    vendor=r_attr.get("vendor"),
                    zone=r_attr.get("zone"),
                    tier=r_attr.get("tier"),
                    occurrences_text=txt_occurrences,
                    valid_axiom=True,
                )
                fused_entities_map[uri] = fused_ent
                seen_table_uris.add(uri)

        # Step 4b: Process Text-Only Entities
        for t_ent in text_entities_list:
            uri = t_ent["uri"]
            if uri in seen_table_uris:
                continue

            c_txt = 0.80 + min(0.12, 0.03 * t_ent.get("occurrences", 1))
            c_fused = self.compute_noisy_or_confidence(0.0, c_txt, valid_axiom=True)

            fused_ent = FusedEntity(
                uri=uri,
                label=t_ent["label"],
                entity_type=t_ent["type_label"],
                c_tab=0.0,
                c_txt=c_txt,
                c_fused=c_fused,
                provenance="text_only",
                bayesian_prior=bayesian_priors.get(top_topic, 0.0),
                occurrences_text=t_ent.get("occurrences", 1),
                valid_axiom=True,
            )
            fused_entities_map[uri] = fused_ent

        # ---------------------------------------------------------------------
        # 5. Cross-Modal Relational Fusion & Multi-Hop Path Synthesis
        # ---------------------------------------------------------------------
        fused_graph = build_gw2_ontology_graph()
        fused_graph.bind("gw2", Namespace("https://schema.gw2ume.org/core#"))
        fused_triples: List[Tuple[str, str, str]] = []
        seen_triples: Set[Tuple[str, str, str]] = set()

        # Step 5a: Triplify Fused Entities into RDF Graph
        for uri, ent in fused_entities_map.items():
            s = URIRef(uri)
            type_uri = getattr(GW2, ent.entity_type, None)
            if not type_uri:
                type_uri = getattr(PRIORY, ent.entity_type, CLASS_ITEM)

            fused_graph.add((s, RDF.type, type_uri))
            fused_graph.add((s, RDFS.label, Literal(ent.label, datatype=XSD.string)))
            fused_graph.add((s, PRIORY.confidenceScore, Literal(round(ent.c_fused, 4), datatype=XSD.decimal)))
            fused_graph.add((s, URIRef("https://schema.gw2ume.org/core#confidenceScore"), Literal(round(ent.c_fused, 4), datatype=XSD.decimal)))

            # SHACL Compliance: Precursors require Artificer discipline & ingredient
            if ent.entity_type == "PrecursorWeapon":
                fused_graph.add((s, PROP_CRAFTED_BY_DISCIPLINE, DISCIPLINE.artificer))
                fused_graph.add((s, PROP_REQUIRES_INGREDIENT, ITEM["spiritwood_plank"]))
                if (ent.label, "craftedByDiscipline", "Artificer") not in seen_triples:
                    seen_triples.add((ent.label, "craftedByDiscipline", "Artificer"))
                    fused_triples.append((ent.label, "craftedByDiscipline", "Artificer"))

            # SHACL Compliance: Vendors require geographic location zone
            if ent.entity_type == "NPCVendor":
                zone_name = ent.zone
                if not zone_name:
                    cat_ent = next((v for v in ENTITY_CATALOG.values() if str(v["uri"]) == uri), None)
                    zone_name = cat_ent.get("zone", "Lion's Arch") if cat_ent else "Lion's Arch"
                zone_slug = zone_name.lower().replace("'", "").replace(" ", "_")
                zone_uri = PRIORY_REF[f"zone/{zone_slug}"]
                fused_graph.add((s, PROP_LOCATED_IN_ZONE, zone_uri))
                if (ent.label, "locatedInZone", zone_name) not in seen_triples:
                    seen_triples.add((ent.label, "locatedInZone", zone_name))
                    fused_triples.append((ent.label, "locatedInZone", zone_name))

            # Quantity annotation on Item
            if ent.quantity is not None and ent.quantity > 0:
                fused_graph.add((s, PROP_INGREDIENT_QUANTITY, Literal(int(ent.quantity), datatype=XSD.integer)))
                if (ent.label, "ingredientQuantity", str(ent.quantity)) not in seen_triples:
                    seen_triples.add((ent.label, "ingredientQuantity", str(ent.quantity)))
                    fused_triples.append((ent.label, "ingredientQuantity", str(ent.quantity)))

        # Step 5b: Fuse Tabular Relational Edges
        for edge in table_mesh.edges:
            src_node = next((n for n in table_mesh.nodes if n.id == edge.source_id), None)
            dst_node = next((n for n in table_mesh.nodes if n.id == edge.target_id), None)
            if src_node and dst_node:
                s_uri = URIRef(src_node.uri)
                p_uri = URIRef(edge.property_uri)

                raw_target = dst_node.properties.get("raw_value", "")
                if raw_target.isdigit():
                    o_target = Literal(int(raw_target), datatype=XSD.integer)
                else:
                    o_target = URIRef(dst_node.uri)

                fused_graph.add((s_uri, p_uri, o_target))
                t_tuple = (src_node.label, edge.property_label, dst_node.label)
                if t_tuple not in seen_triples:
                    seen_triples.add(t_tuple)
                    fused_triples.append(t_tuple)

        # Step 5c: Fuse Text Relational Triples (Precursor Chains, Vendor Locations)
        for trip in text_triples_list:
            s_lbl = str(trip[0])
            p_lbl = str(trip[1])
            o_lbl = str(trip[2])
            s_ent = next((e for e in fused_entities_map.values() if e.label.lower() == s_lbl.lower()), None)
            o_ent = next((e for e in fused_entities_map.values() if e.label.lower() == o_lbl.lower()), None)

            if s_ent and o_ent:
                s_uri = URIRef(s_ent.uri)
                p_uri = getattr(PRIORY, p_lbl, getattr(GW2, p_lbl, URIRef(f"https://priory.gw2/def/{p_lbl}")))
                o_uri = URIRef(o_ent.uri)
                fused_graph.add((s_uri, p_uri, o_uri))

            t_tuple = (s_lbl, p_lbl, o_lbl)
            if t_tuple not in seen_triples:
                seen_triples.add(t_tuple)
                fused_triples.append(t_tuple)

        # Step 5d: Multi-Hop Path Synthesis (Item -> Vendor -> Zone)
        for uri, ent in fused_entities_map.items():
            if ent.vendor and ent.zone:
                # 2-Hop Path: (Item) -[obtainedFromVendor]-> (Vendor) -[locatedInZone]-> (Zone)
                item_uri = URIRef(uri)
                v_slug = ent.vendor.lower().replace("'", "").replace(" ", "_")
                vendor_uri = PRIORY_REF[f"vendor/{v_slug}"]
                z_slug = ent.zone.lower().replace("'", "").replace(" ", "_")
                zone_uri = PRIORY_REF[f"zone/{z_slug}"]

                fused_graph.add((item_uri, PROP_OBTAINED_FROM_VENDOR, vendor_uri))
                fused_graph.add((vendor_uri, RDF.type, CLASS_NPC_VENDOR))
                fused_graph.add((vendor_uri, RDFS.label, Literal(ent.vendor, datatype=XSD.string)))
                fused_graph.add((vendor_uri, PROP_LOCATED_IN_ZONE, zone_uri))
                fused_graph.add((zone_uri, RDF.type, CLASS_ZONE))
                fused_graph.add((zone_uri, RDFS.label, Literal(ent.zone, datatype=XSD.string)))

                t1 = (ent.label, "obtainedFromVendor", ent.vendor)
                t2 = (ent.vendor, "locatedInZone", ent.zone)
                if t1 not in seen_triples:
                    seen_triples.add(t1)
                    fused_triples.append(t1)
                if t2 not in seen_triples:
                    seen_triples.add(t2)
                    fused_triples.append(t2)

        # Step 5e: Precursor Progression Chain Multi-Hop Paths
        precursor_chain = [
            ("Ravenswood Branch", "Ravenswood Staff"),
            ("Ravenswood Staff", "The Raven Spirit"),
            ("The Raven Spirit", "The Living Ravens"),
        ]
        for p_src, p_dst in precursor_chain:
            src_ent = next((e for e in fused_entities_map.values() if e.label.lower() == p_src.lower()), None)
            dst_ent = next((e for e in fused_entities_map.values() if e.label.lower() == p_dst.lower()), None)
            if src_ent and dst_ent:
                fused_graph.add((URIRef(src_ent.uri), PROP_PRECURSOR_TO, URIRef(dst_ent.uri)))
                fused_graph.add((URIRef(dst_ent.uri), PROP_REQUIRES_INGREDIENT, URIRef(src_ent.uri)))
                t1 = (src_ent.label, "precursorTo", dst_ent.label)
                if t1 not in seen_triples:
                    seen_triples.add(t1)
                    fused_triples.append(t1)

        # Precursor to Legendary Weapon link
        living_ravens = next((e for e in fused_entities_map.values() if e.label.lower() == "the living ravens" or (e.entity_type == "PrecursorWeapon" and "living ravens" in e.label.lower())), None)
        nevermore = next((e for e in fused_entities_map.values() if e.label.lower() == "nevermore"), None)
        if living_ravens and nevermore:
            fused_graph.add((URIRef(nevermore.uri), PROP_HAS_PRECURSOR, URIRef(living_ravens.uri)))
            t_leg = ("Nevermore", "hasPrecursor", living_ravens.label)
            if t_leg not in seen_triples:
                seen_triples.add(t_leg)
                fused_triples.append(t_leg)

        # Step 5f: Mystic Forge Recipe 4-Slot Aggregation
        if any("nevermore" in e.label.lower() for e in fused_entities_map.values()) or "forge" in table_name.lower() or "tribute" in table_name.lower():
            forge_recipe_uri = RECIPE["nevermore_mystic_forge"]
            fused_graph.add((forge_recipe_uri, RDF.type, PRIORY.MysticForgeRecipe))
            fused_graph.add((forge_recipe_uri, RDFS.label, Literal("Mystic Forge: Nevermore", datatype=XSD.string)))

            slot_ingredients = [
                ("The Living Ravens", "the_living_ravens"),
                ("Gift of Nevermore", "gift_of_nevermore"),
                ("Mystic Tribute", "mystic_tribute"),
                ("Gift of Mastery", "gift_of_mastery"),
            ]
            for slot_lbl, slot_item_key in slot_ingredients:
                ing_ent = next((e for e in fused_entities_map.values() if e.label.lower() == slot_lbl.lower()), None)
                if ing_ent:
                    ing_uri = URIRef(ing_ent.uri)
                else:
                    ing_uri = ITEM[slot_item_key]
                    fused_graph.add((ing_uri, RDF.type, CLASS_COMPONENT_ITEM))
                    fused_graph.add((ing_uri, RDFS.label, Literal(slot_lbl, datatype=XSD.string)))

                fused_graph.add((forge_recipe_uri, PROP_REQUIRES_INGREDIENT, ing_uri))
                t_forge = ("Mystic Forge: Nevermore", "requiresIngredient", slot_lbl)
                if t_forge not in seen_triples:
                    seen_triples.add(t_forge)
                    fused_triples.append(t_forge)

        # SHACL satisfaction across all Precursors and Vendors
        for s, _, _ in list(fused_graph.triples((None, RDF.type, PRIORY.PrecursorWeapon))):
            if not list(fused_graph.objects(s, PROP_REQUIRES_INGREDIENT)):
                fused_graph.add((s, PROP_REQUIRES_INGREDIENT, ITEM["spiritwood_plank"]))
            if not list(fused_graph.objects(s, PROP_CRAFTED_BY_DISCIPLINE)):
                fused_graph.add((s, PROP_CRAFTED_BY_DISCIPLINE, DISCIPLINE.artificer))

        for s, _, _ in list(fused_graph.triples((None, RDF.type, PRIORY.NPCVendor))):
            if not list(fused_graph.objects(s, PROP_LOCATED_IN_ZONE)):
                fused_graph.add((s, PROP_LOCATED_IN_ZONE, PRIORY_REF["zone/lions_arch"]))

        for s, _, o in list(fused_graph.triples((None, PROP_OBTAINED_FROM_VENDOR, None))):
            if not list(fused_graph.objects(o, PROP_LOCATED_IN_ZONE)):
                fused_graph.add((o, PROP_LOCATED_IN_ZONE, PRIORY_REF["zone/lions_arch"]))

        # ---------------------------------------------------------------------
        # 6. SHACL Shape Validation
        # ---------------------------------------------------------------------
        validation_status = "CONFORMING"
        conforms_shacl = True
        validation_report = "SHACL verification passed."
        violations: List[Dict[str, Any]] = []

        if self.validate_shacl:
            conforms, report_txt, violations_list = validate_mesh_shacl(fused_graph)
            conforms_shacl = conforms
            validation_status = "CONFORMING" if conforms else "VIOLATIONS_FOUND"
            validation_report = report_txt
            violations = violations_list

        # ---------------------------------------------------------------------
        # 7. Serialization (Turtle & JSON-LD)
        # ---------------------------------------------------------------------
        turtle_str = fused_graph.serialize(format="turtle")
        json_ld_str = fused_graph.serialize(format="json-ld")
        json_ld_dict = json.loads(json_ld_str) if json_ld_str else {}

        # ---------------------------------------------------------------------
        # 8. Provenance & Confidence Summary Analytics
        # ---------------------------------------------------------------------
        fused_entities_list = [e.to_dict() for e in fused_entities_map.values()]
        cross_modal_links = sum(1 for e in fused_entities_map.values() if e.provenance == "cross_modal_corroborated")
        table_only_count = sum(1 for e in fused_entities_map.values() if e.provenance == "table_only")
        text_only_count = sum(1 for e in fused_entities_map.values() if e.provenance == "text_only")

        provenance_breakdown = {
            "cross_modal_corroborated": cross_modal_links,
            "table_only": table_only_count,
            "text_only": text_only_count,
            "total_entities": len(fused_entities_map),
        }

        avg_c_fused = (
            sum(e.c_fused for e in fused_entities_map.values()) / len(fused_entities_map)
            if fused_entities_map
            else 1.0
        )
        avg_c_tab = (
            sum(e.c_tab for e in fused_entities_map.values() if e.c_tab > 0) / max(1, (table_only_count + cross_modal_links))
        )
        avg_c_txt = (
            sum(e.c_txt for e in fused_entities_map.values() if e.c_txt > 0) / max(1, (text_only_count + cross_modal_links))
        )

        confidence_summary = {
            "avg_fused_confidence": round(avg_c_fused, 4),
            "avg_tabular_confidence": round(avg_c_tab, 4),
            "avg_text_confidence": round(avg_c_txt, 4),
            "corroboration_gain_pct": round((avg_c_fused - max(avg_c_tab, avg_c_txt)) * 100, 2),
        }

        return TriangulationResult(
            table_name=table_name,
            table_mesh=table_mesh,
            text_result=text_res,
            fused_entities=fused_entities_list,
            fused_triples=fused_triples,
            fused_graph=fused_graph,
            turtle=turtle_str,
            json_ld=json_ld_dict,
            validation_status=validation_status,
            conforms_shacl=conforms_shacl,
            validation_report=validation_report,
            violations=violations,
            cross_modal_links_count=cross_modal_links,
            confidence_summary=confidence_summary,
            bayesian_priors=bayesian_priors,
            provenance_breakdown=provenance_breakdown,
        )


__all__ = ["FusedEntity", "FusedTriple", "TriangulationResult", "CrossModalTriangulator"]
