"""Proof-of-Value Benchmark Tests comparing Pure NLP against GW2-UME Semantic Mesh."""

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.benchmark.runner import BenchmarkRunner
from gw2_ume.neurosymbolic.baseline_nlp import PureNLPBaseline
from gw2_ume.neurosymbolic.pingpong import NeuroSymbolicPingPongEngine
from gw2_ume.mesh.relational_mesh import build_relational_mesh


class TestProofOfValueBenchmark(unittest.TestCase):
    """Tests evaluating the semantic advantage of GW2-UME over Pure NLP."""

    def setUp(self):
        self.runner = BenchmarkRunner()
        self.data_dir = Path(__file__).resolve().parent.parent / "data"

    def test_clean_wiki_table_nevermore_steps(self):
        """Tests that Semantic Mesh outperforms pure NLP on clean Nevermore steps."""
        table_path = str(self.data_dir / "sample_tables" / "legendary_nevermore_steps.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_nevermore_steps",
            table_name="Nevermore 4-Tier Steps",
        )

        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cta_accuracy, nlp_score.cta_accuracy)
        self.assertGreater(mesh_score.cpa_f1, nlp_score.cpa_f1)
        self.assertEqual(mesh_score.shacl_violations, 0)
        self.assertEqual(mesh_score.semantic_validity_rate, 1.0)

    def test_ambiguous_matrix_polysemy_disambiguation(self):
        """Tests that Semantic Mesh resolves ambiguous and polysemous terms where Pure NLP fails."""
        table_path = str(self.data_dir / "sample_tables" / "ambiguous_crafting_matrix.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_ambiguous_matrix",
            table_name="Ambiguous Crafting Matrix",
        )

        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.semantic_validity_rate, nlp_score.semantic_validity_rate)
        self.assertEqual(mesh_score.hallucination_count, 0)

    def test_noisy_scraped_tribute_resilience(self):
        """Tests that Semantic Mesh corrects OCR/leetspeak errors and handles noisy scraped tables."""
        table_path = str(self.data_dir / "sample_tables" / "noisy_scraped_tribute.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_noisy_scraped_tribute",
            table_name="Noisy Scraped Tribute",
        )

        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cpa_f1, nlp_score.cpa_f1)
        self.assertLess(mesh_score.shacl_violations, nlp_score.shacl_violations)

    def test_complete_benchmark_suite_summary(self):
        """Tests overall benchmark suite execution and verifies systemic semantic advantage."""
        scores, summary = self.runner.run_all_benchmarks()

        self.assertEqual(len(scores), 5)
        self.assertGreater(summary.mesh_avg_cea, summary.pure_nlp_avg_cea)
        self.assertGreater(summary.mesh_avg_cta, summary.pure_nlp_avg_cta)
        self.assertGreater(summary.mesh_avg_cpa_f1, summary.pure_nlp_avg_cpa_f1)
        self.assertGreater(summary.mesh_avg_validity, summary.pure_nlp_avg_validity)
        self.assertEqual(summary.mesh_total_violations, 0)
        self.assertGreater(summary.pure_nlp_total_violations, 0)


if __name__ == "__main__":
    unittest.main()
