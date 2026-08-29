"""Unit test suite for GW2-UME Normalization, Neuro-Symbolic Ping-Pong Engine,

LLM Integration, and Knowledge Graph Enrichment.
"""

import json
import sys
from pathlib import Path
import unittest

import rdflib

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.models import (
    CandidateTableInterpretation,
    CellMention,
    DiagnosticConflict,
    EntitySpan,
    PingPongResult,
    RefinedProposal,
    TableColumnInterpretation,
    TableGrid,
    TableInterpretationMesh,
)
from gw2_ume.normalization.llm_normalizer import (
    APILLMNormalizer,
    HeuristicNormalizer,
    LocalGemmaNormalizer,
    get_normalizer,
)
from gw2_ume.normalization.text_cleaner import (
    CSVTableParser,
    HTMLTableParser,
    JSONTableParser,
    MarkdownTableParser,
    TSVTableParser,
    TextCleaner,
    extract_entity_spans,
    normalize_text,
    parse_table,
)
from gw2_ume.pipeline.enricher import KnowledgeGraphEnricher
from gw2_ume.pipeline.engine import UMEEngine
from gw2_ume.pipeline.pingpong import NeuroSymbolicPingPongEngine, SymbolicAxiomReasoner


class TestTextCleanerAndParsers(unittest.TestCase):
    """Test text cleaning, GW2 jargon/typo normalization, span extraction, and multi-format table parsing."""

    def test_typo_and_jargon_normalization(self):
        """Verify normalization of colloquial game jargon and common typos."""
        self.assertEqual(normalize_text("amalgams"), "Amalgamated Gemstone")
        self.assertEqual(normalize_text("clovers"), "Mystic Clover")
        self.assertEqual(normalize_text("spirtwood"), "Spiritwood Plank")
        self.assertEqual(normalize_text("tribute"), "Mystic Tribute")
        self.assertEqual(normalize_text("nevermore 1"), "Nevermore I: Ravenswood Branch")
        self.assertEqual(normalize_text("ass"), "Antique Summoning Stone")
        self.assertEqual(normalize_text("ecto"), "Glob of Ectoplasm")
        self.assertEqual(normalize_text("mc"), "Mystic Coin")
        self.assertEqual(normalize_text("deldrimor"), "Deldrimor Steel Ingot")
        self.assertEqual(normalize_text("elonian"), "Elonian Leather Square")
        self.assertEqual(normalize_text("damask"), "Bolt of Damask")
        self.assertEqual(normalize_text("obsi"), "Obsidian Shard")

    def test_quantity_extraction(self):
        """Verify extraction of quantity, item name, and unit."""
        # Prefix format
        name, qty, unit = TextCleaner.extract_quantity("250x Spiritwood Plank")
        self.assertEqual(name, "Spiritwood Plank")
        self.assertEqual(qty, 250)
        self.assertEqual(unit, "count")

        # Suffix format
        name, qty, unit = TextCleaner.extract_quantity("Deldrimor Steel Ingot x100")
        self.assertEqual(name, "Deldrimor Steel Ingot")
        self.assertEqual(qty, 100)
        self.assertEqual(unit, "count")

        # Currency format
        name, qty, unit = TextCleaner.extract_quantity("10,000 Karma")
        self.assertEqual(name, "Karma")
        self.assertEqual(qty, 10000)
        self.assertEqual(unit, "Karma")

        # GW2 money format
        name, qty, unit = TextCleaner.extract_quantity("500g 20s 15c")
        self.assertEqual(qty, 500.2015)
        self.assertEqual(unit, "Gold")

    def test_entity_span_extraction(self):
        """Verify entity span extraction from unstructured text."""
        text = "To craft Nevermore, you need 250x Spiritwood Plank and 1 Mystic Tribute. Also bring 77 clovers."
        spans = extract_entity_spans(text)
        self.assertTrue(len(spans) >= 4)

        names = [s.normalized_text for s in spans]
        self.assertIn("Nevermore", names)
        self.assertIn("Spiritwood Plank", names)
        self.assertIn("Mystic Tribute", names)
        self.assertIn("Mystic Clover", names)

        # Check Spiritwood Plank quantity
        sp_span = next(s for s in spans if s.normalized_text == "Spiritwood Plank")
        self.assertEqual(sp_span.quantity, 250)

        # Check Mystic Clover quantity
        clover_span = next(s for s in spans if s.normalized_text == "Mystic Clover")
        self.assertEqual(clover_span.quantity, 77)

    def test_markdown_table_parsing(self):
        """Verify markdown table parsing."""
        md = """
| Material | Quantity | Cost |
|:---|:---:|---:|
| Spiritwood Plank | 250 | 100g |
| Deldrimor Steel Ingot | 100 | 50g |
| Mystic Clover | 77 | 0g |
"""
        grid = parse_table(md, format_hint="markdown")
        self.assertEqual(grid.headers, ["Material", "Quantity", "Cost"])
        self.assertEqual(grid.shape, (3, 3))
        self.assertEqual(grid.rows[0], ["Spiritwood Plank", "250", "100g"])
        self.assertEqual(grid.rows[1], ["Deldrimor Steel Ingot", "100", "50g"])
        self.assertEqual(grid.rows[2], ["Mystic Clover", "77", "0g"])

    def test_csv_and_tsv_parsing(self):
        """Verify CSV and TSV parsing."""
        csv_data = "Item,Qty\nSpiritwood Plank,250\nGlob of Ectoplasm,250\n"
        grid_csv = parse_table(csv_data, format_hint="csv")
        self.assertEqual(grid_csv.headers, ["Item", "Qty"])
        self.assertEqual(grid_csv.shape, (2, 2))
        self.assertEqual(grid_csv.rows[0], ["Spiritwood Plank", "250"])

        tsv_data = "Item\tQty\nBolt of Damask\t50\nElonian Leather Square\t50\n"
        grid_tsv = parse_table(tsv_data, format_hint="tsv")
        self.assertEqual(grid_tsv.headers, ["Item", "Qty"])
        self.assertEqual(grid_tsv.shape, (2, 2))
        self.assertEqual(grid_tsv.rows[0], ["Bolt of Damask", "50"])

    def test_html_table_parsing(self):
        """Verify HTML table parsing."""
        html_data = """
        <table>
            <thead>
                <tr><th>Component</th><th>Amount</th></tr>
            </thead>
            <tbody>
                <tr><td>Gift of Energy</td><td>1</td></tr>
                <tr><td>Gift of Wood</td><td>1</td></tr>
            </tbody>
        </table>
        """
        grid_html = parse_table(html_data, format_hint="html")
        self.assertEqual(grid_html.headers, ["Component", "Amount"])
        self.assertEqual(grid_html.shape, (2, 2))
        self.assertEqual(grid_html.rows[0], ["Gift of Energy", "1"])
        self.assertEqual(grid_html.rows[1], ["Gift of Wood", "1"])

    def test_json_table_parsing(self):
        """Verify JSON table parsing with records and schema formats."""
        records = [
            {"Material": "Amalgamated Gemstone", "Quantity": 250},
            {"Material": "Mystic Coin", "Quantity": 250},
        ]
        grid_json = parse_table(records)
        self.assertEqual(grid_json.headers, ["Material", "Quantity"])
        self.assertEqual(grid_json.shape, (2, 2))
        self.assertEqual(grid_json.rows[0], ["Amalgamated Gemstone", "250"])


