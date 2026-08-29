"""Multi-domain benchmark tests evaluating GW2-UME Semantic Mesh against Pure NLP Baseline across 5 domains."""

from __future__ import annotations
import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.benchmark.runner import BenchmarkRunner
from gw2_ume.benchmark.metrics import BenchmarkScore, BenchmarkSummary


class TestMultiDomainBenchmark(unittest.TestCase):
    """Evaluates the 5 distinct benchmark domains ensuring 100% semantic validity and 0 SHACL violations."""

    def setUp(self) -> None:
        self.runner = BenchmarkRunner()
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.sample_tables_dir = self.data_dir / "sample_tables"

    def test_domain_1_gen2_nevermore_precursor_journey(self) -> None:
        """Domain 1: Gen 2 Precursor Weapon Journeys (Nevermore 4-tier steps)."""
        table_path = str(self.sample_tables_dir / "legendary_nevermore_steps.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_nevermore_journey",
            table_name="Gen 2 Precursor Weapon Journeys (Nevermore)",
            domain="Gen 2 Precursor Weapon Journeys",
        )

        # Mesh guarantees
        self.assertEqual(mesh_score.semantic_validity_rate, 1.0)
        self.assertEqual(mesh_score.shacl_violations, 0)
        self.assertEqual(mesh_score.hallucination_count, 0)
        self.assertGreaterEqual(mesh_score.cea_accuracy, 0.90)
        self.assertEqual(mesh_score.cta_accuracy, 1.0)
        self.assertGreaterEqual(mesh_score.cpa_f1, 0.40)

        # Head-to-Head advantage over Pure NLP
        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cta_accuracy, nlp_score.cta_accuracy)
        self.assertGreater(mesh_score.cpa_f1, nlp_score.cpa_f1)
        self.assertGreater(mesh_score.semantic_validity_rate, nlp_score.semantic_validity_rate)
        self.assertLess(mesh_score.shacl_violations, nlp_score.shacl_violations)
        self.assertGreater(nlp_score.shacl_violations, 0)

    def test_domain_2_gen1_gen2_multi_precursor_hope_bifrost(self) -> None:
        """Domain 2: Gen 1 & Gen 2 Multi-Precursor & Mystic Forge (HOPE / Bifrost tracker)."""
        table_path = str(self.sample_tables_dir / "google_sheet_hope_bifrost_tracker.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_hope_bifrost_forge",
            table_name="Gen 1 & Gen 2 Multi-Precursor & Mystic Forge (HOPE / Bifrost)",
            domain="Gen 1 & Gen 2 Multi-Precursor & Mystic Forge",
        )

        # Mesh guarantees
        self.assertEqual(mesh_score.semantic_validity_rate, 1.0)
        self.assertEqual(mesh_score.shacl_violations, 0)
        self.assertEqual(mesh_score.hallucination_count, 0)
        self.assertGreaterEqual(mesh_score.cea_accuracy, 0.20)
        self.assertGreaterEqual(mesh_score.cta_accuracy, 0.35)

        # Head-to-Head advantage
        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cta_accuracy, nlp_score.cta_accuracy)
        self.assertGreater(mesh_score.semantic_validity_rate, nlp_score.semantic_validity_rate)
        self.assertLess(mesh_score.shacl_violations, nlp_score.shacl_violations)
        self.assertGreater(nlp_score.shacl_violations, 50)

    def test_domain_3_mount_acquisition_skyscale(self) -> None:
        """Domain 3: Mount Acquisition Chains (Skyscale Tracker)."""
        table_path = str(self.sample_tables_dir / "skyscale_acquisition_tracker.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_skyscale_acquisition",
            table_name="Mount Acquisition Chains (Skyscale Tracker)",
            domain="Mount Acquisition Chains",
        )

        # Mesh guarantees
        self.assertEqual(mesh_score.semantic_validity_rate, 1.0)
        self.assertEqual(mesh_score.shacl_violations, 0)
        self.assertEqual(mesh_score.hallucination_count, 0)
        self.assertGreaterEqual(mesh_score.cea_accuracy, 0.40)
        self.assertGreaterEqual(mesh_score.cta_accuracy, 0.80)

        # Head-to-Head advantage
        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cta_accuracy, nlp_score.cta_accuracy)
        self.assertGreater(mesh_score.semantic_validity_rate, nlp_score.semantic_validity_rate)
        self.assertLess(mesh_score.shacl_violations, nlp_score.shacl_violations)
        self.assertGreater(nlp_score.shacl_violations, 10)

    def test_domain_4_crafting_discipline_materials(self) -> None:
        """Domain 4: Multi-Discipline Crafting Matrices (Crafting Discipline Materials)."""
        table_path = str(self.sample_tables_dir / "crafting_discipline_materials.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_crafting_discipline_materials",
            table_name="Multi-Discipline Crafting Matrices (Crafting Discipline Materials)",
            domain="Multi-Discipline Crafting Matrices",
        )

        # Mesh guarantees
        self.assertEqual(mesh_score.semantic_validity_rate, 1.0)
        self.assertEqual(mesh_score.shacl_violations, 0)
        self.assertEqual(mesh_score.hallucination_count, 0)
        self.assertGreaterEqual(mesh_score.cea_accuracy, 0.95)
        self.assertGreaterEqual(mesh_score.cta_accuracy, 0.50)
        self.assertGreaterEqual(mesh_score.cpa_f1, 0.30)

        # Head-to-Head advantage
        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cta_accuracy, nlp_score.cta_accuracy)
        self.assertGreater(mesh_score.cpa_f1, nlp_score.cpa_f1)
        self.assertGreater(mesh_score.semantic_validity_rate, nlp_score.semantic_validity_rate)
        self.assertLess(mesh_score.shacl_violations, nlp_score.shacl_violations)
        self.assertGreater(nlp_score.shacl_violations, 10)

    def test_domain_5_noisy_scraped_ocr_tribute(self) -> None:
        """Domain 5: Noisy Scraped OCR Tables (Noisy Scraped Tribute)."""
        table_path = str(self.sample_tables_dir / "noisy_scraped_tribute.csv")
        nlp_score, mesh_score = self.runner.run_table_benchmark(
            table_path=table_path,
            table_id="bench_noisy_scraped_tribute",
            table_name="Noisy Scraped OCR Tables (Noisy Scraped Tribute)",
            domain="Noisy Scraped OCR Tables",
        )

        # Mesh guarantees
        self.assertEqual(mesh_score.semantic_validity_rate, 1.0)
        self.assertEqual(mesh_score.shacl_violations, 0)
        self.assertEqual(mesh_score.hallucination_count, 0)
        self.assertGreaterEqual(mesh_score.cea_accuracy, 0.20)
        self.assertGreaterEqual(mesh_score.cta_accuracy, 0.50)
        self.assertGreaterEqual(mesh_score.cpa_f1, 0.20)

        # Head-to-Head advantage on noisy corrupted inputs
        self.assertGreater(mesh_score.cea_accuracy, nlp_score.cea_accuracy)
        self.assertGreater(mesh_score.cta_accuracy, nlp_score.cta_accuracy)
        self.assertGreater(mesh_score.cpa_f1, nlp_score.cpa_f1)
        self.assertGreater(mesh_score.semantic_validity_rate, nlp_score.semantic_validity_rate)
        self.assertLess(mesh_score.shacl_violations, nlp_score.shacl_violations)
        self.assertGreater(nlp_score.shacl_violations, 0)

    def test_complete_multi_domain_benchmark_suite_summary(self) -> None:
        """Verify executing the full multi-domain benchmark suite across all 5 domains."""
        scores, summary = self.runner.run_all_benchmarks()

        # 5 distinct domains evaluated
        self.assertEqual(len(scores), 5)
        domain_ids = [s[1].table_id for s in scores]
        self.assertIn("bench_nevermore_journey", domain_ids)
        self.assertIn("bench_hope_bifrost_forge", domain_ids)
        self.assertIn("bench_skyscale_acquisition", domain_ids)
        self.assertIn("bench_crafting_discipline_materials", domain_ids)
        self.assertIn("bench_noisy_scraped_tribute", domain_ids)

        # Summary assertions
        self.assertGreaterEqual(summary.mesh_avg_validity, 0.99)
        self.assertEqual(summary.mesh_total_violations, 0)
        self.assertGreater(summary.mesh_avg_cea, summary.pure_nlp_avg_cea)
        self.assertGreater(summary.mesh_avg_cta, summary.pure_nlp_avg_cta)
        self.assertGreater(summary.mesh_avg_cpa_f1, summary.pure_nlp_avg_cpa_f1)
        self.assertGreater(summary.mesh_avg_validity, summary.pure_nlp_avg_validity)
        self.assertGreater(summary.pure_nlp_total_violations, 0)

        # Serializability
        summary_dict = summary.to_dict()
        self.assertIn("pure_nlp", summary_dict)
        self.assertIn("gw2_ume_mesh", summary_dict)
        self.assertEqual(summary_dict["gw2_ume_mesh"]["total_shacl_violations"], 0)

    def test_domain_lookup_and_individual_runner(self) -> None:
        """Verify querying benchmark config by ID and executing individual domain benchmarks."""
        # Benchmark config lookup
        b_info = self.runner.get_benchmark_by_id("bench_nevermore_journey")
        self.assertIsNotNone(b_info)
        self.assertEqual(b_info["domain"], "Gen 2 Precursor Weapon Journeys")

        # Run domain benchmark by domain keyword
        nlp_s, mesh_s = self.runner.run_domain_benchmark("Skyscale")
        self.assertEqual(mesh_s.table_id, "bench_skyscale_acquisition")
        self.assertEqual(mesh_s.semantic_validity_rate, 1.0)
        self.assertEqual(mesh_s.shacl_violations, 0)

        # Nonexistent domain raises ValueError
        with self.assertRaises(ValueError):
            self.runner.run_domain_benchmark("NonExistentDomainXYZ")


if __name__ == "__main__":
    unittest.main()
