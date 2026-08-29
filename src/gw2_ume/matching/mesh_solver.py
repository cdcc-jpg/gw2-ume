"""Relational Mesh Constraint Solver for Joint Semantic Table Interpretation."""

from __future__ import annotations

import itertools
from typing import Any
from gw2_ume.matching.models import (
    CellCandidate,
    CellCandidateList,
    ColumnTypeCandidate,
    ColumnPropertyCandidate,
    MeshTriple,
    TableGrid,
    TableInterpretationMesh,
)
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner


class RelationalMeshSolver:
    """Relational Mesh Constraint Solver performing joint optimization over CEA, CTA, and CPA."""

    def __init__(
        self,
        reasoner: SymbolicAxiomReasoner,
        lambda_cta: float = 1.0,
        lambda_cpa: float = 1.0,
        lambda_axiom: float = 1.5,
        prune_disjoint: bool = True,
    ) -> None:
        """Initialize solver with reasoner and objective hyperparameters."""
        self.reasoner = reasoner
        self.lambda_cta = lambda_cta
        self.lambda_cpa = lambda_cpa
        self.lambda_axiom = lambda_axiom
        self.prune_disjoint = prune_disjoint

    def solve(
        self,
        table: TableGrid,
        cell_candidates: dict[tuple[int, int], CellCandidateList],
        column_types: dict[int, list[ColumnTypeCandidate]],
        column_properties: dict[tuple[int, int], list[ColumnPropertyCandidate]],
    ) -> TableInterpretationMesh:
        """Solve joint relational mesh constraint optimization.

        Objective:
            TotalScore(M) = sum(CEA) + lambda_cta * sum(CTA) + lambda_cpa * sum(CPA)
                            + lambda_axiom * sum(AxiomBonus(Cell(r, c1), P(c1, c2), Cell(r, c2)))
        """
        solver_log: list[str] = []
        solver_log.append(f"Starting Relational Mesh Solver for table with {table.num_rows} rows, {table.num_cols} cols.")

        # Step 1: Select Best Column Types (CTA)
        chosen_column_types: dict[int, ColumnTypeCandidate] = {}
        for col_idx in range(table.num_cols):
            cands = column_types.get(col_idx, [])
            if cands:
                chosen_column_types[col_idx] = cands[0]
                solver_log.append(
                    f"Col {col_idx} ('{table.headers[col_idx] if col_idx < len(table.headers) else ''}') "
                    f"-> Type: {cands[0].class_label} ({cands[0].class_iri}) [conf={cands[0].confidence:.2f}]"
                )

        # Step 2: Select Best Column Properties (CPA) with Domain/Range Consistency
        chosen_column_relations: dict[tuple[int, int], ColumnPropertyCandidate] = {}
        num_cols = table.num_cols

        for i in range(num_cols):
            for j in range(num_cols):
                if i == j:
                    continue
                pair_cands = column_properties.get((i, j), [])
                if not pair_cands:
                    continue

                best_prop: ColumnPropertyCandidate | None = None
                best_prop_score = -999.0

                type_i = chosen_column_types.get(i)
                type_j = chosen_column_types.get(j)

                for prop_cand in pair_cands:
                    score = prop_cand.confidence
                    # Check domain/range consistency with chosen column types
                    if type_i and prop_cand.domain_iri:
                        if not self.reasoner.is_subclass_of(type_i.class_iri, prop_cand.domain_iri):
                            if self.reasoner.are_disjoint(type_i.class_iri, prop_cand.domain_iri):
                                score -= 2.0
                            else:
                                score -= 0.3

                    if type_j and prop_cand.range_iri:
                        if not self.reasoner.is_subclass_of(type_j.class_iri, prop_cand.range_iri):
                            if self.reasoner.are_disjoint(type_j.class_iri, prop_cand.range_iri):
                                score -= 2.0
                            else:
                                score -= 0.3

                    if score > best_prop_score:
                        best_prop_score = score
                        best_prop = prop_cand

                if best_prop and best_prop_score > 0.15:
                    chosen_column_relations[(i, j)] = best_prop
                    solver_log.append(
                        f"Relation ({i} -> {j}) -> Property: {best_prop.property_label} "
                        f"({best_prop.property_iri}) [conf={best_prop.confidence:.2f}, support={best_prop.row_support_count}]"
                    )

        # Step 3: Joint Cell Entity Disambiguation (Relational Mesh Optimization per Row)
        resolved_cells: dict[tuple[int, int], CellCandidate] = {}
        extracted_triples: list[MeshTriple] = []

        total_cea_score = 0.0
        total_axiom_bonus = 0.0

        for r_idx in range(table.num_rows):
            col_candidates_list: list[list[CellCandidate]] = []
            for c_idx in range(num_cols):
                cell_list = cell_candidates.get((r_idx, c_idx))
                if cell_list and cell_list.candidates:
                    col_type = chosen_column_types.get(c_idx)
                    filtered = []
                    for cand in cell_list.candidates:
                        is_disjoint = False
                        if self.prune_disjoint and col_type:
                            for t in cand.types:
                                if self.reasoner.are_disjoint(t, col_type.class_iri):
                                    is_disjoint = True
                                    break
                        if not is_disjoint:
                            filtered.append(cand)
                    col_candidates_list.append(filtered if filtered else cell_list.candidates[:1])
                else:
                    col_candidates_list.append([])

            active_cols = [c for c in range(num_cols) if col_candidates_list[c]]
            best_row_assignment: dict[int, CellCandidate] = {}
            best_row_score = -1e9
            best_row_triples: list[MeshTriple] = []

            relational_cols = {ci for ci, _ in chosen_column_relations.keys()} | {cj for _, cj in chosen_column_relations.keys()}
            options: list[list[CellCandidate]] = []
            for c in active_cols:
                cands = col_candidates_list[c]
                if c in relational_cols:
                    options.append(cands[:3])
                else:
                    options.append(cands[:1])

            # Safety cap on total combinations per row
            total_combos = 1
            for opt in options:
                total_combos *= max(1, len(opt))
            if total_combos > 128:
                options = [opt[:2] if c in relational_cols else opt[:1] for c, opt in zip(active_cols, options)]

            for combo in itertools.product(*options):
                assignment = {c_idx: cand for c_idx, cand in zip(active_cols, combo)}
                row_cea = sum(cand.score for cand in assignment.values())
                row_axiom = 0.0
                combo_triples: list[MeshTriple] = []

                # Column coherence bonus
                coherence_bonus = 0.0
                for c_idx, cand in assignment.items():
                    col_type = chosen_column_types.get(c_idx)
                    if col_type:
                        if any(self.reasoner.is_subclass_of(t, col_type.class_iri) for t in cand.types):
                            coherence_bonus += 0.25
                        elif any(self.reasoner.are_disjoint(t, col_type.class_iri) for t in cand.types):
                            coherence_bonus -= 1.0

                # Evaluate pairwise relational mesh axioms across columns
                for (ci, cj), prop in chosen_column_relations.items():
                    if ci in assignment and cj in assignment:
                        cand_i = assignment[ci]
                        cand_j = assignment[cj]

                        axiom_score = self.reasoner.evaluate_axiom_bonus(
                            subject_iri=cand_i.entity_iri,
                            predicate_iri=prop.property_iri,
                            object_iri=cand_j.entity_iri,
                            subject_types=cand_i.types,
                            object_types=cand_j.types,
                        )
                        row_axiom += axiom_score

                        if self.reasoner.has_triple(cand_i.entity_iri, prop.property_iri, cand_j.entity_iri):
                            origin = "direct_ontology"
                            conf = 1.0
                        elif axiom_score > 0.0:
                            origin = "inferred_cpa"
                            conf = float(min(1.0, (cand_i.score + cand_j.score + prop.confidence) / 3.0))
                        else:
                            origin = "tentative"
                            conf = 0.4

                        combo_triples.append(
                            MeshTriple(
                                subject_iri=cand_i.entity_iri,
                                subject_label=cand_i.label,
                                predicate_iri=prop.property_iri,
                                predicate_label=prop.property_label,
                                object_iri=cand_j.entity_iri,
                                object_label=cand_j.label,
                                row_idx=r_idx,
                                subject_col=ci,
                                object_col=cj,
                                confidence=conf,
                                triple_origin=origin,
                            )
                        )

                total_combo_score = row_cea + coherence_bonus + self.lambda_axiom * row_axiom
                if total_combo_score > best_row_score:
                    best_row_score = total_combo_score
                    best_row_assignment = assignment
                    best_row_triples = combo_triples

            for c_idx, resolved_cand in best_row_assignment.items():
                resolved_cells[(r_idx, c_idx)] = resolved_cand
                total_cea_score += resolved_cand.score

                original_top = col_candidates_list[c_idx][0] if col_candidates_list[c_idx] else None
                if original_top and original_top.entity_iri != resolved_cand.entity_iri:
                    solver_log.append(
                        f"Row {r_idx}, Col {c_idx}: Disambiguated '{original_top.label}' ({original_top.entity_iri}) "
                        f"-> '{resolved_cand.label}' ({resolved_cand.entity_iri}) via Relational Mesh!"
                    )

            extracted_triples.extend(best_row_triples)
            total_axiom_bonus += max(0.0, best_row_score - sum(c.score for c in best_row_assignment.values()))

        # Step 4: Overall Confidence and Score Breakdown
        total_cta_score = sum(ct.confidence for ct in chosen_column_types.values())
        total_cpa_score = sum(cp.confidence for cp in chosen_column_relations.values())

        total_score = (
            total_cea_score
            + self.lambda_cta * total_cta_score
            + self.lambda_cpa * total_cpa_score
            + self.lambda_axiom * total_axiom_bonus
        )

        normalized_confidence = min(
            1.0,
            max(
                0.0,
                (total_cea_score / max(1, len(resolved_cells)) if resolved_cells else 0.5) * 0.4
                + (total_cta_score / max(1, len(chosen_column_types)) if chosen_column_types else 0.5) * 0.3
                + (total_cpa_score / max(1, len(chosen_column_relations)) if chosen_column_relations else 0.5) * 0.3,
            ),
        )

        solver_log.append(
            f"Relational Mesh Solved: {len(resolved_cells)} cells resolved, "
            f"{len(chosen_column_types)} column types, {len(chosen_column_relations)} relations, "
            f"{len(extracted_triples)} row triples extracted. Confidence={normalized_confidence:.2f}"
        )

        return TableInterpretationMesh(
            table=table,
            cell_annotations=resolved_cells,
            column_types=chosen_column_types,
            column_relations=chosen_column_relations,
            row_triples=extracted_triples,
            overall_confidence=float(normalized_confidence),
            score_breakdown={
                "cea_score": float(total_cea_score),
                "cta_score": float(total_cta_score),
                "cpa_score": float(total_cpa_score),
                "axiom_bonus": float(total_axiom_bonus),
                "total_joint_score": float(total_score),
            },
            solver_log=solver_log,
        )
