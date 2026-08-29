"""Benchmark runner executing Head-to-Head Proof-of-Value evaluations across multiple game domains."""

from __future__ import annotations
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from gw2_ume.mesh.annotator import parse_table_content
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.neurosymbolic.baseline_nlp import PureNLPBaseline
from gw2_ume.neurosymbolic.pingpong import NeuroSymbolicPingPongEngine
from gw2_ume.benchmark.metrics import (
    BenchmarkScore,
    BenchmarkSummary,
    compute_cea_metrics,
    compute_cta_metrics,
    compute_cpa_metrics,
    compute_semantic_validity_rate,
)


class BenchmarkRunner:
    """Harness that evaluates tables across both Pure NLP and GW2-UME Semantic Mesh."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            # Default to repo root / data
            self.data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)

        self.tables_dir = self.data_dir / "sample_tables"
        self.benchmarks_dir = self.data_dir / "benchmarks"
        self.pure_nlp = PureNLPBaseline()
        self.pingpong = NeuroSymbolicPingPongEngine()

    def _load_ground_truth(self, table_id: str, table_path: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """Loads ground truth annotations for a specific benchmark table."""
        # 1. Check direct filename match in benchmarks dir
        direct_candidates = [
            self.benchmarks_dir / f"ground_truth_{table_id}.json",
            self.benchmarks_dir / f"ground_truth_{re.sub(r'^bench_', '', table_id)}.json",
        ]
        for cand in direct_candidates:
            if cand.exists():
                with open(cand, "r", encoding="utf-8") as f:
                    return json.load(f)

        # 2. Check benchmark_suite.json for ground_truth_path
        suite_file = self.benchmarks_dir / "benchmark_suite.json"
        if suite_file.exists():
            with open(suite_file, "r", encoding="utf-8") as f:
                suite_data = json.load(f)
            for b in suite_data.get("benchmarks", []):
                if b["id"] == table_id or Path(b.get("table_path", "")).name == Path(table_path).name:
                    gt_path_str = b.get("ground_truth_path")
                    if gt_path_str:
                        gt_path = Path(gt_path_str)
                        if not gt_path.is_absolute():
                            gt_path = self.data_dir.parent / gt_path_str
                        if gt_path.exists():
                            with open(gt_path, "r", encoding="utf-8") as f:
                                return json.load(f)

        # 3. Match by table name keywords
        table_name_lower = Path(table_path).stem.lower()
        if "nevermore" in table_name_lower:
            cand = self.benchmarks_dir / "ground_truth_nevermore.json"
        elif "hope" in table_name_lower or "bifrost" in table_name_lower:
            cand = self.benchmarks_dir / "ground_truth_hope_bifrost.json"
        elif "skyscale" in table_name_lower:
            cand = self.benchmarks_dir / "ground_truth_skyscale.json"
        elif "crafting" in table_name_lower or "discipline" in table_name_lower:
            cand = self.benchmarks_dir / "ground_truth_crafting_discipline_materials.json"
        elif "noisy" in table_name_lower or "tribute" in table_name_lower:
            cand = self.benchmarks_dir / "ground_truth_noisy_tribute.json"
        elif "ambiguous" in table_name_lower:
            cand = self.benchmarks_dir / "ground_truth_ambiguous_matrix.json"
        else:
            cand = self.benchmarks_dir / "ground_truth_nevermore.json"

        if cand.exists():
            with open(cand, "r", encoding="utf-8") as f:
                return json.load(f)

        return {}

    def run_table_benchmark(
        self,
        table_path: str,
        table_id: str,
        table_name: str,
        domain: Optional[str] = None,
    ) -> Tuple[BenchmarkScore, BenchmarkScore]:
        """Runs dynamic ground-truth evaluation on a table for both Pure NLP and GW2-UME Mesh."""
        path = Path(table_path)
        if not path.is_absolute():
            path = self.data_dir.parent / table_path
        if not path.exists():
            # Fallback to tables_dir
            candidate = self.tables_dir / Path(table_path).name
            if candidate.exists():
                path = candidate

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        headers, rows = parse_table_content(content, table_name)
        total_cells = sum(len(r) for r in rows)

        # Load ground truth for this benchmark
        ground_truth = self._load_ground_truth(table_id, table_path, domain=domain)

        # 1. Run Pure NLP Baseline & Dynamically Compute Metrics
        nlp_res = self.pure_nlp.predict_table(content, table_name)
        nlp_cea_metrics = compute_cea_metrics(nlp_res.get("cea", []), ground_truth, total_cells=total_cells)
        nlp_cta_metrics = compute_cta_metrics(nlp_res.get("cta", []), ground_truth)
        nlp_cpa_metrics = compute_cpa_metrics(nlp_res.get("cpa", []), ground_truth)
        nlp_validity = compute_semantic_validity_rate(
            nlp_res,
            ground_truth,
            shacl_violations=nlp_res.get("violations_count", 0),
            total_elements=total_cells,
        )

        nlp_score = BenchmarkScore(
            table_id=table_id,
            table_name=table_name,
            model_name="Pure NLP Baseline",
            cea_accuracy=nlp_cea_metrics["accuracy"],
            cta_accuracy=nlp_cta_metrics["accuracy"],
            cpa_precision=nlp_cpa_metrics["precision"],
            cpa_recall=nlp_cpa_metrics["recall"],
            cpa_f1=nlp_cpa_metrics["f1"],
            semantic_validity_rate=nlp_validity,
            shacl_violations=nlp_res.get("violations_count", 0),
            hallucination_count=nlp_res.get("hallucinations_count", 0),
        )

        # 2. Run GW2-UME Relational Mesh & Dynamically Compute Metrics
        mesh = build_relational_mesh(content, table_name=table_name, validate_shacl=True)
        mesh_cea_metrics = compute_cea_metrics(mesh.cea, ground_truth, total_cells=total_cells)
        mesh_cta_metrics = compute_cta_metrics(mesh.cta, ground_truth)
        mesh_cpa_metrics = compute_cpa_metrics(mesh.cpa, ground_truth)
        mesh_validity = compute_semantic_validity_rate(
            mesh,
            ground_truth,
            shacl_violations=len(mesh.validation_violations),
            total_elements=max(1, len(mesh.nodes) + len(mesh.edges)),
        )

        mesh_score = BenchmarkScore(
            table_id=table_id,
            table_name=table_name,
            model_name="GW2-UME Semantic Mesh",
            cea_accuracy=mesh_cea_metrics["accuracy"],
            cta_accuracy=mesh_cta_metrics["accuracy"],
            cpa_precision=mesh_cpa_metrics["precision"],
            cpa_recall=mesh_cpa_metrics["recall"],
            cpa_f1=mesh_cpa_metrics["f1"],
            semantic_validity_rate=mesh_validity,
            shacl_violations=len(mesh.validation_violations),
            hallucination_count=0,
        )

        return nlp_score, mesh_score

    def run_all_benchmarks(self, suite_path: Optional[str] = None) -> Tuple[List[Tuple[BenchmarkScore, BenchmarkScore]], BenchmarkSummary]:
        """Runs the complete suite of benchmarks across all 5 domains."""
        if suite_path is None:
            suite_file = self.benchmarks_dir / "benchmark_suite.json"
        else:
            suite_file = Path(suite_path)

        with open(suite_file, "r", encoding="utf-8") as f:
            suite_data = json.load(f)

        scores: List[Tuple[BenchmarkScore, BenchmarkScore]] = []

        for b in suite_data.get("benchmarks", []):
            table_id = b["id"]
            table_name = b["name"]
            rel_path = b["table_path"]
            domain = b.get("domain")
            nlp_s, mesh_s = self.run_table_benchmark(rel_path, table_id, table_name, domain=domain)
            scores.append((nlp_s, mesh_s))

        # Compute Summary averages
        nlp_scores = [s[0] for s in scores]
        mesh_scores = [s[1] for s in scores]

        summary = BenchmarkSummary(
            pure_nlp_avg_cea=sum(s.cea_accuracy for s in nlp_scores) / len(nlp_scores) if nlp_scores else 0.0,
            mesh_avg_cea=sum(s.cea_accuracy for s in mesh_scores) / len(mesh_scores) if mesh_scores else 0.0,
            pure_nlp_avg_cta=sum(s.cta_accuracy for s in nlp_scores) / len(nlp_scores) if nlp_scores else 0.0,
            mesh_avg_cta=sum(s.cta_accuracy for s in mesh_scores) / len(mesh_scores) if mesh_scores else 0.0,
            pure_nlp_avg_cpa_f1=sum(s.cpa_f1 for s in nlp_scores) / len(nlp_scores) if nlp_scores else 0.0,
            mesh_avg_cpa_f1=sum(s.cpa_f1 for s in mesh_scores) / len(mesh_scores) if mesh_scores else 0.0,
            pure_nlp_avg_validity=sum(s.semantic_validity_rate for s in nlp_scores) / len(nlp_scores) if nlp_scores else 0.0,
            mesh_avg_validity=sum(s.semantic_validity_rate for s in mesh_scores) / len(mesh_scores) if mesh_scores else 0.0,
            pure_nlp_total_violations=sum(s.shacl_violations for s in nlp_scores),
            mesh_total_violations=sum(s.shacl_violations for s in mesh_scores),
        )

        return scores, summary

    def get_benchmark_by_id(self, benchmark_id: str, suite_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves benchmark configuration dictionary by its ID."""
        if suite_path is None:
            suite_file = self.benchmarks_dir / "benchmark_suite.json"
        else:
            suite_file = Path(suite_path)

        with open(suite_file, "r", encoding="utf-8") as f:
            suite_data = json.load(f)

        for b in suite_data.get("benchmarks", []):
            if b["id"] == benchmark_id:
                return b
        return None

    def run_domain_benchmark(self, domain_name: str, suite_path: Optional[str] = None) -> Tuple[BenchmarkScore, BenchmarkScore]:
        """Runs benchmark matching a specific domain name or ID."""
        if suite_path is None:
            suite_file = self.benchmarks_dir / "benchmark_suite.json"
        else:
            suite_file = Path(suite_path)

        with open(suite_file, "r", encoding="utf-8") as f:
            suite_data = json.load(f)

        for b in suite_data.get("benchmarks", []):
            if (
                domain_name.lower() in b.get("domain", "").lower()
                or domain_name.lower() in b.get("name", "").lower()
                or domain_name.lower() in b.get("id", "").lower()
            ):
                return self.run_table_benchmark(b["table_path"], b["id"], b["name"], domain=b.get("domain"))

        raise ValueError(f"Domain '{domain_name}' not found in benchmark suite.")


__all__ = ["BenchmarkRunner"]

