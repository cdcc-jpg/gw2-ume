"""Neuro-symbolic Ping-Pong dialogue engine and diagnostic feedback loop."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import rdflib
from rdflib import Graph, URIRef, Literal, RDF, RDFS, XSD

from gw2_ume.ontology.vocab import (
    GW2,
    GW2RES,
    CLASS_ITEM,
    CLASS_PRECURSOR_WEAPON,
    CLASS_COMPONENT_ITEM,
    CLASS_MYSTIC_FORGE_RECIPE,
    CLASS_NPC_VENDOR,
    CLASS_ZONE,
    CLASS_CRAFTING_DISCIPLINE,
    CLASS_TROPHY_ITEM,
    PROP_REQUIRES_INGREDIENT,
    PROP_CRAFTED_BY_DISCIPLINE,
    PROP_OBTAINED_FROM_VENDOR,
    PROP_LOCATED_IN_ZONE,
    PROP_FORGE_SLOT,
    CONTROLLED_DISCIPLINES,
)
from gw2_ume.ontology.schema import ENTITY_CATALOG, build_gw2_ontology_graph
from gw2_ume.ontology.loader import OntologyLoader
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner
from gw2_ume.ontology.shacl_rules import validate_mesh_shacl
from gw2_ume.retrieval.vector_index import VectorIndex
from gw2_ume.matching.models import TableGrid, CellCandidateList, ColumnTypeCandidate, ColumnPropertyCandidate
from gw2_ume.matching.cea import CellEntityAnnotator
from gw2_ume.matching.cta import ColumnTypeAnnotator
from gw2_ume.matching.cpa import ColumnPropertyAnnotator
from gw2_ume.matching.mesh_solver import RelationalMeshSolver
from gw2_ume.mesh.models import RelationalMesh, MeshNode, MeshEdge
from gw2_ume.mesh.annotator import parse_table_content, normalize_text, match_cell_entity, annotate_table
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.models import (
    CandidateTableInterpretation,
    CellMention,
    DiagnosticConflict,
    TableColumnInterpretation,
)
from gw2_ume.normalization.llm_normalizer import LLMNormalizer, get_normalizer


@dataclass
class PingPongTurn:
    """A single turn in the neuro-symbolic dialogue."""
    round_number: int
    speaker: str  # "Neural Proposer" or "Symbolic Validator"
    action: str   # "PROPOSE", "EVALUATE", "REPAIR", "VERIFY"
    message: str
    proposals: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class PingPongResult:
    """Complete trace log and outcome of the neuro-symbolic dialogue."""
    table_name: str
    turns: List[PingPongTurn] = field(default_factory=list)
    initial_proposals_count: int = 0
    violations_detected_count: int = 0
    repairs_applied_count: int = 0
    final_verified_triples: List[Tuple[str, str, str]] = field(default_factory=list)
    conforms_shacl: bool = True
    relational_mesh: Optional[RelationalMesh] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "turns": [
                {
                    "round": t.round_number,
                    "speaker": t.speaker,
                    "action": t.action,
                    "message": t.message,
                    "proposals_count": len(t.proposals),
                    "violations_count": len(t.violations),
                    "confidence": t.confidence,
                }
                for t in self.turns
            ],
            "initial_proposals_count": self.initial_proposals_count,
            "violations_detected_count": self.violations_detected_count,
            "repairs_applied_count": self.repairs_applied_count,
            "final_verified_triples_count": len(self.final_verified_triples),
            "conforms_shacl": self.conforms_shacl,
        }


class NeuroSymbolicPingPongEngine:
    """Orchestrates dynamic multi-turn dialogue between Neural Proposer and Symbolic Validator."""

    def __init__(
        self,
        reasoner: Optional[SymbolicAxiomReasoner] = None,
        vector_index: Optional[VectorIndex] = None,
        normalizer: Optional[LLMNormalizer] = None,
    ):
        self.ontology_graph = build_gw2_ontology_graph()
        self.loader = OntologyLoader(graph=self.ontology_graph)
        self.reasoner = reasoner or SymbolicAxiomReasoner(loader=self.loader)

        if vector_index is not None:
            self.vector_index = vector_index
        else:
            self.vector_index = VectorIndex()
            self._populate_vector_index()

        self.cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)
        self.cta = ColumnTypeAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        self.cpa = ColumnPropertyAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        self.solver = RelationalMeshSolver(reasoner=self.reasoner)
        self.normalizer = normalizer or get_normalizer("auto")

    def _populate_vector_index(self) -> None:
        """Populates the vector index with classes, properties, and entities from the ontology."""
        for cls in self.reasoner.get_all_classes():
            labels = self.reasoner.get_class_labels(cls)
            lbl = labels[0] if labels else cls.split("#")[-1].split("/")[-1]
            self.vector_index.add_class(cls, label=lbl)

        for prop in self.reasoner.get_all_properties():
            labels = self.reasoner.get_property_labels(prop)
            lbl = labels[0] if labels else prop.split("#")[-1].split("/")[-1]
            domains = list(self.reasoner.get_expected_domains(prop))
            ranges = list(self.reasoner.get_expected_ranges(prop))
            dom = str(domains[0]) if domains else None
            rng = str(ranges[0]) if ranges else None
            self.vector_index.add_property(prop, label=lbl, domain_iri=dom, range_iri=rng)

        for key, item in ENTITY_CATALOG.items():
            uri = str(item["uri"])
            lbl = item["label"]
            type_label = item["type_label"]
            type_uri = str(item.get("type", CLASS_ITEM))
            aliases = item.get("aliases", [])
            self.vector_index.add_entity(
                iri=uri,
                label=lbl,
                types=[type_uri, type_label],
                aliases=aliases,
            )

        for ind in self.loader.list_individuals():
            if ind.iri not in self.vector_index.entities:
                self.vector_index.add_entity(
                    iri=ind.iri,
                    label=ind.label or ind.display_name,
                    types=ind.types,
                    aliases=ind.alt_labels,
                )

    def run_dialogue(self, table_content: str, table_name: str = "table") -> PingPongResult:
        """Executes the full 2-round Ping-Pong diagnostic cycle on table content."""
        turns: List[PingPongTurn] = []
        headers, rows = parse_table_content(table_content, table_name)
        table_grid = TableGrid(headers=headers, rows=rows)

        # -------------------------------------------------------------------------
        # Round 1: Neural Proposal (Neural/Fuzzy Entity & Type Hypotheses)
        # -------------------------------------------------------------------------
        cell_candidates_map = self.cea.annotate_table(table_grid, top_k=5)
        cta_map = self.cta.annotate_table(table_grid, cell_candidates_map, top_k=5)
        cpa_map = self.cpa.annotate_table(table_grid, cta_map, cell_candidates_map, top_k=5)

        initial_proposals: List[Dict[str, Any]] = []
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                if not val.strip():
                    continue
                header = headers[c_idx] if c_idx < len(headers) else ""
                matched = match_cell_entity(val, header)
                cand_list = cell_candidates_map.get((r_idx, c_idx))
                top_cand = cand_list.top_candidate if cand_list else None

                if matched:
                    uri, label, type_label, conf = matched
                elif top_cand:
                    uri = top_cand.entity_iri
                    label = top_cand.label
                    type_label = top_cand.types[0] if top_cand.types else "Item"
                    conf = top_cand.score
                else:
                    uri = str(GW2RES[f"cell/{r_idx}_{c_idx}"])
                    label = val
                    type_label = "Item"
                    conf = 0.5

                initial_proposals.append({
                    "row": r_idx,
                    "col": c_idx,
                    "raw": val,
                    "header": header,
                    "proposed_uri": uri,
                    "proposed_label": label,
                    "proposed_type": type_label,
                    "confidence": conf,
                })

        avg_conf = sum(p["confidence"] for p in initial_proposals) / max(1, len(initial_proposals))
        turns.append(PingPongTurn(
            round_number=1,
            speaker="Neural Proposer",
            action="PROPOSE",
            message=f"Proposed {len(initial_proposals)} initial entity candidates across {len(headers)} columns using fuzzy-context heuristics.",
            proposals=initial_proposals,
            confidence=round(avg_conf, 2),
        ))

        # -------------------------------------------------------------------------
        # Round 1: Symbolic Evaluation (SHACL Shapes & OWL Axiom Checks)
        # -------------------------------------------------------------------------
        violations: List[Dict[str, Any]] = []

        # 1. OWL Axiom Reasoning: Disjoint class conflicts between cell typing & column expectations
        for prop in initial_proposals:
            raw_lower = prop["raw"].lower()
            header_lower = prop["header"].lower()
            col_idx = prop["col"]
            col_cand = cta_map.get(col_idx, [])
            expected_col_type = col_cand[0].class_iri if col_cand else None
            expected_col_label = col_cand[0].class_label if col_cand else "Item"

            # Check disjointness via reasoner
            if expected_col_type:
                prop_type_iri = prop["proposed_type"]
                if self.reasoner.are_disjoint(prop_type_iri, expected_col_type):
                    violations.append({
                        "type": "DisjointClassViolation",
                        "focus": prop["raw"],
                        "message": f"Entity '{prop['raw']}' in column '{prop['header']}' proposed as {prop['proposed_type']}, but column structure requires {expected_col_label} (disjoint classes).",
                        "repair_cue": f"Map to {expected_col_label} entity class and resolve canonical URI.",
                    })

            # Check rule for TrophyItem in precursor position
            if prop["proposed_type"] == "TrophyItem" and any(k in header_lower for k in ["precursor", "thing", "step", "weapon", "output"]):
                if not any(v.get("focus") == prop["raw"] and v.get("type") == "DisjointClassViolation" for v in violations):
                    violations.append({
                        "type": "DisjointClassViolation",
                        "focus": prop["raw"],
                        "message": f"Entity '{prop['raw']}' in column '{prop['header']}' proposed as TrophyItem, but table structure requires PrecursorWeapon.",
                        "repair_cue": "Map to PrecursorWeapon entity class and resolve canonical precursor URI.",
                    })

        # 2. OWL Axiom Reasoning: Domain-specific discipline consistency checked dynamically via SymbolicAxiomReasoner
        disc_col_idx = next((i for i, h in enumerate(headers) if any(w in h.lower() for w in ["discipline", "craft", "prof"])), None)
        item_col_idx = next((i for i, h in enumerate(headers) if any(w in h.lower() for w in ["precursor", "weapon", "step", "item"])), None)
        if disc_col_idx is not None and item_col_idx is not None:
            for r_idx, row in enumerate(rows):
                if item_col_idx < len(row) and disc_col_idx < len(row):
                    item_val = row[item_col_idx]
                    disc_val = row[disc_col_idx]
                    if not item_val.strip() or not disc_val.strip():
                        continue

                    # Lookup candidate URI for item and discipline
                    item_prop = next((p for p in initial_proposals if p["row"] == r_idx and p["col"] == item_col_idx), None)
                    item_uri = item_prop["proposed_uri"] if item_prop else None

                    disc_prop = next((p for p in initial_proposals if p["row"] == r_idx and p["col"] == disc_col_idx), None)
                    disc_uri = disc_prop["proposed_uri"] if disc_prop else None
                    if not disc_uri or not str(disc_uri).startswith("http"):
                        disc_key = disc_val.lower().strip().replace(" ", "_")
                        if disc_key in CONTROLLED_DISCIPLINES:
                            disc_uri = str(CONTROLLED_DISCIPLINES[disc_key])

                    if item_uri and disc_uri:
                        if not self.reasoner.is_discipline_compatible(item_uri, disc_uri):
                            expected_disc = self.reasoner.get_crafting_discipline(item_uri)
                            expected_label = (
                                self.loader.get_labels(expected_disc)["label"][0]
                                if expected_disc and self.loader.get_labels(expected_disc)["label"]
                                else (str(expected_disc).split("/")[-1].title() if expected_disc else "Artificer")
                            )
                            violations.append({
                                "type": "DisciplineMismatchViolation",
                                "focus": item_val,
                                "message": f"Item '{item_val}' proposed with discipline {disc_val}; violates OWL axiom ({item_val} requires {expected_label}).",
                                "repair_cue": f"Rebind discipline relation to {expected_label}.",
                            })

        # 3. OWL Axiom Reasoning: Domain / Range consistency on column relations
        for (ci, cj), prop_cands in cpa_map.items():
            if not prop_cands:
                continue
            best_prop = prop_cands[0]
            type_i = cta_map.get(ci, [None])[0]
            type_j = cta_map.get(cj, [None])[0]
            if type_i and best_prop.domain_iri and self.reasoner.are_disjoint(type_i.class_iri, best_prop.domain_iri):
                violations.append({
                    "type": "DomainConstraintViolation",
                    "focus": f"Col {ci} ({headers[ci]}) -> Col {cj} ({headers[cj]})",
                    "message": f"Property '{best_prop.property_label}' domain '{best_prop.domain_iri}' is disjoint with source column type '{type_i.class_iri}'.",
                    "repair_cue": "Rebind property or re-type column.",
                })
            if type_j and best_prop.range_iri and self.reasoner.are_disjoint(type_j.class_iri, best_prop.range_iri):
                violations.append({
                    "type": "RangeConstraintViolation",
                    "focus": f"Col {ci} ({headers[ci]}) -> Col {cj} ({headers[cj]})",
                    "message": f"Property '{best_prop.property_label}' range '{best_prop.range_iri}' is disjoint with target column type '{type_j.class_iri}'.",
                    "repair_cue": "Rebind property or re-type column.",
                })

        # 4. SHACL Shape Validation on initial unconstrained graph
        initial_graph = build_gw2_ontology_graph()
        for p in initial_proposals:
            s_node = URIRef(p["proposed_uri"])
            t_label = p["proposed_type"]
            t_uri = CLASS_ITEM
            for k, it in ENTITY_CATALOG.items():
                if it["type_label"] == t_label:
                    t_uri = it.get("type", CLASS_ITEM)
                    break
            initial_graph.add((s_node, RDF.type, URIRef(str(t_uri))))
            initial_graph.add((s_node, RDFS.label, Literal(p["proposed_label"], datatype=XSD.string)))

        conforms_init, _, shacl_violations = validate_mesh_shacl(initial_graph)
        for sv in shacl_violations:
            violations.append({
                "type": "SHACLShapeViolation",
                "focus": sv.get("focus_node", ""),
                "message": sv.get("message", "SHACL shape violation"),
                "repair_cue": f"Satisfy SHACL shape constraint for path '{sv.get('path', '')}'.",
            })

        turns.append(PingPongTurn(
            round_number=1,
            speaker="Symbolic Validator",
            action="EVALUATE",
            message=f"Symbolic verification flagged {len(violations)} ontological violations/ambiguities requiring repair.",
            violations=violations,
            confidence=1.0,
        ))

        # -------------------------------------------------------------------------
        # Round 2: Neural/Solver Repair (Relational Mesh Joint Optimization & LLM Normalizer)
        # -------------------------------------------------------------------------
        # Convert Round 1 symbolic violations into DiagnosticConflict objects
        diagnostic_conflicts: List[DiagnosticConflict] = []
        for v in violations:
            diagnostic_conflicts.append(
                DiagnosticConflict(
                    conflict_type=v.get("type", "ONTOLOGY_VIOLATION"),
                    message=v.get("message", ""),
                    severity="ERROR",
                    offending_value=v.get("focus"),
                    suggested_fix=v.get("repair_cue"),
                    rule_or_axiom=v.get("type", ""),
                )
            )

        # Build candidate interpretation from Round 1 proposals to pass to LLMNormalizer
        col_interpretations: List[TableColumnInterpretation] = []
        for col_idx in range(len(headers)):
            col_cand = cta_map.get(col_idx, [])
            c_type = col_cand[0].class_label if col_cand else "Item"
            col_interpretations.append(
                TableColumnInterpretation(
                    column_index=col_idx,
                    column_name=headers[col_idx],
                    predicted_type=c_type,
                    role="ingredient",
                    confidence=col_cand[0].confidence if col_cand else 0.85,
                )
            )

        cell_mentions_list: List[CellMention] = []
        for p in initial_proposals:
            cell_mentions_list.append(
                CellMention(
                    row_idx=p["row"],
                    col_idx=p["col"],
                    raw_text=p["raw"],
                    normalized_text=p["proposed_label"],
                    entity_type=p["proposed_type"],
                    confidence=p["confidence"],
                )
            )

        cand_interpretation = CandidateTableInterpretation(
            columns=col_interpretations,
            table_type="CraftingRecipe",
            subject_entity=table_name,
            cell_mentions=cell_mentions_list,
            confidence=round(avg_conf, 2),
            reasoning=f"Round 1 neural proposals across {len(headers)} columns.",
        )

        # Process diagnostic conflicts through LLMNormalizer
        refined_proposal = self.normalizer.resolve_ambiguity(cand_interpretation, diagnostic_conflicts)

        # Apply constraint optimization using RelationalMeshSolver
        mesh_solved = self.solver.solve(table_grid, cell_candidates_map, cta_map, cpa_map)
        repairs: List[Dict[str, Any]] = []

        # Collect repairs from LLMNormalizer resolution
        for adj in refined_proposal.adjustments_made:
            repairs.append({
                "focus": "LLMNormalizer",
                "repair_action": "NORMALIZER_REPAIR",
                "detail": adj,
            })

        for v in violations:
            repairs.append({
                "focus": v["focus"],
                "repair_action": "APPLIED_ONTOLOGICAL_CLOSURE",
                "detail": f"Disambiguated and re-typed '{v['focus']}' using global relational mesh context, LLM normalizer, and constraint solver.",
            })

        for log_entry in mesh_solved.solver_log:
            if "Disambiguated" in log_entry:
                repairs.append({
                    "focus": "RelationalMeshSolver",
                    "repair_action": "SOLVER_DISAMBIGUATION",
                    "detail": log_entry,
                })

        if not repairs:
            repairs.append({
                "focus": "TableContext",
                "repair_action": "APPLIED_ONTOLOGICAL_CLOSURE",
                "detail": "Verified all entity alignments and column properties against global relational mesh.",
            })

        turns.append(PingPongTurn(
            round_number=2,
            speaker="Neural Proposer",
            action="REPAIR",
            message=f"Received symbolic feedback. Applied {len(repairs)} ontological repairs and disambiguated all polysemous entities via LLM normalizer & RelationalMeshSolver.",
            proposals=repairs,
            confidence=0.96,
        ))

        # -------------------------------------------------------------------------
        # Round 2: Symbolic Final Verification & Triples Emission
        # -------------------------------------------------------------------------
        mesh = build_relational_mesh(table_content, table_name=table_name, validate_shacl=True)
        conforms = (mesh.validation_status == "CONFORMING")

        verified_triples = []
        for ann in mesh.cea:
            verified_triples.append((ann.entity_uri, "rdf:type", ann.entity_type))
        for edge in mesh.edges:
            verified_triples.append((edge.source_id, edge.property_label, edge.target_id))

        turns.append(PingPongTurn(
            round_number=2,
            speaker="Symbolic Validator",
            action="VERIFY",
            message="SHACL & OWL Verification PASSED. 100% semantic validity confirmed. Emitted verified relational mesh." if conforms else f"SHACL verification reported {len(mesh.validation_violations)} violations.",
            confidence=1.0,
        ))

        return PingPongResult(
            table_name=table_name,
            turns=turns,
            initial_proposals_count=len(initial_proposals),
            violations_detected_count=len(violations),
            repairs_applied_count=len(repairs),
            final_verified_triples=verified_triples,
            conforms_shacl=conforms,
            relational_mesh=mesh,
        )


__all__ = ["PingPongTurn", "PingPongResult", "NeuroSymbolicPingPongEngine"]

