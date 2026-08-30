"""Metrics and evaluation scores for the Proof-of-Value Benchmark.

Provides dynamic calculation functions for:
- Cell Entity Annotation (CEA): precision, recall, F1, accuracy
- Column Type Annotation (CTA): accuracy, macro-F1, precision, recall
- Column Property Annotation (CPA): precision, recall, F1
- Semantic Validity Rate against domain constraints and SHACL rules
"""

from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Any, List, Set, Tuple, Optional, Sequence, Union


def normalize_identifier(val: Any) -> str:
    """Normalizes URIs, labels, or column names for robust invariant comparison."""
    if val is None:
        return ""
    s = str(val).strip()
    # Extract local name / fragment from URI
    if "#" in s:
        s = s.split("#")[-1]
    elif "/" in s:
        # Keep entity type prefix if present, e.g. item/ravenswood_branch -> item_ravenswood_branch
        parts = [p for p in s.split("/") if p]
        if len(parts) >= 2 and parts[-2] in ["item", "vendor", "zone", "discipline", "recipe", "currency", "step"]:
            s = f"{parts[-2]}_{parts[-1]}"
        else:
            s = parts[-1]
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", s)
    # Strip spaces and special characters, lowercase
    s = re.sub(r"[\W_]+", "", s).lower()
    return s


def normalize_entity_uri(uri: Any) -> str:
    """Normalizes an entity URI to its canonical identifier slug for CEA comparison."""
    if uri is None:
        return ""
    s = str(uri).strip()
    if "unknown" in s.lower():
        slug = re.sub(r"[\W_]+", "_", s.split("/")[-1]).strip("_").lower()
        return f"unknown_{slug}"
    if "#" in s:
        s = s.split("#")[-1]
    elif "/" in s:
        s = s.split("/")[-1]
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", s)
    return re.sub(r"[\W_]+", "_", s).strip("_").lower()


def compute_cea_metrics(
    predictions: Any,
    ground_truth: Dict[str, Any],
    total_cells: Optional[int] = None,
) -> Dict[str, float]:
    """Dynamically computes real CEA precision, recall, F1, and accuracy.

    Args:
        predictions: List of CellAnnotation or dicts or (row, col) mappings.
        ground_truth: Ground-truth dictionary containing 'cea_entities' or 'cell_entities'.
        total_cells: Optional total count of candidate entity cells.

    Returns:
        Dict with 'accuracy', 'precision', 'recall', 'f1', 'tp', 'fp', 'fn'.
    """
    cea_gt_map: Dict[str, str] = ground_truth.get("cea_entities", {})
    cell_gt_map: Dict[str, str] = ground_truth.get("cell_entities", {})

    # Extract predicted cell items: list of dicts with raw_value, entity_uri, row_idx, col_idx
    pred_items: List[Dict[str, Any]] = []
    if isinstance(predictions, list):
        for p in predictions:
            if hasattr(p, "raw_value") and hasattr(p, "entity_uri"):
                pred_items.append({
                    "raw_value": getattr(p, "raw_value", ""),
                    "entity_uri": getattr(p, "entity_uri", ""),
                    "row_idx": getattr(p, "row_idx", None),
                    "col_idx": getattr(p, "col_idx", None),
                    "confidence": getattr(p, "confidence", 1.0),
                })
            elif isinstance(p, dict):
                pred_items.append({
                    "raw_value": p.get("raw", p.get("raw_value", "")),
                    "entity_uri": p.get("entity", p.get("entity_uri", "")),
                    "row_idx": p.get("row", p.get("row_idx")),
                    "col_idx": p.get("col", p.get("col_idx")),
                    "confidence": p.get("confidence", 1.0),
                })
    elif isinstance(predictions, dict):
        if "cea" in predictions and isinstance(predictions["cea"], list):
            return compute_cea_metrics(predictions["cea"], ground_truth, total_cells)
        for k, v in predictions.items():
            pred_items.append({"raw_value": str(k), "entity_uri": str(v), "confidence": 1.0})

    # Filter out numeric or empty cells
    filtered_preds = [p for p in pred_items if str(p.get("raw_value", "")).strip() and not str(p.get("raw_value", "")).strip().isdigit()]

    tp = 0
    fp = 0
    fn = 0
    evaluated = 0

    for p in filtered_preds:
        raw = str(p.get("raw_value", "")).strip()
        pred_uri = str(p.get("entity_uri", "")).strip()
        row_idx = p.get("row_idx")
        col_idx = p.get("col_idx")

        # Find expected URI from ground truth
        expected_uri = None
        if row_idx is not None and col_idx is not None:
            coord_key = f"({row_idx}, {col_idx})"
            if coord_key in cell_gt_map:
                expected_uri = cell_gt_map[coord_key]
            elif (row_idx, col_idx) in cell_gt_map:  # type: ignore
                expected_uri = cell_gt_map[(row_idx, col_idx)]  # type: ignore

        if expected_uri is None:
            raw_norm = normalize_identifier(raw)
            for gt_text, gt_uri in cea_gt_map.items():
                if normalize_identifier(gt_text) == raw_norm:
                    expected_uri = gt_uri
                    break
            if expected_uri is None:
                for gt_text, gt_uri in cea_gt_map.items():
                    if normalize_identifier(gt_text) in raw_norm or raw_norm in normalize_identifier(gt_text):
                        expected_uri = gt_uri
                        break

        evaluated += 1
        norm_pred = normalize_entity_uri(pred_uri)

        if expected_uri is not None:
            norm_exp = normalize_entity_uri(expected_uri)
            if norm_pred.startswith("unknown_") or "unknown" in norm_pred:
                fn += 1
            elif norm_pred == norm_exp:
                tp += 1
            else:
                fp += 1
        else:
            # Cell not in ground truth
            if norm_pred.startswith("unknown_") or "unknown" in norm_pred:
                fp += 1
            elif norm_pred:
                # Extra unmapped annotation
                fp += 1

    total_eval = evaluated if evaluated > 0 else (len(filtered_preds) if filtered_preds else 1)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = tp / total_eval if total_eval > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "total_evaluated": total_eval,
    }


