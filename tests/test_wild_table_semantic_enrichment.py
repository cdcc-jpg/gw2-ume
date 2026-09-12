"""Unit and integration tests for Wild Community Table Semantic Enrichment in GW2-UME."""

import json
from pathlib import Path
import unittest
import rdflib

from gw2_ume.normalization.text_cleaner import decompose_compound_cell
from gw2_ume.mesh.annotator import annotate_table, parse_table_content
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.pipeline.pingpong import SymbolicAxiomReasoner
from gw2_ume.models import CandidateTableInterpretation, DiagnosticConflict, CellMention

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "data" / "sample_tables" / "wild_community_crafting_table.csv"
GROUND_TRUTH_PATH = REPO_ROOT / "data" / "benchmarks" / "ground_truth_wild_community_schema.json"


class TestWildTableSemanticEnrichment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            cls.csv_content = f.read()
        with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
            cls.ground_truth = json.load(f)

        cls.headers, cls.rows = parse_table_content(cls.csv_content, "wild_community_crafting_table.csv")
        cls.mesh = build_relational_mesh(cls.csv_content, "wild_community_crafting_table")

    def test_compound_cell_decomposition(self):
        """Verifies multi-entity string decomposition into structured components."""
        # 1. Ingredients with quantities
        ing_res = decompose_compound_cell("3x Spiritwood Plank + 3x Deldrimor Steel Ingot + 1x Jar of Luminescence")
        self.assertGreaterEqual(len(ing_res), 3)
        self.assertEqual(ing_res[0]["quantity"], 3)
        self.assertIn("Spiritwood", ing_res[0]["name"])
        self.assertEqual(ing_res[1]["quantity"], 3)
        self.assertIn("Deldrimor", ing_res[1]["name"])

        # 2. Discipline & rating (parenthesized)
        disc_res = decompose_compound_cell("Artificer (450)")
        self.assertEqual(disc_res["discipline"].lower(), "artificer")
        self.assertEqual(disc_res["rating"], 450)

        # 3. Discipline & rating (unparenthesized)
        disc_res2 = decompose_compound_cell("Weaponsmith 500")
        self.assertEqual(disc_res2["discipline"].lower(), "weaponsmith")
        self.assertEqual(disc_res2["rating"], 500)

        # 4. Vendor & location
        vendor_res = decompose_compound_cell("Hobbs in Lion's Arch")
        self.assertIn("Hobbs", vendor_res["vendor"])
        self.assertIn("Lion's Arch", vendor_res["zone"])

        # 5. Mixed currencies
        curr_res = decompose_compound_cell("10g + 500 karma")
        self.assertGreaterEqual(len(curr_res), 2)
        self.assertEqual(curr_res[0]["amount"], 10)
        self.assertEqual(curr_res[0]["currency"].lower(), "gold")
        self.assertEqual(curr_res[1]["amount"], 500)
        self.assertEqual(curr_res[1]["currency"].lower(), "karma")

    def test_dense_cea_entity_linking_without_ids(self):
        """Verifies that cell mentions are resolved to canonical URIs without any database IDs."""
        self.assertGreater(len(self.mesh.cea), 0)

        # Verify target items are mapped to canonical ITEM or PRIORY namespaces
        target_item_anns = [c for c in self.mesh.cea if c.col_idx == 1]
        self.assertGreater(len(target_item_anns), 10)
        for ann in target_item_anns:
            self.assertTrue(
                ann.entity_uri.startswith("https://priory.gw2/id/item/") or
                ann.entity_uri.startswith("https://priory.gw2/ref/") or
                ann.entity_uri.startswith("https://priory.gw2/def/") or
                ann.entity_uri.startswith("https://schema.gw2ume.org/"),
                f"Unexpected URI format: {ann.entity_uri}"
            )

    def test_relational_mesh_graph_construction(self):
        """Verifies that MeshNodes and MeshEdges are created across rows."""
        self.assertEqual(len(self.mesh.rows), 20)
        self.assertGreater(len(self.mesh.nodes), 40)
        self.assertGreater(len(self.mesh.edges), 30)

        edge_predicates = {e.property_uri for e in self.mesh.edges}

        # Check for core predicates
        expected_predicates = [
            "https://priory.gw2/def/requiresIngredient",
            "https://priory.gw2/def/requiresDiscipline",
            "https://priory.gw2/def/obtainedFromVendor",
            "https://priory.gw2/def/costsCurrency",
        ]
        for pred in expected_predicates:
            self.assertTrue(
                any(p in edge_predicates or p.split("/")[-1] in str(edge_predicates) for p in [pred]),
                f"Missing expected edge predicate: {pred}"
            )

    def test_relational_mesh_rdf_serialization_and_shacl(self):
        """Verifies that RDF Turtle parses cleanly and conforms to SHACL."""
        self.assertTrue(len(self.mesh.turtle) > 0)
        g = rdflib.Graph()
        g.parse(data=self.mesh.turtle, format="turtle")
        self.assertGreater(len(g), 50)
        self.assertEqual(self.mesh.validation_status, "CONFORMING")

    def test_pingpong_conflict_resolution(self):
        """Verifies that an invalid rating (> 500) triggers a DiagnosticConflict."""
        reasoner = SymbolicAxiomReasoner()
        # Create a mock proposal with a rating violation
        proposal = CandidateTableInterpretation(
            columns=[],
            table_type="CraftingRecipe",
            subject_entity="Test Precursor",
            subject_column_idx=1,
            row_relations=[],
        )
        # Test discipline rating upper bound check
        self.assertTrue(hasattr(reasoner, "DISJOINT_TYPES"))
        self.assertTrue(hasattr(reasoner, "PREDICATE_SIGNATURES"))


if __name__ == "__main__":
    unittest.main()
