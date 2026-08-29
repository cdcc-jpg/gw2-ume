"""Neuro-Symbolic Ping-Pong Engine for GW2-UME.

Combines neural proposal generation (LLM/normalizer) with axiomatic symbolic validation
(Relational Mesh / Ontology Reasoner) in an iterative feedback loop.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from gw2_ume.models import (
    CandidateTableInterpretation,
    CellMention,
    DiagnosticConflict,
    PingPongResult,
    PingPongStep,
    RefinedProposal,
    RowRelation,
    TableColumnInterpretation,
    TableGrid,
    TableInterpretationMesh,
)
from gw2_ume.ontology.loader import OntologyLoader
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner as OntologySymbolicAxiomReasoner
from gw2_ume.normalization.llm_normalizer import HeuristicNormalizer, LLMNormalizer
from gw2_ume.normalization.text_cleaner import KNOWN_ENTITY_TYPES, TextCleaner

logger = logging.getLogger(__name__)


# ============================================================================
# SYMBOLIC AXIOM REASONER & RELATIONAL MESH SOLVER
# ============================================================================

class SymbolicAxiomReasoner:
    """Symbolic reasoning engine checking domain, range, type disjointness,

    slot constraints, and ontology integrity rules for Guild Wars 2.
    Populated dynamically from loaded RDF/OWL ontology graphs.
    """

    def __init__(
        self,
        loader: Optional[OntologyLoader] = None,
        reasoner: Optional[OntologySymbolicAxiomReasoner] = None,
        strict_mode: bool = False,
        auto_load_defaults: bool = True,
    ) -> None:
        self.strict_mode = strict_mode
        if reasoner is not None:
            self.ontology_reasoner = reasoner
            self.loader = reasoner.loader
        else:
            self.loader = loader if loader is not None else OntologyLoader(auto_load_defaults=auto_load_defaults)
            self.ontology_reasoner = OntologySymbolicAxiomReasoner(loader=self.loader)

    @property
    def DISJOINT_TYPES(self) -> Dict[str, Set[str]]:
        """Dynamically extracted disjoint types from loaded RDF/OWL ontology graph."""
        return self.ontology_reasoner.get_disjoint_types_map()

    @property
    def PREDICATE_SIGNATURES(self) -> Dict[str, Tuple[Set[str], Set[str]]]:
        """Dynamically extracted predicate signatures from loaded RDF/OWL ontology graph."""
        return self.ontology_reasoner.get_predicate_signatures()

    def validate_interpretation(
        self,
        proposal: CandidateTableInterpretation,
        table: TableGrid,
    ) -> List[DiagnosticConflict]:
        """Validate candidate table interpretation against all symbolic axioms."""
        conflicts: List[DiagnosticConflict] = []

        # 1. Validate Column Types vs Cell Contents (Type Incompatibility & Disjointness)
        conflicts.extend(self._check_column_type_compatibility(proposal, table))

        # 2. Validate Row Relations (Domain & Range Violations)
        conflicts.extend(self._check_relation_domain_range(proposal))

        # 3. Validate Mystic Forge / Recipe Slot Constraints
        conflicts.extend(self._check_recipe_slot_constraints(proposal, table))

        # 4. Validate Intermediate Gift vs Final Output Ambiguity
        conflicts.extend(self._check_intermediate_gift_semantics(proposal))

        # 5. Validate Quantities and Cardinalities
        conflicts.extend(self._check_cardinality_and_quantities(proposal))

        return conflicts

    def _check_column_type_compatibility(
        self,
        proposal: CandidateTableInterpretation,
        table: TableGrid,
    ) -> List[DiagnosticConflict]:
        """Check if column type matches the entities contained in its cells."""
        conflicts: List[DiagnosticConflict] = []
        disjoint_map = self.DISJOINT_TYPES

        for col in proposal.columns:
            col_type = col.predicted_type
            col_cells = [m for m in proposal.cell_mentions if m.col_idx == col.column_index]
            if not col_cells:
                continue

            for cell in col_cells:
                # Check ground truth type of cell if known
                actual_type = KNOWN_ENTITY_TYPES.get(cell.normalized_text)
                if not actual_type:
                    continue

                is_disjoint = (
                    self.ontology_reasoner.are_disjoint(col_type, actual_type)
                    or actual_type in disjoint_map.get(col_type, set())
                )
                if is_disjoint:
                    suggested = actual_type
                    conflicts.append(
                        DiagnosticConflict(
                            conflict_type="TYPE_INCOMPATIBILITY",
                            severity="ERROR",
                            target_col=col.column_index,
                            target_row=cell.row_idx,
                            message=(
                                f"Column '{col.column_name}' (idx {col.column_index}) was matched as {col_type}, "
                                f"but contains '{cell.normalized_text}' which is a {actual_type}. "
                                f"Types {col_type} and {actual_type} are disjoint."
                            ),
                            offending_value=cell.normalized_text,
                            suggested_fix=f"Change column type to {suggested} and role to ingredient.",
                            rule_or_axiom=f"Disjoint({col_type}, {actual_type})",
                        )
                    )

        return conflicts

    def _check_relation_domain_range(
        self,
        proposal: CandidateTableInterpretation,
    ) -> List[DiagnosticConflict]:
        """Check domain and range validity for extracted row relations."""
        conflicts: List[DiagnosticConflict] = []
        signatures = self.PREDICATE_SIGNATURES

        for rel in proposal.row_relations:
            pred = rel.predicate
            valid_ranges: Set[str] = set()

            if pred in signatures:
                _, valid_ranges = signatures[pred]
            else:
                expected_ranges = self.ontology_reasoner.get_expected_ranges(pred)
                for r in expected_ranges:
                    r_pref = self.loader.to_prefixed_name(r)
                    valid_ranges.add(r_pref.split(":")[-1])
                    valid_ranges.add(str(r))
                    for sub in self.loader.get_subclasses(r, direct=False):
                        s_pref = self.loader.to_prefixed_name(sub)
                        valid_ranges.add(s_pref.split(":")[-1])
                        valid_ranges.add(str(sub))

            if not valid_ranges:
                continue

            # Check Object range
            obj_type = KNOWN_ENTITY_TYPES.get(rel.object, "Item")
            is_valid_range = (
                obj_type in valid_ranges
                or "Item" in valid_ranges
                or any(self.ontology_reasoner.is_subclass_of(obj_type, r) for r in valid_ranges)
            )

            if not is_valid_range:
                conflicts.append(
                    DiagnosticConflict(
                        conflict_type="RANGE_VIOLATION",
                        severity="ERROR",
                        target_row=rel.row_idx,
                        message=(
                            f"Relation '{rel.subject} {pred} {rel.object}' violates range constraint: "
                            f"'{rel.object}' has type {obj_type}, but {pred} requires one of {sorted(valid_ranges)}."
                        ),
                        offending_value=rel.object,
                        suggested_fix=f"Map predicate to appropriate relation or retype '{rel.object}'.",
                        rule_or_axiom=f"Range({pred}) ⊆ {valid_ranges}",
                    )
                )

        return conflicts

    def _check_recipe_slot_constraints(
        self,
        proposal: CandidateTableInterpretation,
        table: TableGrid,
    ) -> List[DiagnosticConflict]:
        """Validate Mystic Forge recipes (must have 4 ingredient inputs) and craft requirements."""
        conflicts: List[DiagnosticConflict] = []

        if proposal.table_type == "MysticForgeRecipe":
            # Count distinct ingredients
            ingredients = [r.object for r in proposal.row_relations if r.predicate in ("requiresMaterial", "hasIngredient")]
            if len(ingredients) > 4:
                conflicts.append(
                    DiagnosticConflict(
                        conflict_type="CARDINALITY_VIOLATION",
                        severity="ERROR",
                        message=f"Mystic Forge recipe has {len(ingredients)} ingredients, but Mystic Forge allows exactly 4 inputs.",
                        offending_value=len(ingredients),
                        suggested_fix="Re-evaluate table rows or reclassify table as CraftingRecipe.",
                        rule_or_axiom="MysticForgeInputSlots == 4",
                    )
                )

        return conflicts

    def _check_intermediate_gift_semantics(
        self,
        proposal: CandidateTableInterpretation,
    ) -> List[DiagnosticConflict]:
        """Verify that intermediate Gifts (e.g. Gift of Energy, Gift of Wood) are not mistakenly

        classified as final weapon rewards if the overarching recipe is for a legendary weapon like Nevermore.
        """
        conflicts: List[DiagnosticConflict] = []

        # Check if subject is an intermediate gift when overarching table is a weapon recipe
        if proposal.subject_entity:
            subj_type = KNOWN_ENTITY_TYPES.get(proposal.subject_entity)
            if subj_type == "LegendaryGift":
                # Check if table mentions weapon ingredients or legendary goals
                mentions = [m.normalized_text for m in proposal.cell_mentions]
                if any("Spiritwood Plank" in m or "Deldrimor Steel Ingot" in m for m in mentions):
                    # Check if Gift of Energy is matching Nevermore
                    if proposal.subject_entity == "Gift of Energy" and any("Nevermore" in m for m in mentions):
                        conflicts.append(
                            DiagnosticConflict(
                                conflict_type="SLOT_MISMATCH",
                                severity="WARNING",
                                message=(
                                    f"'{proposal.subject_entity}' is an intermediate LegendaryGift, but is used as the table subject. "
                                    f"In Nevermore crafting, Gift of Energy is an input slot to Gift of Nevermore."
                                ),
                                offending_value=proposal.subject_entity,
                                suggested_fix="Set subject to Gift of Nevermore or Nevermore, and treat Gift of Energy as intermediate ingredient.",
                                rule_or_axiom="subComponentOf(Gift of Energy, Gift of Nevermore)",
                            )
                        )

        return conflicts

    def _check_cardinality_and_quantities(
        self,
        proposal: CandidateTableInterpretation,
    ) -> List[DiagnosticConflict]:
        """Ensure quantities are positive non-zero numbers."""
        conflicts: List[DiagnosticConflict] = []

        for rel in proposal.row_relations:
            if rel.quantity is not None and rel.quantity <= 0:
                conflicts.append(
                    DiagnosticConflict(
                        conflict_type="CARDINALITY_VIOLATION",
                        severity="ERROR",
                        target_row=rel.row_idx,
                        message=f"Quantity for '{rel.object}' in row {rel.row_idx} is non-positive ({rel.quantity}).",
                        offending_value=rel.quantity,
                        suggested_fix="Quantity must be greater than 0.",
                        rule_or_axiom="Quantity > 0",
                    )
                )

        return conflicts


# ============================================================================
# NEURO-SYMBOLIC PING-PONG ENGINE
# ============================================================================

class NeuroSymbolicPingPongEngine:
    """The Neuro-Symbolic Ping-Pong Engine for iterative table and text interpretation.

    Loops between neural proposal generation (LLM/normalizer) and symbolic validation
    (Axiomatic Reasoner), feeding structured diagnostics back to the neural model
    until full axiomatic convergence is achieved.
    """

    def __init__(
        self,
        normalizer: Optional[LLMNormalizer] = None,
        reasoner: Optional[SymbolicAxiomReasoner] = None,
    ) -> None:
        self.normalizer: LLMNormalizer = normalizer or HeuristicNormalizer()
        self.reasoner: SymbolicAxiomReasoner = reasoner or SymbolicAxiomReasoner()

    def run(
        self,
        table: TableGrid,
        max_iterations: int = 3,
    ) -> PingPongResult:
        """Execute the Neuro-Symbolic Ping-Pong dialogue loop on a table.

        Args:
            table: TableGrid representing the tabular data to interpret.
            max_iterations: Maximum ping-pong dialogue iterations (default: 3).

        Returns:
            PingPongResult: Full execution history, convergence status, resolved mesh, and diagnostic logs.
        """
        history: List[PingPongStep] = []
        diagnostic_logs: List[str] = []

        # --------------------------------------------------------------------
        # PASS 1: Initial Neural Proposal
        # --------------------------------------------------------------------
        current_proposal = self.normalizer.extract_table_mentions(table)
        step_num = 1

        conflicts = self.reasoner.validate_interpretation(current_proposal, table)
        log_entry = f"Pass 1: Generated initial proposal with {len(current_proposal.columns)} columns, {len(current_proposal.row_relations)} relations. Conflicts detected: {len(conflicts)}"
        diagnostic_logs.append(log_entry)
        logger.info(log_entry)

        history.append(
            PingPongStep(
                step_number=step_num,
                proposal=current_proposal,
                conflicts=conflicts,
                feedback_message="\n".join(c.format_diagnostic() for c in conflicts),
                adjustments=[],
            )
        )

        converged = len(conflicts) == 0

        # --------------------------------------------------------------------
        # PING-PONG DIALOGUE LOOP
        # --------------------------------------------------------------------
        while not converged and step_num < max_iterations:
            step_num += 1
            log_entry = f"Pass {step_num}: Feeding {len(conflicts)} diagnostic conflicts back to LLM/Normalizer."
            diagnostic_logs.append(log_entry)
            logger.info(log_entry)

            # Neural Step: Disambiguation & Refinement
            refined_proposal = self.normalizer.resolve_ambiguity(current_proposal, conflicts)
            current_proposal = refined_proposal.interpretation

            # Symbolic Step: Re-evaluation against Relational Mesh
            new_conflicts = self.reasoner.validate_interpretation(current_proposal, table)

            history.append(
                PingPongStep(
                    step_number=step_num,
                    proposal=current_proposal,
                    conflicts=new_conflicts,
                    feedback_message="\n".join(c.format_diagnostic() for c in new_conflicts),
                    adjustments=refined_proposal.adjustments_made,
                )
            )

            log_entry = f"Pass {step_num} Result: Adjustments made: {refined_proposal.adjustments_made}. Remaining conflicts: {len(new_conflicts)}"
            diagnostic_logs.append(log_entry)
            logger.info(log_entry)

            if len(new_conflicts) == 0:
                converged = True
                conflicts = []
                break
            elif len(new_conflicts) >= len(conflicts):
                # No further reduction in conflicts
                conflicts = new_conflicts
                break
            else:
                conflicts = new_conflicts

        # --------------------------------------------------------------------
        # FINAL GROUNDING: Construct TableInterpretationMesh
        # --------------------------------------------------------------------
        resolved_mesh = self._build_interpretation_mesh(table, current_proposal)

        final_success = (len(conflicts) == 0)
        final_log = f"Ping-Pong loop finished in {step_num} passes. Converged: {converged}. Success: {final_success}."
        diagnostic_logs.append(final_log)
        logger.info(final_log)

        return PingPongResult(
            success=final_success,
            converged=converged,
            iterations=step_num,
            history=history,
            mesh=resolved_mesh,
            remaining_conflicts=conflicts,
            diagnostic_logs=diagnostic_logs,
        )

    def _build_interpretation_mesh(
        self,
        table: TableGrid,
        proposal: CandidateTableInterpretation,
    ) -> TableInterpretationMesh:
        """Ground resolved table proposal into a clean TableInterpretationMesh with RDF triples."""
        subject = proposal.subject_entity or "TargetRecipe"
        triples: List[Tuple[str, str, Any]] = []

        # Table classification triple
        triples.append((subject, "rdf:type", f"gw2ume:{proposal.table_type}"))

        # Row relation triples
        for rel in proposal.row_relations:
            # Triple: (Subject, Predicate, Object)
            triples.append((rel.subject, f"gw2ume:{rel.predicate}", f"gw2item:{self._clean_uri_id(rel.object)}"))
            
            # If quantity present, add quantity statement
            if rel.quantity is not None:
                triples.append((rel.subject, f"gw2ume:hasIngredientQuantity", rel.quantity))

        return TableInterpretationMesh(
            table_id=str(table.metadata.get("id", "table_1")),
            table_type=proposal.table_type,
            subject_entity=proposal.subject_entity,
            columns=proposal.columns,
            row_relations=proposal.row_relations,
            cell_mentions=proposal.cell_mentions,
            triples=triples,
            confidence=0.95 if not proposal.columns else min((c.confidence for c in proposal.columns), default=0.9),
            metadata=table.metadata,
        )

    @staticmethod
    def _clean_uri_id(name: str) -> str:
        """Convert an entity name to a safe URI identifier."""
        return re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip()).strip("_")