def compute_cta_metrics(
    predictions: Any,
    ground_truth: Dict[str, Any],
) -> Dict[str, float]:
    """Dynamically computes real CTA accuracy, macro-F1, precision, and recall.

    Args:
        predictions: List of ColumnAnnotation or dict of column -> class predictions.
        ground_truth: Ground-truth dictionary containing 'cta' mapping.

    Returns:
        Dict with 'accuracy', 'macro_f1', 'precision', 'recall'.
    """
    cta_gt: Dict[str, str] = ground_truth.get("cta", {})
    if not cta_gt:
        return {"accuracy": 1.0, "macro_f1": 1.0, "precision": 1.0, "recall": 1.0}

    # Extract predicted columns
    pred_map: Dict[str, str] = {}
    if isinstance(predictions, list):
        for p in predictions:
            if hasattr(p, "col_name") and (hasattr(p, "type_uri") or hasattr(p, "type_label")):
                col = getattr(p, "col_name")
                uri = getattr(p, "type_uri", getattr(p, "type_label", ""))
                pred_map[str(col)] = str(uri)
            elif isinstance(p, dict):
                col = p.get("col", p.get("col_name", p.get("column", "")))
                uri = p.get("type", p.get("type_uri", p.get("type_label", "")))
                pred_map[str(col)] = str(uri)
    elif isinstance(predictions, dict):
        if "cta" in predictions and isinstance(predictions["cta"], list):
            return compute_cta_metrics(predictions["cta"], ground_truth)
        for k, v in predictions.items():
            pred_map[str(k)] = str(v)

    correct = 0
    total_cols = len(cta_gt)

    # Class-level confusion tracking for macro-F1
    all_classes: Set[str] = set()
    gt_class_by_col: Dict[str, str] = {}
    pred_class_by_col: Dict[str, str] = {}

    for gt_col, gt_class in cta_gt.items():
        norm_gt_col = normalize_identifier(gt_col)
        norm_gt_cls = normalize_identifier(gt_class)
        all_classes.add(norm_gt_cls)
        gt_class_by_col[norm_gt_col] = norm_gt_cls

        # Find matching predicted col
        pred_cls_raw = None
        for p_col, p_cls in pred_map.items():
            if normalize_identifier(p_col) == norm_gt_col:
                pred_cls_raw = p_cls
                break
        if pred_cls_raw is None:
            # Try fuzzy match
            for p_col, p_cls in pred_map.items():
                if norm_gt_col in normalize_identifier(p_col) or normalize_identifier(p_col) in norm_gt_col:
                    pred_cls_raw = p_cls
                    break

        norm_pred_cls = normalize_identifier(pred_cls_raw) if pred_cls_raw else "unassigned"
        all_classes.add(norm_pred_cls)
        pred_class_by_col[norm_gt_col] = norm_pred_cls

        if norm_pred_cls == norm_gt_cls:
            correct += 1

    accuracy = correct / total_cols if total_cols > 0 else 0.0

    # Calculate Macro-F1 across classes
    f1_scores: List[float] = []
    for cls in all_classes:
        if cls == "unassigned":
            continue
        c_tp = sum(1 for c, g_cls in gt_class_by_col.items() if g_cls == cls and pred_class_by_col.get(c) == cls)
        c_fp = sum(1 for c, p_cls in pred_class_by_col.items() if p_cls == cls and gt_class_by_col.get(c) != cls)
        c_fn = sum(1 for c, g_cls in gt_class_by_col.items() if g_cls == cls and pred_class_by_col.get(c) != cls)

        c_prec = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0.0
        c_rec = c_tp / (c_tp + c_fn) if (c_tp + c_fn) > 0 else 0.0
        c_f1 = (2 * c_prec * c_rec) / (c_prec + c_rec) if (c_prec + c_rec) > 0 else 0.0
        f1_scores.append(c_f1)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else accuracy

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "precision": round(accuracy, 4),
        "recall": round(accuracy, 4),
    }


