"""Knowledge Graph Triplifier, RDF Turtle & JSON-LD Exporter, and Ontology Builder.

Converts resolved TableInterpretationMesh and TextInterpretationResult instances
into valid RDF/Turtle, JSON-LD graphs, and proposes candidate ontology axioms
for novel entities and relations.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from gw2_ume.models import (
    CandidateOntologyAxiom,
    PingPongResult,
    TableInterpretationMesh,
    TextInterpretationResult,
)
from gw2_ume.normalization.text_cleaner import KNOWN_ENTITY_TYPES

logger = logging.getLogger(__name__)


# ============================================================================
# NAMESPACES
# ============================================================================

SCHEMA = Namespace("http://schema.org/")
GW2UME = Namespace("http://gw2ume.org/ontology/")
GW2ITEM = Namespace("http://gw2ume.org/resource/item/")
GW2RECIPE = Namespace("http://gw2ume.org/resource/recipe/")
GW2CURR = Namespace("http://gw2ume.org/resource/currency/")
GW2NPC = Namespace("http://gw2ume.org/resource/npc/")


# ============================================================================
# KNOWLEDGE GRAPH ENRICHER
# ============================================================================

class KnowledgeGraphEnricher:
    """Triplifier and ontology generator for resolved meshes and text extractions."""

    def __init__(self) -> None:
        pass

    def build_rdf_graph(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> Graph:
        """Build an rdflib.Graph populated with semantic triples from mesh or text result."""
        g = Graph()
        g.bind("gw2ume", GW2UME)
        g.bind("gw2item", GW2ITEM)
        g.bind("gw2recipe", GW2RECIPE)
        g.bind("gw2curr", GW2CURR)
        g.bind("gw2npc", GW2NPC)
        g.bind("schema", SCHEMA)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)

        if isinstance(target, PingPongResult):
            mesh = target.mesh
            self._enrich_from_mesh(g, mesh)
        elif isinstance(target, TableInterpretationMesh):
            self._enrich_from_mesh(g, target)
        elif isinstance(target, TextInterpretationResult):
            self._enrich_from_text(g, target)

        return g

    def export_turtle(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> str:
        """Export knowledge graph to valid Turtle (TTL) string format."""
        g = self.build_rdf_graph(target)
        return g.serialize(format="turtle")

    def export_jsonld(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> Dict[str, Any]:
        """Export knowledge graph to structured JSON-LD dictionary."""
        g = self.build_rdf_graph(target)
        jsonld_str = g.serialize(format="json-ld")
        try:
            return json.loads(jsonld_str)
        except Exception:
            return {"@context": {}, "@graph": []}

    def propose_ontology_extensions(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> List[CandidateOntologyAxiom]:
        """Detect novel ungrounded entities or candidate relations and propose ontology extensions."""
        axioms: List[CandidateOntologyAxiom] = []

        if isinstance(target, PingPongResult):
            mesh = target.mesh
        elif isinstance(target, TableInterpretationMesh):
            mesh = target
        else:
            # Text result
            mesh = None

        if mesh:
            # Check cell mentions and row relations for novel entities
            for cell in mesh.cell_mentions:
                norm = cell.normalized_text
                if not norm:
                    continue

                if norm not in KNOWN_ENTITY_TYPES:
                    # Candidate novel entity!
                    pred_class = cell.entity_type if cell.entity_type != "Unknown" else "CraftingMaterial"
                    turtle_def = (
                        f"gw2item:{self._clean_id(norm)} rdf:type gw2ume:{pred_class} ;\n"
                        f"    rdfs:label \"{norm}\"@en .\n"
                    )
                    axioms.append(
                        CandidateOntologyAxiom(
                            axiom_type="InstanceDeclaration",
                            subject=f"gw2item:{self._clean_id(norm)}",
                            predicate="rdf:type",
                            object=f"gw2ume:{pred_class}",
                            confidence=0.85,
                            evidence=f"Discovered novel item '{norm}' in table '{mesh.table_id}' classified as '{pred_class}'.",
                            proposed_turtle=turtle_def,
                        )
                    )

            # Check if custom relations exist
            for rel in mesh.row_relations:
                if rel.predicate not in ("requiresMaterial", "hasIngredient", "requiresDiscipline", "costsCurrency"):
                    pred_id = self._clean_id(rel.predicate)
                    turtle_def = (
                        f"gw2ume:{pred_id} rdf:type rdf:Property ;\n"
                        f"    rdfs:label \"{rel.predicate}\"@en ;\n"
                        f"    rdfs:domain gw2ume:CraftingRecipe ;\n"
                        f"    rdfs:range gw2ume:Item .\n"
                    )
                    axioms.append(
                        CandidateOntologyAxiom(
                            axiom_type="NewProperty",
                            subject=f"gw2ume:{pred_id}",
                            predicate="rdf:type",
                            object="rdf:Property",
                            confidence=0.8,
                            evidence=f"Discovered relation predicate '{rel.predicate}' in table '{mesh.table_id}'.",
                            proposed_turtle=turtle_def,
                        )
                    )

        return axioms

    # ------------------------------------------------------------------------
    # Internal Enrichment Helpers
    # ------------------------------------------------------------------------

    def _enrich_from_mesh(self, g: Graph, mesh: TableInterpretationMesh) -> None:
        """Add triples from TableInterpretationMesh into rdflib Graph."""
        subject_name = mesh.subject_entity or "TargetRecipe"
        subject_uri = self._get_entity_uri(subject_name, mesh.table_type)

        # Subject classification
        type_class = getattr(GW2UME, mesh.table_type, GW2UME.CraftingRecipe)
        g.add((subject_uri, RDF.type, type_class))
        g.add((subject_uri, RDFS.label, Literal(subject_name, lang="en")))

        # Add row relations
        for rel in mesh.row_relations:
            pred_uri = getattr(GW2UME, rel.predicate, URIRef(f"http://gw2ume.org/ontology/{rel.predicate}"))
            obj_type = KNOWN_ENTITY_TYPES.get(rel.object, "Item")
            obj_uri = self._get_entity_uri(rel.object, obj_type)

            # Classify object
            obj_class = getattr(GW2UME, obj_type, GW2UME.Item)
            g.add((obj_uri, RDF.type, obj_class))
            g.add((obj_uri, RDFS.label, Literal(rel.object, lang="en")))

            # Link subject -> object
            if rel.quantity is not None:
                # Create a blank node or direct property for ingredient requirement
                ing_node = BNode()
                g.add((subject_uri, GW2UME.hasIngredientRequirement, ing_node))
                g.add((ing_node, RDF.type, GW2UME.IngredientRequirement))
                g.add((ing_node, GW2UME.requiresItem, obj_uri))
                g.add((ing_node, GW2UME.quantity, Literal(rel.quantity, datatype=XSD.decimal if isinstance(rel.quantity, float) else XSD.integer)))
            
            # Also add direct predicate
            g.add((subject_uri, pred_uri, obj_uri))

    def _enrich_from_text(self, g: Graph, text_res: TextInterpretationResult) -> None:
        """Add triples from TextInterpretationResult into rdflib Graph."""
        for span in text_res.spans:
            ent_name = span.normalized_text or span.text
            ent_type = span.candidate_types[0] if span.candidate_types else "Item"
            ent_uri = self._get_entity_uri(ent_name, ent_type)
            ent_class = getattr(GW2UME, ent_type, GW2UME.Item)

            g.add((ent_uri, RDF.type, ent_class))
            g.add((ent_uri, RDFS.label, Literal(ent_name, lang="en")))
            if span.quantity is not None:
                g.add((ent_uri, GW2UME.quantity, Literal(span.quantity, datatype=XSD.integer if isinstance(span.quantity, int) else XSD.decimal)))

        for rel in text_res.relations:
            s_uri = self._get_entity_uri(rel.subject, "Item")
            p_uri = getattr(GW2UME, rel.predicate, URIRef(f"http://gw2ume.org/ontology/{rel.predicate}"))
            o_uri = self._get_entity_uri(rel.object, "Item")
            g.add((s_uri, p_uri, o_uri))

    def _get_entity_uri(self, name: str, entity_type: str) -> URIRef:
        """Generate a clean URIRef for an entity name based on type."""
        clean_name = self._clean_id(name)
        if entity_type == "Currency":
            return GW2CURR[clean_name]
        elif entity_type in ("CraftingRecipe", "MysticForgeRecipe"):
            return GW2RECIPE[clean_name]
        elif entity_type == "NPC":
            return GW2NPC[clean_name]
        else:
            return GW2ITEM[clean_name]

    @staticmethod
    def _clean_id(name: str) -> str:
        """Create safe URI identifier slug."""
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip())
        return clean.strip("_")
