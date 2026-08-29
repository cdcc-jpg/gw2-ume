"""End-to-End Pipeline Tests for GW2-UME."""

import sys
import unittest
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.mesh.annotator import parse_table_content, annotate_table
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.neurosymbolic.pingpong import NeuroSymbolicPingPongEngine
from gw2_ume.text.extractor import TextEntityRelationExtractor
from gw2_ume.ui.visualizer import generate_dashboard_html
from gw2_ume.cli import main


class TestEndToEndPipeline(unittest.TestCase):
    """End-to-end integration tests for the full GW2-UME semantic toolchain."""

    def setUp(self):
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.steps_csv = self.data_dir / "sample_tables" / "legendary_nevermore_steps.csv"
        self.tribute_csv = self.data_dir / "sample_tables" / "mystic_forge_tribute_matrix.csv"
        self.guide_txt = self.data_dir / "sample_tables" / "unstructured_guide_nevermore.txt"

    def test_table_parsing_and_annotation(self):
        """Tests table parsing and CEA/CTA/CPA generation."""
        with open(self.steps_csv, "r", encoding="utf-8") as f:
            content = f.read()

        headers, rows = parse_table_content(content)
        self.assertEqual(len(headers), 9)
        self.assertEqual(len(rows), 17)

        cta, cea, cpa = annotate_table(headers, rows)
        self.assertEqual(len(cta), 9)
        self.assertGreater(len(cea), 15)
        self.assertGreater(len(cpa), 3)

    def test_relational_mesh_construction_and_shacl(self):
        """Tests building Relational Mesh and validating against SHACL."""
        with open(self.steps_csv, "r", encoding="utf-8") as f:
            content = f.read()

        mesh = build_relational_mesh(content, table_name="nevermore_steps", validate_shacl=True)
        self.assertGreater(len(mesh.nodes), 20)
        self.assertGreater(len(mesh.edges), 10)
        self.assertEqual(mesh.validation_status, "CONFORMING")
        self.assertIn("@prefix gw2:", mesh.turtle)
        self.assertTrue(len(mesh.json_ld) > 0)

    def test_unstructured_text_extraction(self):
        """Tests text entity-relation extraction on guide text."""
        with open(self.guide_txt, "r", encoding="utf-8") as f:
            content = f.read()

        extractor = TextEntityRelationExtractor()
        result = extractor.extract_from_text(content)

        self.assertGreater(result["entity_count"], 5)
        self.assertGreater(result["triple_count"], 2)
        self.assertIn("Nevermore", result["turtle"])

    def test_pingpong_dialogue_trace(self):
        """Tests that Neuro-Symbolic ping-pong dialogue runs 2 rounds with diagnostic trace."""
        with open(self.steps_csv, "r", encoding="utf-8") as f:
            content = f.read()

        engine = NeuroSymbolicPingPongEngine()
        result = engine.run_dialogue(content, table_name="nevermore_steps")

        self.assertEqual(len(result.turns), 4)
        self.assertTrue(result.conforms_shacl)
        self.assertGreater(len(result.final_verified_triples), 5)

    def test_html_visualizer_generation(self):
        """Tests generating standalone interactive HTML dashboard."""
        with open(self.tribute_csv, "r", encoding="utf-8") as f:
            content = f.read()

        mesh = build_relational_mesh(content, table_name="mystic_forge_tribute")
        
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            html_out = generate_dashboard_html(mesh, title="Mystic Forge Test Dashboard", output_path=tmp_path)
            self.assertIn("<!DOCTYPE html>", html_out)
            self.assertIn("GW2-UME Semantic Mesh Visualizer", html_out)
            self.assertIn("Mystic Forge Test Dashboard", html_out)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 500)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cli_match_table(self):
        """Tests CLI match-table subcommand."""
        runner = CliRunner()
        res = runner.invoke(main, ["match-table", str(self.steps_csv), "--format", "turtle"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Column Type Annotations", res.output)
        self.assertIn("CONFORMING", res.output)

    def test_cli_classify_text(self):
        """Tests CLI classify-text subcommand."""
        runner = CliRunner()
        res = runner.invoke(main, ["classify-text", str(self.guide_txt)])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Extracted Entities", res.output)

    def test_cli_pingpong(self):
        """Tests CLI pingpong subcommand."""
        runner = CliRunner()
        res = runner.invoke(main, ["pingpong", str(self.steps_csv), "--verbose"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Neuro-Symbolic Ping-Pong Engine", res.output)
        self.assertIn("Round 1", res.output)
        self.assertIn("Round 2", res.output)

    def test_cli_benchmark(self):
        """Tests CLI benchmark subcommand."""
        runner = CliRunner()
        res = runner.invoke(main, ["benchmark"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Proof-of-Value Executive Summary", res.output)
        self.assertIn("GW2-UME", res.output)

    def test_cli_visualize(self):
        """Tests CLI visualize subcommand."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            res = runner.invoke(main, ["visualize", str(self.steps_csv), "--output", tmp_path])
            self.assertEqual(res.exit_code, 0)
            self.assertTrue(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