class TestLLMNormalizers(unittest.TestCase):
    """Test HeuristicNormalizer, LocalGemmaNormalizer fallback, and get_normalizer factory."""

    def test_heuristic_normalizer(self):
        """Test rule-based table mention extraction and proposal construction."""
        normalizer = HeuristicNormalizer()
        grid = TableGrid(
            headers=["Requirement", "Qty"],
            rows=[
                ["Spiritwood Plank", "250"],
                ["Deldrimor Steel Ingot", "100"],
            ],
            metadata={"title": "Nevermore"},
        )
        proposal = normalizer.extract_table_mentions(grid)
        self.assertEqual(len(proposal.columns), 2)
        self.assertEqual(proposal.columns[0].predicted_type, "CraftingMaterial")
        self.assertEqual(proposal.columns[1].predicted_type, "Quantity")
        self.assertEqual(proposal.subject_entity, "Nevermore")
        self.assertEqual(len(proposal.row_relations), 2)
        self.assertEqual(proposal.row_relations[0].predicate, "requiresMaterial")
        self.assertEqual(proposal.row_relations[0].object, "Spiritwood Plank")
        self.assertEqual(proposal.row_relations[0].quantity, 250)

    def test_factory_get_normalizer(self):
        """Test get_normalizer auto-selection."""
        n1 = get_normalizer("heuristic")
        self.assertIsInstance(n1, HeuristicNormalizer)

        n2 = get_normalizer("auto")
        self.assertIsInstance(n2, HeuristicNormalizer)

    def test_api_normalizer_fallback_without_keys(self):
        """Test APILLMNormalizer falls back with transparent logging when API keys are absent."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            gemini_norm = APILLMNormalizer(provider="gemini")
            self.assertFalse(gemini_norm._has_api_key())
            self.assertEqual(gemini_norm.normalize_text("spirtwood"), "Spiritwood Plank")

            spans = gemini_norm.extract_entity_spans("Need 250x spirtwood")
            self.assertTrue(len(spans) > 0)
            self.assertEqual(spans[0].normalized_text, "Spiritwood Plank")

            grid = TableGrid(headers=["Item"], rows=[["Spiritwood Plank"]])
            prop = gemini_norm.extract_table_mentions(grid)
            self.assertIsInstance(prop, CandidateTableInterpretation)

            refined = gemini_norm.resolve_ambiguity(prop, [])
            self.assertIsInstance(refined, RefinedProposal)

    def test_api_normalizer_gemini_mocked_calls(self):
        """Test APILLMNormalizer HTTP request execution and JSON parsing for Gemini."""
        import io
        import os
        from unittest.mock import MagicMock, patch

        mock_resp_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps({"normalized_text": "Spiritwood Plank"})}
                        ]
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_gemini_key"}):
            with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                normalizer = APILLMNormalizer(provider="gemini", model="gemini-2.5-flash")
                self.assertTrue(normalizer._has_api_key())
                res = normalizer.normalize_text("spirtwood")
                self.assertEqual(res, "Spiritwood Plank")
                mock_urlopen.assert_called_once()
                req = mock_urlopen.call_args[0][0]
                self.assertIn("key=fake_gemini_key", req.full_url)
                self.assertIn("gemini-2.5-flash", req.full_url)

    def test_api_normalizer_openai_mocked_calls(self):
        """Test APILLMNormalizer HTTP request execution and JSON parsing for OpenAI."""
        import os
        from unittest.mock import MagicMock, patch

        mock_resp_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps([
                            {
                                "raw_text": "Spiritwood Plank",
                                "normalized_text": "Spiritwood Plank",
                                "entity_type": "CraftingMaterial",
                                "quantity": 250,
                                "unit": "count",
                                "start": 0,
                                "end": 16,
                                "confidence": 0.99,
                            }
                        ])
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake_openai_key"}):
            with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                normalizer = APILLMNormalizer(provider="openai", model="gpt-4o-mini")
                self.assertTrue(normalizer._has_api_key())
                spans = normalizer.extract_entity_spans("Spiritwood Plank")
                self.assertEqual(len(spans), 1)
                self.assertEqual(spans[0].normalized_text, "Spiritwood Plank")
                self.assertEqual(spans[0].quantity, 250)

                req = mock_urlopen.call_args[0][0]
                self.assertIn("Bearer fake_openai_key", req.headers["Authorization"])

    def test_api_normalizer_anthropic_mocked_calls(self):
        """Test APILLMNormalizer HTTP request execution and JSON parsing for Anthropic."""
        import os
        from unittest.mock import MagicMock, patch

        mock_resp_data = {
            "content": [
                {
                    "text": json.dumps({
                        "columns": [
                            {"column_index": 0, "column_name": "Requirement", "predicted_type": "CraftingMaterial", "role": "ingredient", "confidence": 0.95},
                            {"column_index": 1, "column_name": "Quantity", "predicted_type": "Quantity", "role": "quantity", "confidence": 0.95},
                        ],
                        "table_type": "CraftingRecipe",
                        "subject_entity": "Nevermore",
                        "row_relations": [
                            {"row_idx": 0, "subject": "Nevermore", "predicate": "requiresMaterial", "object": "Spiritwood Plank", "quantity": 250, "unit": "count", "confidence": 0.95}
                        ],
                        "cell_mentions": [
                            {"row_idx": 0, "col_idx": 0, "raw_text": "Spiritwood Plank", "normalized_text": "Spiritwood Plank", "entity_type": "CraftingMaterial", "quantity": 250, "unit": "count", "confidence": 0.95}
                        ],
                        "confidence": 0.95,
                        "reasoning": "Extracted via Anthropic Claude."
                    })
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_anthropic_key"}):
            with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                normalizer = APILLMNormalizer(provider="anthropic", model="claude-3-5-sonnet-20241022")
                self.assertTrue(normalizer._has_api_key())
                grid = TableGrid(headers=["Requirement", "Quantity"], rows=[["Spiritwood Plank", "250"]])
                prop = normalizer.extract_table_mentions(grid)

                self.assertEqual(prop.table_type, "CraftingRecipe")
                self.assertEqual(prop.subject_entity, "Nevermore")
                self.assertEqual(len(prop.columns), 2)
                self.assertEqual(prop.columns[0].predicted_type, "CraftingMaterial")

                req = mock_urlopen.call_args[0][0]
                self.assertEqual(req.headers["X-api-key"], "fake_anthropic_key")
                self.assertEqual(req.headers["Anthropic-version"], "2023-06-01")

    def test_api_normalizer_http_error_fallback(self):
        """Test APILLMNormalizer gracefully catches HTTP errors and falls back to heuristic engine."""
        import os
        import urllib.error
        from unittest.mock import patch

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)):
                normalizer = APILLMNormalizer(provider="gemini")
                res = normalizer.normalize_text("spirtwood")
                self.assertEqual(res, "Spiritwood Plank")


class TestNeuroSymbolicPingPongEngine(unittest.TestCase):
    """Test SymbolicAxiomReasoner, conflict detection, diagnostic feedback,

    and multi-pass ping-pong convergence.
    """

    def setUp(self):
        self.reasoner = SymbolicAxiomReasoner()
        self.normalizer = HeuristicNormalizer()
        self.engine = NeuroSymbolicPingPongEngine(normalizer=self.normalizer, reasoner=self.reasoner)

    def test_conflict_detection_type_incompatibility(self):
        """Verify symbolic reasoner catches type incompatibility (materials in a column classified as Weapon)."""
        bad_proposal = CandidateTableInterpretation(
            columns=[
                TableColumnInterpretation(column_index=0, column_name="Weapon", predicted_type="Weapon", role="reward"),
                TableColumnInterpretation(column_index=1, column_name="Qty", predicted_type="Quantity", role="quantity"),
            ],
            cell_mentions=[
                CellMention(row_idx=0, col_idx=0, raw_text="Spiritwood Plank", normalized_text="Spiritwood Plank", entity_type="CraftingMaterial"),
                CellMention(row_idx=1, col_idx=0, raw_text="Deldrimor Steel Ingot", normalized_text="Deldrimor Steel Ingot", entity_type="CraftingMaterial"),
            ],
            table_type="CraftingRecipe",
            subject_entity="Nevermore",
            row_relations=[],
        )
        dummy_grid = TableGrid(headers=["Weapon", "Qty"], rows=[["Spiritwood Plank", "250"], ["Deldrimor Steel Ingot", "100"]])

        conflicts = self.reasoner.validate_interpretation(bad_proposal, dummy_grid)
        self.assertTrue(len(conflicts) >= 2)
        self.assertTrue(any(c.conflict_type == "TYPE_INCOMPATIBILITY" for c in conflicts))
        self.assertTrue(any("Disjoint" in c.rule_or_axiom for c in conflicts))

    def test_ping_pong_feedback_loop_convergence(self):
        """Verify full ping-pong loop where neural proposal with conflict is corrected

        via diagnostic feedback in 2 iterations.
        """
        # Create a table where header says "Weapon" but rows contain Crafting Materials
        table = TableGrid(
            headers=["Weapon", "Quantity"],
            rows=[
                ["Spiritwood Plank", "250"],
                ["Deldrimor Steel Ingot", "100"],
                ["Glob of Ectoplasm", "250"],
                ["Mystic Clover", "77"],
            ],
            metadata={"title": "Nevermore", "id": "test_table_nevermore"},
        )

        result: PingPongResult = self.engine.run(table, max_iterations=3)

        # Check convergence & success
        self.assertTrue(result.success)
        self.assertTrue(result.converged)
        self.assertLessEqual(result.iterations, 3)
        self.assertEqual(len(result.remaining_conflicts), 0)

        # Verify history steps
        self.assertEqual(len(result.history), result.iterations)
        step_1 = result.history[0]
        # In step 1, initial proposal classified "Weapon" header as "Weapon", triggering conflict
        self.assertTrue(len(step_1.conflicts) > 0)
        self.assertIn("TYPE_INCOMPATIBILITY", step_1.conflicts[0].conflict_type)

        # In step 2, feedback resolved the conflict
        step_2 = result.history[1]
        self.assertEqual(len(step_2.conflicts), 0)
        self.assertTrue(len(step_2.adjustments) > 0)

        # Verify resolved mesh
        mesh = result.mesh
        self.assertEqual(mesh.subject_entity, "Nevermore")
        self.assertEqual(mesh.columns[0].predicted_type, "CraftingMaterial")
        self.assertEqual(len(mesh.row_relations), 4)

        relation_objects = [r.object for r in mesh.row_relations]
        self.assertIn("Spiritwood Plank", relation_objects)
        self.assertIn("Deldrimor Steel Ingot", relation_objects)
        self.assertIn("Glob of Ectoplasm", relation_objects)
        self.assertIn("Mystic Clover", relation_objects)


class TestKnowledgeGraphEnricherAndRDF(unittest.TestCase):
    """Test RDF Turtle serialization, JSON-LD generation, and ontology learning."""

    def setUp(self):
        self.enricher = KnowledgeGraphEnricher()

    def test_rdf_turtle_validity(self):
        """Verify generated Turtle string is 100% syntactically valid by parsing with rdflib."""
        grid = TableGrid(
            headers=["Material", "Count"],
            rows=[
                ["Spiritwood Plank", "250"],
                ["Mystic Tribute", "1"],
            ],
            metadata={"title": "Nevermore", "id": "table_nevermore_craft"},
        )
        engine = UMEEngine()
        mesh = engine.match_table(grid)

        turtle_str = self.enricher.export_turtle(mesh)
        self.assertIn("gw2ume:CraftingRecipe", turtle_str)
        self.assertIn("Spiritwood_Plank", turtle_str)
        self.assertIn("Nevermore", turtle_str)

        # Parse turtle string back with rdflib to assert validity
        g = rdflib.Graph()
        g.parse(data=turtle_str, format="turtle")
        self.assertTrue(len(g) > 0)

    def test_jsonld_export(self):
        """Verify JSON-LD export dictionary structure."""
        grid = TableGrid(
            headers=["Material", "Count"],
            rows=[["Spiritwood Plank", "250"]],
            metadata={"title": "Nevermore"},
        )
        engine = UMEEngine()
        mesh = engine.match_table(grid)

        jsonld_dict = self.enricher.export_jsonld(mesh)
        self.assertIsInstance(jsonld_dict, (dict, list))

    def test_ontology_extension_proposal(self):
        """Verify detection of novel ungrounded entities and generation of CandidateOntologyAxiom."""
        grid = TableGrid(
            headers=["Material", "Count"],
            rows=[["Mysterious Ancient Relic From Future Expansion", "5"]],
            metadata={"title": "Unknown Weapon"},
        )
        engine = UMEEngine()
        mesh = engine.match_table(grid)

        axioms = self.enricher.propose_ontology_extensions(mesh)
        self.assertTrue(len(axioms) >= 1)
        self.assertEqual(axioms[0].axiom_type, "InstanceDeclaration")
        self.assertIn("Mysterious_Ancient_Relic_From_Future_Expansion", axioms[0].subject)
        self.assertIn("rdf:type gw2ume:CraftingMaterial", axioms[0].proposed_turtle)


class TestUMEEngineMasterIntegration(unittest.TestCase):
    """Test top-level UMEEngine API."""

    def test_end_to_end_markdown_matching(self):
        """Verify end-to-end table matching and RDF export."""
        engine = UMEEngine()
        md_table = """
