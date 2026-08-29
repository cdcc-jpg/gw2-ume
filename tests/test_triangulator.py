"""Unit tests for CrossModalTriangulator and CLI triangulate command."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.pipeline.triangulator import CrossModalTriangulator, TriangulationResult
from gw2_ume.cli import main


class TestCrossModalTriangulator(unittest.TestCase):
    """Test suite for Cross-Modal Triangulation, Noisy-OR Fusion, and SHACL Validation."""

    def setUp(self):
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.steps_csv = self.data_dir / "sample_tables" / "legendary_nevermore_steps.csv"
        self.guide_txt = self.data_dir / "sample_tables" / "unstructured_guide_nevermore.txt"

        with open(self.steps_csv, "r", encoding="utf-8") as f:
            self.table_content = f.read()
        with open(self.guide_txt, "r", encoding="utf-8") as f:
            self.text_content = f.read()

        self.triangulator = CrossModalTriangulator(alpha=0.05, validate_shacl=True)

    def test_noisy_or_confidence_formula(self):
        """Tests the Noisy-OR formula: C_fused = 1 - (1 - C_tab)(1 - C_txt) + alpha * ValidAxiom."""
        # Case 1: Both modalities present with high confidence + valid axiom (alpha=0.05)
        # C_base = 1 - (1 - 0.90)(1 - 0.85) = 1 - 0.015 = 0.985
        # C_fused = min(1.0, 0.985 + 0.05) = 1.0
        c1 = self.triangulator.compute_noisy_or_confidence(0.90, 0.85, valid_axiom=True)
        self.assertAlmostEqual(c1, 1.0, places=3)

        # Case 2: Table-only entity (C_txt = 0.0) + valid axiom
        # C_base = 0.80 -> C_fused = 0.80 + 0.05 = 0.85
        c2 = self.triangulator.compute_noisy_or_confidence(0.80, 0.0, valid_axiom=True)
        self.assertAlmostEqual(c2, 0.85, places=3)

        # Case 3: Text-only entity (C_tab = 0.0) + invalid axiom
        # C_base = 0.75 -> C_fused = 0.75 + 0.0 = 0.75
        c3 = self.triangulator.compute_noisy_or_confidence(0.0, 0.75, valid_axiom=False)
        self.assertAlmostEqual(c3, 0.75, places=3)

        # Case 4: Moderate confidence in both modalities
        # C_base = 1 - (1 - 0.70)(1 - 0.60) = 1 - 0.12 = 0.88 -> + 0.05 = 0.93
        c4 = self.triangulator.compute_noisy_or_confidence(0.70, 0.60, valid_axiom=True)
        self.assertAlmostEqual(c4, 0.93, places=3)

    def test_bayesian_prior_transmission(self):
        """Tests that document aboutness correctly derives priors from text keywords."""
        priors = self.triangulator._infer_document_aboutness(self.text_content)
        self.assertIn("nevermore", priors)
        self.assertGreater(priors["nevermore"], 0.5)

    def test_cross_modal_triangulation_execution(self):
        """Tests end-to-end triangulation on Nevermore table and text guide."""
        res = self.triangulator.triangulate(self.table_content, self.text_content, table_name="nevermore_test")

        self.assertIsInstance(res, TriangulationResult)
        self.assertEqual(res.table_name, "nevermore_test")
        self.assertTrue(res.conforms_shacl)
        self.assertEqual(res.validation_status, "CONFORMING")
        self.assertGreater(len(res.fused_entities), 10)
        self.assertGreater(len(res.fused_triples), 10)
        self.assertGreater(res.cross_modal_links_count, 3)

        # Check provenance breakdown
        self.assertIn("cross_modal_corroborated", res.provenance_breakdown)
        self.assertGreater(res.provenance_breakdown["cross_modal_corroborated"], 0)

        # Check serialization
        self.assertIn("@prefix priory:", res.turtle)
        self.assertIn("@prefix item:", res.turtle)
        self.assertIn("Nevermore", res.turtle)
        self.assertTrue(len(res.json_ld) > 0)

    def test_fused_attributes_and_quantities(self):
        """Verifies that exact table quantities are merged with narrative lore."""
        res = self.triangulator.triangulate(self.table_content, self.text_content, table_name="nevermore_test")

        ent_dict = {e["label"]: e for e in res.fused_entities}

        # Spiritwood Plank should have quantity 3
        self.assertIn("Spiritwood Plank", ent_dict)
        self.assertEqual(ent_dict["Spiritwood Plank"]["quantity"], 3)

        # Ravenswood Branch should be PrecursorWeapon with Artificer discipline
        self.assertIn("Ravenswood Branch", ent_dict)
        self.assertEqual(ent_dict["Ravenswood Branch"]["discipline"], "Artificer")
        self.assertEqual(ent_dict["Ravenswood Branch"]["entity_type"], "PrecursorWeapon")

        # Shaman Sigurlina should have Wayfarer Foothills zone
        self.assertIn("Shaman Sigurlina", ent_dict)
        self.assertEqual(ent_dict["Shaman Sigurlina"]["zone"], "Wayfarer Foothills")

    def test_multi_hop_relational_paths(self):
        """Verifies multi-hop path synthesis: Precursor chain & Vendor-Zone relations."""
        res = self.triangulator.triangulate(self.table_content, self.text_content, table_name="nevermore_test")

        triples = set(res.fused_triples)

        # Precursor chain
        self.assertIn(("Ravenswood Branch", "precursorTo", "Ravenswood Staff"), triples)
        self.assertIn(("Ravenswood Staff", "precursorTo", "The Raven Spirit"), triples)
        self.assertIn(("The Raven Spirit", "precursorTo", "The Living Ravens"), triples)

        # Vendor -> Zone
        self.assertIn(("Shaman Sigurlina", "locatedInZone", "Wayfarer Foothills"), triples)
        self.assertIn(("Grandmaster Craftsman Hobbs", "locatedInZone", "Lion's Arch"), triples)

        # Item -> Vendor
        self.assertIn(("Essence of the Raven", "obtainedFromVendor", "Shaman Sigurlina"), triples)

    def test_cli_triangulate_turtle(self):
        """Tests the CLI `gw2-ume triangulate` command emitting Turtle format."""
        runner = CliRunner()
        res = runner.invoke(main, [
            "triangulate",
            str(self.steps_csv),
            str(self.guide_txt),
            "--format", "turtle",
        ])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Cross-Modal Triangulation", res.output)
        self.assertIn("Fused & Corroborated Entities", res.output)
        self.assertIn("Fused Relational Triples", res.output)
        self.assertIn("CONFORMING", res.output)
        self.assertIn("@prefix priory:", res.output)

    def test_cli_triangulate_jsonld_and_output(self):
        """Tests the CLI `gw2-ume triangulate` command saving JSON-LD to file."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".jsonld", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            res = runner.invoke(main, [
                "triangulate",
                str(self.steps_csv),
                str(self.guide_txt),
                "--format", "json-ld",
                "--output", tmp_path,
            ])
            self.assertEqual(res.exit_code, 0)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 200)

            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, (dict, list))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cli_triangulate_dashboard(self):
        """Tests the CLI `gw2-ume triangulate` command generating interactive HTML dashboard."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            res = runner.invoke(main, [
                "triangulate",
                str(self.steps_csv),
                str(self.guide_txt),
                "--dashboard", tmp_path,
            ])
            self.assertEqual(res.exit_code, 0)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 500)

            with open(tmp_path, "r", encoding="utf-8") as f:
                html_txt = f.read()
            self.assertIn("<!DOCTYPE html>", html_txt)
            self.assertIn("GW2-UME Semantic Mesh Visualizer", html_txt)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