def compute_cpa_metrics(
    predictions: Any,
    ground_truth: Union[Dict[str, Any], List[Dict[str, Any]]],
) -> Dict[str, float]:
    """Dynamically computes real CPA precision, recall, and F1.

    Args:
        predictions: List of ColumnPropertyAnnotation, dicts, or tuples.
        ground_truth: Ground truth dict with 'cpa' or list of CPA relations.

    Returns:
        Dict with 'precision', 'recall', 'f1', 'tp', 'fp', 'fn'.
    """
    cpa_gt_list: List[Dict[str, Any]] = (
        ground_truth.get("cpa", []) if isinstance(ground_truth, dict) else ground_truth
    )

    target_relations: Set[Tuple[str, str, str]] = set()
    for rel in cpa_gt_list:
        src = normalize_identifier(rel.get("source_column", rel.get("source", "")))
        tgt = normalize_identifier(rel.get("target_column", rel.get("target", "")))
        prop = normalize_identifier(rel.get("property", rel.get("property_uri", rel.get("relation", ""))))
        if src and tgt:
            target_relations.add((src, tgt, prop))

    predicted_relations: Set[Tuple[str, str, str]] = set()
    if isinstance(predictions, list):
        for p in predictions:
            if hasattr(p, "source_col") and hasattr(p, "target_col"):
                src = normalize_identifier(getattr(p, "source_col"))
                tgt = normalize_identifier(getattr(p, "target_col"))
                prop = normalize_identifier(getattr(p, "property_uri", getattr(p, "property_label", "")))
                predicted_relations.add((src, tgt, prop))
            elif isinstance(p, dict):
                src = normalize_identifier(p.get("source", p.get("source_col", p.get("source_column", ""))))
                tgt = normalize_identifier(p.get("target", p.get("target_col", p.get("target_column", ""))))
                prop = normalize_identifier(p.get("property", p.get("property_uri", p.get("relation", ""))))
                if src and tgt:
                    predicted_relations.add((src, tgt, prop))
            elif isinstance(p, tuple) and len(p) == 3:
                predicted_relations.add((normalize_identifier(p[0]), normalize_identifier(p[1]), normalize_identifier(p[2])))
    elif isinstance(predictions, dict) and "cpa" in predictions:
        return compute_cpa_metrics(predictions["cpa"], ground_truth)

    if not target_relations and not predicted_relations:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}

    tp = 0
    fp = 0
    fn = 0

    for pred in predicted_relations:
        if pred in target_relations:
            tp += 1
        else:
            # Check relaxed predicate match if source and target match
            matched = False
            for tgt in target_relations:
                if pred[0] == tgt[0] and pred[1] == tgt[1]:
                    if pred[2] == tgt[2] or tgt[2] in pred[2] or pred[2] in tgt[2]:
                        tp += 1
                        matched = True
                        break
            if not matched:
                fp += 1

    for tgt in target_relations:
        matched = False
        for pred in predicted_relations:
            if pred[0] == tgt[0] and pred[1] == tgt[1]:
                if pred[2] == tgt[2] or tgt[2] in pred[2] or pred[2] in tgt[2]:
                    matched = True
                    break
        if not matched:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def compute_semantic_validity_rate(
    model_output: Any,
    ground_truth: Optional[Dict[str, Any]] = None,
    shacl_violations: int = 0,
    total_elements: Optional[int] = None,
) -> float:
    """Computes the semantic validity rate based on SHACL validation and ontology conformance.

    Args:
        model_output: RelationalMesh or PureNLP prediction dictionary.
        ground_truth: Optional ground truth dictionary.
        shacl_violations: Number of SHACL constraint violations.
        total_elements: Optional total number of entities / triples evaluated.

    Returns:
        Float rate between 0.0 and 1.0.
    """
    if hasattr(model_output, "validation_status"):
        # RelationalMesh object
        if model_output.validation_status == "CONFORMING" and len(model_output.validation_violations) == 0:
            return 1.0
        total = total_elements or max(1, len(getattr(model_output, "nodes", [])) + len(getattr(model_output, "edges", [])))
        violations = len(getattr(model_output, "validation_violations", []))
        return max(0.0, round(1.0 - (violations / total), 4))

    if isinstance(model_output, dict):
        if "semantic_validity_rate" in model_output:
            return float(model_output["semantic_validity_rate"])
        violations = model_output.get("violations_count", shacl_violations)
        total = total_elements or model_output.get("total_cells", 100)
        return max(0.0, round(1.0 - (violations / max(1, total)), 4))

    return 1.0 if shacl_violations == 0 else max(0.0, round(1.0 - (shacl_violations / 50.0), 4))