| Requirement | Quantity |
|---|---|
| 250x spirtwood | 250 |
| 77 clovers | 77 |
| 1 tribute | 1 |
"""
        mesh = engine.match_table(md_table, format_hint="markdown")
        self.assertEqual(len(mesh.row_relations), 3)

        # Check normalization happened
        objects = [r.object for r in mesh.row_relations]
        self.assertIn("Spiritwood Plank", objects)
        self.assertIn("Mystic Clover", objects)
        self.assertIn("Mystic Tribute", objects)

        # Export RDF
        ttl = engine.export_rdf(mesh)
        self.assertIn("Spiritwood_Plank", ttl)
        self.assertIn("Mystic_Clover", ttl)
        self.assertIn("Mystic_Tribute", ttl)

    def test_end_to_end_text_classification(self):
        """Verify unstructured text classification and relation extraction."""
        engine = UMEEngine()
        text = "Crafting Nevermore requires 250x Spiritwood Plank and 1 Mystic Tribute."
        result = engine.classify_text(text)
        self.assertTrue(len(result.spans) >= 3)
        self.assertTrue(len(result.relations) >= 2)

        ttl = engine.export_rdf(result)
        self.assertIn("Nevermore", ttl)
        self.assertIn("Spiritwood_Plank", ttl)


if __name__ == "__main__":
    unittest.main()
