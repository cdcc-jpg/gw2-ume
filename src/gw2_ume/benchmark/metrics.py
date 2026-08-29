"""Metrics and evaluation scores for the Proof-of-Value Benchmark."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any


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


__all__ = ["BenchmarkScore", "BenchmarkSummary"]
