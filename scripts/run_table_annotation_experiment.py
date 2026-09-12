#!/usr/bin/env python3
"""Adversarial Semantic Table Interpretation Benchmark Experiment for GW2-UME.

Evaluates the 3-phase SemanticTableAnnotator against adversarial tables containing:
- Colloquial synonyms (e.g. artwork_uri -> priory:icon, ping_code -> priory:chatCode)
- Deceptive headers / false friends (e.g. armor_defense -> priory:minWeaponPower, item_rank -> priory:hasVendorValue)
- Opaque machine headers (e.g. col_02 -> priory:gw2Id, col_04 -> priory:itemFlags, col_14 -> priory:requiredRating)
- Standard headers (e.g. damage_type -> priory:damageType)

Evaluates:
- Column Property Annotation (CPA) accuracy
- Subject Entity Clustering accuracy
- Deceptive header catch rate
- Multi-phase resolution distribution
- Inter-entity relational consistency (priory:producesItem)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Union

from gw2_ume.pipeline.semantic_table_annotator import SemanticTableAnnotator, TableAnnotationResult


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_experiment(
    table_path: Union[Path, str] = "data/sample_tables/adversarial_table.csv",
    ground_truth_path: Union[Path, str] = "data/benchmarks/ground_truth_adversarial_schema.json",
    output_path: Union[Path, str] = "output/experiment_results.json",
) -> Dict[str, Any]:
    table_p = Path(table_path)
    if not table_p.is_absolute():
        table_p = REPO_ROOT / table_p

    gt_p = Path(ground_truth_path)
    if not gt_p.is_absolute():
        gt_p = REPO_ROOT / gt_p

    out_p = Path(output_path)
    if not out_p.is_absolute():
        out_p = REPO_ROOT / out_p

    if not table_p.exists():
        raise FileNotFoundError(f"Table file not found: {table_p.resolve()}")
    if not gt_p.exists():
        raise FileNotFoundError(f"Ground truth file not found: {gt_p.resolve()}")

    with open(gt_p, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    gt_columns = {col["column_index"]: col for col in ground_truth["columns"]}

    print("=" * 80)
    print("GW2-UME — 3-PHASE SEMANTIC TABLE INTERPRETATION EXPERIMENT")
    print("=" * 80)
    print(f"Table Path:        {table_p}")
    print(f"Ground Truth Path: {gt_p}")
    print(f"Output Path:       {out_p}")
    print("Initializing SemanticTableAnnotator (zero hardcoded domain semantics)...")

    annotator = SemanticTableAnnotator()
    print("Running 3-phase neuro-symbolic table annotation pipeline...")

    t0 = time.perf_counter()
    result: TableAnnotationResult = annotator.annotate(table_p)
    duration = time.perf_counter() - t0

    # Evaluate each column prediction
    evaluation_columns = []
    correct_props = 0
    correct_subjects = 0
    type_stats: Dict[str, Dict[str, int]] = {}

    print("\n" + "-" * 110)
    print(f"{'Idx':<4} {'Header':<22} {'Predicted Property':<26} {'True Property':<26} {'Phase':<12} {'Match':<6}")
    print("-" * 110)

    for col in result.columns:
        idx = col.column_index
        gt = gt_columns.get(idx, {})
        true_prop = gt.get("true_property_uri", "")
        true_subj = gt.get("true_subject_class", "")
        header_type = gt.get("header_type", "unknown")

        prop_match = (col.predicted_property_uri == true_prop)
        subj_match = (col.predicted_subject_class == true_subj)

        if prop_match:
            correct_props += 1
        if subj_match:
            correct_subjects += 1

        type_stats.setdefault(header_type, {"total": 0, "correct_prop": 0, "correct_subj": 0})
        type_stats[header_type]["total"] += 1
        if prop_match:
            type_stats[header_type]["correct_prop"] += 1
        if subj_match:
            type_stats[header_type]["correct_subj"] += 1

        phase_short = (
            "Phase 1" if "Phase 1" in col.resolution_phase
            else ("Phase 2" if "Phase 2" in col.resolution_phase else "Phase 3")
        )
        match_symbol = "PASS" if (prop_match and subj_match) else "FAIL"

        print(f"{idx:<4} {col.header:<22} {col.predicted_property_uri:<26} {true_prop:<26} {phase_short:<12} {match_symbol:<6}")

        evaluation_columns.append({
            "column_index": idx,
            "header": col.header,
            "header_type": header_type,
            "predicted_property_uri": col.predicted_property_uri,
            "true_property_uri": true_prop,
            "property_match": prop_match,
            "predicted_subject_class": col.predicted_subject_class,
            "true_subject_class": true_subj,
            "subject_match": subj_match,
            "resolution_phase": col.resolution_phase,
            "confidence": col.confidence,
            "explanation": col.explanation,
            "is_false_friend": col.is_false_friend,
            "false_friend_explanation": col.false_friend_explanation,
        })

    total_cols = len(result.columns)
    cpa_acc = (correct_props / total_cols) * 100 if total_cols > 0 else 0.0
    cta_acc = (correct_subjects / total_cols) * 100 if total_cols > 0 else 0.0

    print("-" * 110)
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY RESULTS")
    print("=" * 80)
    print(f"Total Rows:                         {result.row_count}")
    print(f"Total Columns:                      {total_cols}")
    print(f"Property Annotation Accuracy (CPA): {correct_props}/{total_cols} ({cpa_acc:.1f}%)")
    print(f"Subject Clustering Accuracy (CTA):  {correct_subjects}/{total_cols} ({cta_acc:.1f}%)")
    print(f"Deceptive Headers Caught:           {result.deceptive_headers_caught}")
    print(f"Execution Duration:                 {duration:.3f} seconds")

    print("\nAccuracy Breakdown by Header Type:")
    for htype, stats in sorted(type_stats.items()):
        tot = stats["total"]
        cp = stats["correct_prop"]
        pct = (cp / tot * 100) if tot > 0 else 0.0
        print(f"  - {htype.capitalize():<12}: {cp}/{tot} ({pct:.1f}%)")

    print("\nPhase Resolution Distribution:")
    for phase_name, count in result.phase_counts.items():
        print(f"  - {phase_name}: {count} columns")

    print("\nInter-Entity Relations Verified:")
    for rel in result.inter_entity_relations:
        print(f"  - {rel['relation_uri']}: {rel['subject_class']} -> {rel['object_class']} (conf={rel['confidence']:.2f})")
        print(f"    {rel['explanation']}")

    experiment_data = {
        "metadata": {
            "dataset_name": ground_truth.get("metadata", {}).get("dataset_name", "ASTI-GW2"),
            "table_path": str(table_p),
            "ground_truth_path": str(gt_p),
            "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "execution_duration_seconds": round(duration, 4),
        },
        "metrics": {
            "row_count": result.row_count,
            "column_count": total_cols,
            "cpa_correct": correct_props,
            "cpa_total": total_cols,
            "cpa_accuracy": round(cpa_acc, 2),
            "cta_correct": correct_subjects,
            "cta_total": total_cols,
            "cta_accuracy": round(cta_acc, 2),
            "deceptive_headers_caught": result.deceptive_headers_caught,
            "header_type_breakdown": {
                htype: {
                    "total": stats["total"],
                    "correct": stats["correct_prop"],
                    "accuracy": round(stats["correct_prop"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0.0,
                }
                for htype, stats in type_stats.items()
            },
            "phase_counts": result.phase_counts,
        },
        "inter_entity_relations": result.inter_entity_relations,
        "column_evaluations": evaluation_columns,
    }

    try:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(experiment_data, f, indent=2)
        print(f"\n[OK] Experiment results saved to {out_p.resolve()}")
    except PermissionError:
        print(f"\n[Notice] Could not write to {out_p} directly due to sandbox file permissions.")

    return experiment_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Semantic Table Interpretation benchmark experiment.")
    parser.add_argument("--table", default="data/sample_tables/adversarial_table.csv", help="Path to table CSV file")
    parser.add_argument("--ground-truth", default="data/benchmarks/ground_truth_adversarial_schema.json", help="Path to ground truth JSON")
    parser.add_argument("--output", default="output/experiment_results.json", help="Path to output JSON")
    args = parser.parse_args()

    run_experiment(args.table, args.ground_truth, args.output)
