"""Unit tests for the 3-Phase Semantic Table Annotator Engine in GW2-UME."""

import json
from pathlib import Path
import unittest

from gw2_ume.pipeline.semantic_table_annotator import SemanticTableAnnotator, TableAnnotationResult

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "data" / "sample_tables" / "adversarial_table.csv"
GROUND_TRUTH_PATH = REPO_ROOT / "data" / "benchmarks" / "ground_truth_adversarial_schema.json"


class TestSemanticTableAnnotator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.annotator = SemanticTableAnnotator()
        cls.result = cls.annotator.annotate(CSV_PATH)
        with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
            cls.ground_truth = json.load(f)
        cls.gt_cols = {c["column_index"]: c for c in cls.ground_truth["columns"]}

    def test_total_columns_processed(self):
        self.assertEqual(len(self.result.columns), 16)
        self.assertEqual(self.result.row_count, 100)

    def test_property_annotation_accuracy(self):
        """Verifies 100% property annotation accuracy against ground truth."""
        correct = sum(
            1 for col in self.result.columns
            if col.predicted_property_uri == self.gt_cols[col.column_index]["true_property_uri"]
        )
        self.assertEqual(correct, 16)

    def test_subject_entity_grouping_accuracy(self):
        """Verifies 100% subject entity clustering accuracy."""
        correct = sum(
            1 for col in self.result.columns
            if col.predicted_subject_class == self.gt_cols[col.column_index]["true_subject_class"]
        )
        self.assertEqual(correct, 16)

    def test_deceptive_header_resistance(self):
        """Verifies that all 4 false friend / deceptive traps are caught and overridden."""
        deceptive_indices = [
            c["column_index"] for c in self.ground_truth["columns"]
            if c["header_type"] == "deceptive"
        ]
        self.assertEqual(len(deceptive_indices), 4)
        for idx in deceptive_indices:
            col = self.result.columns[idx]
            self.assertEqual(col.predicted_property_uri, self.gt_cols[idx]["true_property_uri"])
            self.assertTrue(col.is_false_friend)

    def test_resolution_phase_attribution(self):
        """Verifies that all 3 phases (Phase 1, Phase 2, Phase 3) participate in resolution."""
        phase_counts = self.result.phase_counts
        self.assertGreater(phase_counts["Phase 1 (Deterministic Extensional / Structural Anchor)"], 0)
        self.assertGreater(phase_counts["Phase 2 (Sudoku Relational Propagation)"], 0)
        self.assertGreater(phase_counts["Phase 3 (Gemma Arbiter)"], 0)
        self.assertEqual(sum(phase_counts.values()), 16)

    def test_inter_entity_relation_discovery(self):
        """Verifies that priory:producesItem(Recipe, Item) is discovered and validated."""
        self.assertGreater(len(self.result.inter_entity_relations), 0)
        rel = self.result.inter_entity_relations[0]
        self.assertEqual(rel["relation_uri"], "priory:producesItem")
        self.assertEqual(rel["subject_class"], "priory:DisciplineRecipe")
        self.assertEqual(rel["object_class"], "priory:Item")
        self.assertEqual(rel["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
