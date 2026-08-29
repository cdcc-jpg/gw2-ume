"""Integration tests for Minimum Viable Semantic Layer (MVSL) cross-modal triangulation."""

from __future__ import annotations
import sys
import unittest
from pathlib import Path
import rdflib
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, XSD

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.text.extractor import (
    CrossModalTriangulator,
    TextEntityRelationExtractor,
    TriangulationResult,
    triangulate_table_and_text,
    verify_beverley_principle,
    verify_priory_namespace_consistency,
)
from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.ontology.vocab import GW2, GW2RES, CLASS_ITEM, CLASS_PRECURSOR_WEAPON
from gw2_ume.ontology.namespaces import PRIORY, PRIORY_REF, ITEM


class TestMVSLTriangulation(unittest.TestCase):
    """Test suite evaluating cross-modal triangulation, confidence boosting, and SHACL conformance."""

    def setUp(self) -> None:
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.sample_tables_dir = self.data_dir / "sample_tables"

        # Load Nevermore table
        with open(self.sample_tables_dir / "legendary_nevermore_steps.csv", "r", encoding="utf-8") as f:
            self.nevermore_table_csv = f.read()

        # Load Nevermore unstructured guide
        with open(self.sample_tables_dir / "unstructured_guide_nevermore.txt", "r", encoding="utf-8") as f:
            self.nevermore_guide_txt = f.read()

        # Load Noisy Scraped Tribute
        with open(self.sample_tables_dir / "noisy_scraped_tribute.csv", "r", encoding="utf-8") as f:
            self.noisy_tribute_csv = f.read()

        self.triangulator = CrossModalTriangulator(confidence_boost=0.10)

    def test_nevermore_cross_modal_fusion_and_triangulation(self) -> None:
        """Verify cross-modal triangulation fuses tabular and textual extractions into a valid KG."""
        result: TriangulationResult = self.triangulator.triangulate(
            table_content=self.nevermore_table_csv,
            text_content=self.nevermore_guide_txt,
            table_name="Nevermore Cross-Modal Triangulation",
            validate_shacl=True,
        )

        # 1. Structural assertions
        self.assertGreater(result.total_nodes, 10)
        self.assertGreater(result.total_edges, 10)
        self.assertGreater(len(result.entities), 10)
        self.assertGreater(len(result.triples), 10)

        # 2. Corroborated entities discovery
        self.assertGreater(len(result.corroborated_entities), 0)
        corroborated_labels_lower = [lbl.lower() for lbl in result.corroborated_entities]
        self.assertIn("ravenswood branch", corroborated_labels_lower)
        self.assertIn("spiritwood plank", corroborated_labels_lower)
        self.assertIn("grandmaster craftsman hobbs", corroborated_labels_lower)

        # 3. Confidence boosting verification
        boosted_count = 0
        for ent in result.entities:
            if ent.corroborated:
                self.assertGreaterEqual(ent.boosted_confidence, ent.base_confidence)
                self.assertLessEqual(ent.boosted_confidence, 1.0)
                if ent.base_confidence < 1.0:
                    self.assertGreater(ent.boosted_confidence, ent.base_confidence)
                    boosted_count += 1
        self.assertGreater(boosted_count, 0, "At least some corroborated entities should receive strict confidence boosts.")

        # 4. Corroborated triples verification
        self.assertGreater(len(result.corroborated_triples), 0)
        corroborated_triples_str = [f"{s} {p} {o}" for s, p, o in result.corroborated_triples]
        has_req_ing = any("requiresingredient" in t.lower() for t in corroborated_triples_str)
        self.assertTrue(has_req_ing, "Should have corroborated requiresIngredient triple.")

        # 5. SHACL Conformance
        self.assertEqual(result.validation_status, "CONFORMING")
        self.assertEqual(len(result.validation_violations), 0)

        # 6. Beverley Principle & Priory Consistency
        self.assertTrue(result.beverley_conforming)
        self.assertTrue(result.priory_compliant)

    def test_confidence_boosting_mechanics(self) -> None:
        """Verify mathematical bounds and boosting logic of cross-modal triangulation."""
        res_default = self.triangulator.triangulate(
            table_content=self.nevermore_table_csv,
            text_content=self.nevermore_guide_txt,
            table_name="Boosting Test",
            validate_shacl=False,
        )

        triangulator_high_boost = CrossModalTriangulator(confidence_boost=0.20)
        res_high_boost = triangulator_high_boost.triangulate(
            table_content=self.nevermore_table_csv,
            text_content=self.nevermore_guide_txt,
            table_name="High Boost Test",
            validate_shacl=False,
        )

        for ent_def, ent_high in zip(res_default.entities, res_high_boost.entities):
            if ent_def.corroborated:
                self.assertLessEqual(ent_def.boosted_confidence, ent_high.boosted_confidence)
                self.assertLessEqual(ent_high.boosted_confidence, 1.0)

    def test_beverley_principle_strict_separation(self) -> None:
        """Verify that Beverley Principle strictly separates TBox ontology definitions and ABox data instances."""
        # 1. Clean graph should pass
        clean_graph = build_relational_mesh(self.nevermore_table_csv, "Clean Nevermore").turtle
        g = Graph()
        g.parse(data=clean_graph, format="turtle")
        is_valid, violations = verify_beverley_principle(g)
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)

        # 2. Contaminated graph: Data instance illegally declared as owl:Class
        bad_graph = Graph()
        bad_graph.parse(data=clean_graph, format="turtle")
        bad_graph.add((GW2RES["item/ravenswood_branch"], RDF.type, OWL.Class))
        is_bad_valid, bad_violations = verify_beverley_principle(bad_graph)
        self.assertFalse(is_bad_valid)
        self.assertGreater(len(bad_violations), 0)
        self.assertTrue(any("metaclass" in v for v in bad_violations))

    def test_priory_namespace_consistency_checker(self) -> None:
        """Verify that Priory RDF namespace conventions (def vs ref vs id) are strictly enforced."""
        g = Graph()
        g.bind("priory", PRIORY)
        g.bind("priory-ref", PRIORY_REF)
        g.bind("item", ITEM)

        # Valid triples
        g.add((ITEM["12345"], RDF.type, PRIORY["Item"]))
        g.add((ITEM["12345"], PRIORY["requiresIngredient"], ITEM["67890"]))
        g.add((ITEM["12345"], PRIORY["hasDiscipline"], PRIORY_REF["discipline/artificer"]))

        is_valid, violations = verify_priory_namespace_consistency(g)
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)

        # Invalid triple: Predicate using ref/ instead of def/
        bad_pred = URIRef("https://priory.gw2/ref/invalidPredicate")
        g.add((ITEM["12345"], bad_pred, ITEM["67890"]))

        is_bad_valid, bad_violations = verify_priory_namespace_consistency(g)
        self.assertFalse(is_bad_valid)
        self.assertGreater(len(bad_violations), 0)

    def test_noisy_scraped_table_triangulation_resilience(self) -> None:
        """Verify cross-modal triangulation repairs noisy scraped OCR tables when triangulated with guide text."""
        result: TriangulationResult = self.triangulator.triangulate(
            table_content=self.noisy_tribute_csv,
            text_content=self.nevermore_guide_txt,
            table_name="Noisy Scraped Tribute Triangulation",
            validate_shacl=True,
        )

        self.assertEqual(result.validation_status, "CONFORMING")
        self.assertEqual(len(result.validation_violations), 0)
        self.assertTrue(result.beverley_conforming)
        self.assertGreater(result.total_nodes, 0)
        self.assertGreater(result.total_edges, 0)

    def test_convenience_helper_and_export_formats(self) -> None:
        """Verify triangulate_table_and_text top-level function, Turtle, and JSON-LD serialization."""
        result = triangulate_table_and_text(
            table_content=self.nevermore_table_csv,
            text_content=self.nevermore_guide_txt,
            table_name="Helper Test",
            validate_shacl=True,
        )

        self.assertIsInstance(result, TriangulationResult)
        self.assertIn("@prefix", result.turtle)
        self.assertIn("Nevermore", result.turtle)
        self.assertIsInstance(result.json_ld, (dict, list))


if __name__ == "__main__":
    unittest.main()