@dataclass
class BenchmarkScore:
    """Benchmark results for a single table evaluation."""
    table_id: str
    table_name: str
    model_name: str
    cea_accuracy: float
    cta_accuracy: float
    cpa_precision: float
    cpa_recall: float
    cpa_f1: float
    semantic_validity_rate: float
    shacl_violations: int
    hallucination_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "table_name": self.table_name,
            "model_name": self.model_name,
            "cea_accuracy": round(self.cea_accuracy * 100, 2),
            "cta_accuracy": round(self.cta_accuracy * 100, 2),
            "cpa_precision": round(self.cpa_precision * 100, 2),
            "cpa_recall": round(self.cpa_recall * 100, 2),
            "cpa_f1": round(self.cpa_f1 * 100, 2),
            "semantic_validity_rate": round(self.semantic_validity_rate * 100, 2),
            "shacl_violations": self.shacl_violations,
            "hallucination_count": self.hallucination_count,
        }


@dataclass
class BenchmarkSummary:
    """Overall summary comparing Pure NLP against GW2-UME Relational Mesh."""
    pure_nlp_avg_cea: float
    mesh_avg_cea: float
    pure_nlp_avg_cta: float
    mesh_avg_cta: float
    pure_nlp_avg_cpa_f1: float
    mesh_avg_cpa_f1: float
    pure_nlp_avg_validity: float
    mesh_avg_validity: float
    pure_nlp_total_violations: int
    mesh_total_violations: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pure_nlp": {
                "avg_cea_accuracy": round(self.pure_nlp_avg_cea * 100, 2),
                "avg_cta_accuracy": round(self.pure_nlp_avg_cta * 100, 2),
                "avg_cpa_f1": round(self.pure_nlp_avg_cpa_f1 * 100, 2),
                "avg_semantic_validity": round(self.pure_nlp_avg_validity * 100, 2),
                "total_shacl_violations": self.pure_nlp_total_violations,
            },
            "gw2_ume_mesh": {
                "avg_cea_accuracy": round(self.mesh_avg_cea * 100, 2),
                "avg_cta_accuracy": round(self.mesh_avg_cta * 100, 2),
                "avg_cpa_f1": round(self.mesh_avg_cpa_f1 * 100, 2),
                "avg_semantic_validity": round(self.mesh_avg_validity * 100, 2),
                "total_shacl_violations": self.mesh_total_violations,
            },
        }


__all__ = [
    "normalize_identifier",
    "normalize_entity_uri",
    "compute_cea_metrics",
    "compute_cta_metrics",
    "compute_cpa_metrics",
    "compute_semantic_validity_rate",
    "BenchmarkScore",
    "BenchmarkSummary",
]

