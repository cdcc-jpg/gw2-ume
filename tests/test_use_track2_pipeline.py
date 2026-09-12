"""Comprehensive Unit Test Suite for USE/USEY Track 2 Pipeline.

Verifies:
1. Value-Based Classification (Stage 2) with zero header bias.
2. Single & Multi-Anchor Sub-Entity Routing (Stage 3b & Stage 4), including CRYSTAL16 solid-state models.
3. Stage 5 Cascade Ladder Rungs (Exact, Normalised, TokenSubset, Containment, Fuzzy, FAISS-Edge).
4. Suffix Sanity Re-probes (_ID, _VALUE/_UNIT, _PERCENT).
5. Stage 5a Deterministic Axiom Veto (AxiomFilter-Unique).
6. Stage 6 Concept-Shaped Object Resolution (string cascade & embedding vs literal).
7. Stage 7 Trust Scoring & Downgrade Rule (HITL Validation downgrade).
8. Row Type Conflict checking (Row_Type_Conflict).
9. Full End-to-End Table Execution producing triples.csv and coverage_report.md.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import rdflib
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from gw2_ume.use_pipeline.stage0_setup import OntologyIndex
from gw2_ume.use_pipeline.stage2_classification import ValueClassifier
from gw2_ume.use_pipeline.stage3_table_checks import TableChecker
from gw2_ume.use_pipeline.stage4_row_loop import RowLoopExecutor, Triple
from gw2_ume.use_pipeline.stage5_cascade import MatchResult, PredicateResolver
from gw2_ume.use_pipeline.stage6_object_resolution import ObjectResolver
from gw2_ume.use_pipeline.stage7_trust_scoring import TrustScorer
from gw2_ume.use_pipeline.stage8_assembly import TriplesAssembler
from gw2_ume.use_pipeline.pipeline import USEPipeline


TEST_NS = Namespace("http://example.org/test#")


def create_mock_solid_state_ontology() -> Graph:
    """Creates a dynamic RDF graph modeling solid-state crystal calculations (e.g. CRYSTAL16).
    Zero hardcoded domain assumptions in code: graph defines all classes, properties, domains, ranges.
    """
    g = Graph()
    g.bind("test", TEST_NS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    # Classes
    Calculation = TEST_NS.Calculation
    Solute = TEST_NS.Solute
    ComputationTask = TEST_NS.ComputationTask
    CrystalSystem = TEST_NS.CrystalSystem
    BiologicalSample = TEST_NS.BiologicalSample

    for c in [Calculation, Solute, ComputationTask, CrystalSystem, BiologicalSample]:
        g.add((c, RDF.type, OWL.Class))

    # Labels and comments
    g.add((Calculation, RDFS.label, Literal("Calculation", datatype=XSD.string)))
    g.add((Calculation, RDFS.comment, Literal("A quantum chemical solid-state calculation run.", datatype=XSD.string)))

    g.add((Solute, RDFS.label, Literal("Solute", datatype=XSD.string)))
    g.add((Solute, RDFS.comment, Literal("A chemical solute or crystal structure.", datatype=XSD.string)))

    g.add((ComputationTask, RDFS.label, Literal("Computation Task", datatype=XSD.string)))
    g.add((ComputationTask, RDFS.comment, Literal("An execution job or compute task.", datatype=XSD.string)))

    g.add((CrystalSystem, RDFS.label, Literal("Crystal System", datatype=XSD.string)))
    g.add((CrystalSystem, RDFS.comment, Literal("Crystallographic classification.", datatype=XSD.string)))

    g.add((BiologicalSample, RDFS.label, Literal("Biological Sample", datatype=XSD.string)))
    g.add((BiologicalSample, RDFS.comment, Literal("Organic living tissue specimen.", datatype=XSD.string)))

    # Declare disjointness between Calculation and BiologicalSample to test Row_Type_Conflict
    g.add((Calculation, OWL.disjointWith, BiologicalSample))

    # Object Properties (Inter-Entity Links)
    hasSolute = TEST_NS.hasSolute
    g.add((hasSolute, RDF.type, OWL.ObjectProperty))
    g.add((hasSolute, RDFS.label, Literal("has solute", datatype=XSD.string)))
    g.add((hasSolute, RDFS.domain, Calculation))
    g.add((hasSolute, RDFS.range, Solute))

    hasTask = TEST_NS.hasTask
    g.add((hasTask, RDF.type, OWL.ObjectProperty))
    g.add((hasTask, RDFS.label, Literal("has task", datatype=XSD.string)))
    g.add((hasTask, RDFS.domain, Calculation))
    g.add((hasTask, RDFS.range, ComputationTask))

    # Datatype Properties
    totalEnergy = TEST_NS.totalEnergy
    g.add((totalEnergy, RDF.type, OWL.DatatypeProperty))
    g.add((totalEnergy, RDFS.label, Literal("total energy", datatype=XSD.string)))
    g.add((totalEnergy, RDFS.domain, Calculation))
    g.add((totalEnergy, RDFS.range, XSD.double))

    convergenceStatus = TEST_NS.convergenceStatus
    g.add((convergenceStatus, RDF.type, OWL.DatatypeProperty))
    g.add((convergenceStatus, RDFS.label, Literal("convergence status", datatype=XSD.string)))
    g.add((convergenceStatus, RDFS.domain, Calculation))
    g.add((convergenceStatus, RDFS.range, XSD.string))

    soluteFormula = TEST_NS.soluteFormula
    g.add((soluteFormula, RDF.type, OWL.DatatypeProperty))
    g.add((soluteFormula, RDFS.label, Literal("solute formula", datatype=XSD.string)))
    g.add((soluteFormula, RDFS.domain, Solute))
    g.add((soluteFormula, RDFS.range, XSD.string))

    soluteCharge = TEST_NS.soluteCharge
    g.add((soluteCharge, RDF.type, OWL.DatatypeProperty))
    g.add((soluteCharge, RDFS.label, Literal("solute charge", datatype=XSD.string)))
    g.add((soluteCharge, RDFS.domain, Solute))
    g.add((soluteCharge, RDFS.range, XSD.integer))

    taskCpuTime = TEST_NS.taskCpuTime
    g.add((taskCpuTime, RDF.type, OWL.DatatypeProperty))
    g.add((taskCpuTime, RDFS.label, Literal("task cpu time", datatype=XSD.string)))
    g.add((taskCpuTime, RDFS.domain, ComputationTask))
    g.add((taskCpuTime, RDFS.range, XSD.float))

    crystalSpaceGroup = TEST_NS.crystalSpaceGroup
    g.add((crystalSpaceGroup, RDF.type, OWL.DatatypeProperty))
    g.add((crystalSpaceGroup, RDFS.label, Literal("space group", datatype=XSD.string)))
    g.add((crystalSpaceGroup, RDFS.domain, Solute))
    g.add((crystalSpaceGroup, RDFS.range, XSD.string))

    bioTissueType = TEST_NS.bioTissueType
    g.add((bioTissueType, RDF.type, OWL.DatatypeProperty))
    g.add((bioTissueType, RDFS.label, Literal("tissue type", datatype=XSD.string)))
    g.add((bioTissueType, RDFS.domain, BiologicalSample))
    g.add((bioTissueType, RDFS.range, XSD.string))

    # Properties for Axiom Veto Testing
    scoreValue = TEST_NS.scoreValue
    g.add((scoreValue, RDF.type, OWL.DatatypeProperty))
    g.add((scoreValue, RDFS.label, Literal("numerical score index", datatype=XSD.string)))
    g.add((scoreValue, RDFS.comment, Literal("A numeric numerical metric rating.", datatype=XSD.string)))
    g.add((scoreValue, RDFS.range, XSD.double))

    scoreDescription = TEST_NS.scoreDescription
    g.add((scoreDescription, RDF.type, OWL.DatatypeProperty))
    g.add((scoreDescription, RDFS.label, Literal("score summary notes", datatype=XSD.string)))
    g.add((scoreDescription, RDFS.comment, Literal("Textual rating summary.", datatype=XSD.string)))
    g.add((scoreDescription, RDFS.range, XSD.string))

    scoreEntity = TEST_NS.scoreEntity
    g.add((scoreEntity, RDF.type, OWL.ObjectProperty))
    g.add((scoreEntity, RDFS.label, Literal("evaluated subject calculation", datatype=XSD.string)))
    g.add((scoreEntity, RDFS.range, Calculation))

    # Concept class individuals
    monoclinic = TEST_NS.Monoclinic
    g.add((monoclinic, RDF.type, OWL.Class))
    g.add((monoclinic, RDFS.label, Literal("Monoclinic", datatype=XSD.string)))
    g.add((monoclinic, RDFS.subClassOf, CrystalSystem))

    triclinic = TEST_NS.Triclinic
    g.add((triclinic, RDF.type, OWL.Class))
    g.add((triclinic, RDFS.label, Literal("Triclinic", datatype=XSD.string)))
    g.add((triclinic, RDFS.subClassOf, CrystalSystem))

    return g


class TestUSETrack2Pipeline(unittest.TestCase):
    """Exhaustive test suite verifying Stages 2 through 8 and the pipeline runner."""

    @classmethod
    def setUpClass(cls):
        cls.graph = create_mock_solid_state_ontology()
        cls.index = OntologyIndex(cls.graph, use_sentence_transformers=False)
        cls.resolver = PredicateResolver(cls.index, enable_llm=False)
        cls.object_resolver = ObjectResolver(cls.index)
        cls.trust_scorer = TrustScorer()
        cls.classifier = ValueClassifier()
        cls.checker = TableChecker(cls.index, cls.resolver)
        cls.executor = RowLoopExecutor(
            ontology_index=cls.index,
            predicate_resolver=cls.resolver,
            object_resolver=cls.object_resolver,
            trust_scorer=cls.trust_scorer,
        )
        cls.assembler = TriplesAssembler()
        cls.temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Test 1: Stage 2 Value-Based Classification
    # -------------------------------------------------------------------------
    def test_01_value_based_classification(self):
        """Verify structural role assignment based purely on cell values (zero header bias)."""
        df = pd.DataFrame({
            "col_a": ["11111111-2222-3333-4444-555555555555",
                      "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                      "12345678-1234-5678-1234-567812345678"],
            "col_b": ["FK-101", "FK-101", "FK-102"],  # repeating ID
            "col_c": ["-154.32", "-155.01", "-153.89"],  # numeric
            "col_d": ["50.5 eV", "60.2 eV", "75.1 eV"],  # measurement
            "col_e": ["Monoclinic", "Triclinic", "Monoclinic"],  # categorical
            "col_f": ["2026-09-12 12:00:00", "2026-09-12 13:00:00", "2026-09-12 14:00:00"],  # timestamp
            "col_g": ["Detailed free text log describing the convergence steps of the run",
                      "Second iteration finished with high gradient variance",
                      "Final step converged within 14 cycles successfully"],  # text
        })

        roles = self.classifier.classify_table(df)

        self.assertEqual(roles["col_a"].role, "Entity ID")
        self.assertEqual(roles["col_b"].role, "Foreign Key")
        self.assertEqual(roles["col_c"].role, "Numeric property")
        self.assertEqual(roles["col_d"].role, "Measurement value/unit pair")
        self.assertEqual(roles["col_e"].role, "Categorical")
        self.assertEqual(roles["col_f"].role, "Timestamp")
        self.assertEqual(roles["col_g"].role, "Text")

    # -------------------------------------------------------------------------
    # Test 2: Stage 5 Cascade Ladder Rungs
    # -------------------------------------------------------------------------
    def test_02_cascade_ladder_rungs(self):
        """Verify the 6-step cascade ladder: Exact, Normalised, TokenSubset, Containment, Fuzzy, FAISS-Edge."""
        # 1. Exact Match (0.98)
        res_exact = self.resolver._run_ladder("total energy")
        self.assertIsNotNone(res_exact)
        self.assertEqual(res_exact.method, "Stage0-Exact")
        self.assertAlmostEqual(res_exact.confidence, 0.98, places=2)
        self.assertFalse(res_exact.review_flag)

        # 2. Normalised Match (0.95)
        res_norm = self.resolver._run_ladder("TOTAL_ENERGY")
        self.assertIsNotNone(res_norm)
        self.assertEqual(res_norm.method, "Stage0-Normalised")
        self.assertAlmostEqual(res_norm.confidence, 0.95, places=2)

        # 3. TokenSubset Match (0.70 - 0.92)
        res_subset = self.resolver._run_ladder("solute formula string format")
        self.assertIsNotNone(res_subset)
        self.assertEqual(res_subset.method, "Stage0-TokenSubset")
        self.assertGreaterEqual(res_subset.confidence, 0.70)
        self.assertLessEqual(res_subset.confidence, 0.92)

        # 4. Containment Match (0.51 - 0.85)
        res_cont = self.resolver._run_ladder("formula")
        self.assertIsNotNone(res_cont)
        self.assertIn(res_cont.method, ("Stage0-Containment", "Stage0-TokenSubset"))
        self.assertGreaterEqual(res_cont.confidence, 0.51)

        # 5. Fuzzy Match (ratio * 0.92)
        res_fuzzy = self.resolver._run_ladder("totall energgy")
        self.assertIsNotNone(res_fuzzy)
        self.assertEqual(res_fuzzy.method, "Stage0-Fuzzy")
        self.assertGreaterEqual(res_fuzzy.confidence, 0.60)

        # 6. Suffix probe
        res_sfx = self.resolver.resolve("TOTAL_ENERGY_VALUE", "Numeric property")
        self.assertIsNotNone(res_sfx)
        self.assertIn("totalEnergy", res_sfx.uri)

    # -------------------------------------------------------------------------
    # Test 3: Stage 5a Deterministic Axiom Veto (AxiomFilter-Unique)
    # -------------------------------------------------------------------------
    def test_03_stage5a_deterministic_axiom_veto(self):
        """Verify that when weak match occurs, Stage 5a drops candidates whose rdfs:range
        contradicts the column role, and if exactly 1 survives, accepts it as AxiomFilter-Unique
        with confidence 0.66 without calling an LLM.
        """
        # Search query 'metric rating': has 3 candidates in mock ontology:
        # 1. scoreValue (range xsd:double) -> Valid for Numeric property
        # 2. scoreDescription (range xsd:string) -> Vetoed for Numeric property
        # 3. scoreEntity (range Calculation, ObjectProperty) -> Vetoed for Numeric property
        res = self.resolver.resolve(
            column_name="metric rating",
            column_role="Numeric property",
            sample_values=[12.5, 14.8, 19.2],
        )

        self.assertIsNotNone(res)
        # Verify it chose scoreValue
        self.assertIn("scoreValue", res.uri)
        # Since exactly 1 numeric property survived axiom veto, must be AxiomFilter-Unique!
        self.assertEqual(res.method, "AxiomFilter-Unique")
        self.assertEqual(res.confidence, 0.66)
        self.assertFalse(res.review_flag)

    # -------------------------------------------------------------------------
    # Test 4: Stage 6 Concept-Shaped Object Resolution
    # -------------------------------------------------------------------------
    def test_04_concept_object_resolution(self):
        """Verify concept resolution against ontology classes and literal fallback."""
        # 1. Matches ontology class Monoclinic
        res_cat = self.object_resolver.resolve(
            value="Monoclinic",
            column_role="Categorical",
        )
        self.assertTrue(res_cat.is_concept)
        self.assertIn("Monoclinic", res_cat.resolved_value)
        self.assertGreaterEqual(res_cat.confidence, 0.75)
        self.assertEqual(res_cat.method, "Concept-StringMatch")

        # 2. UUID in categorical column is skipped and remains literal
        res_uuid = self.object_resolver.resolve(
            value="11111111-2222-3333-4444-555555555555",
            column_role="Categorical",
        )
        self.assertFalse(res_uuid.is_concept)
        self.assertEqual(res_uuid.method, "Literal-Value")

        # 3. Numeric value remains literal
        res_num = self.object_resolver.resolve(
            value="-154.32",
            column_role="Numeric property",
        )
        self.assertFalse(res_num.is_concept)
        self.assertEqual(res_num.resolved_value, "-154.32")
        self.assertEqual(res_num.method, "Literal-Value")

    # -------------------------------------------------------------------------
    # Test 5: Stage 7 Trust Scoring & Downgrade Rule
    # -------------------------------------------------------------------------
    def test_05_trust_scoring_and_downgrade_rule(self):
        """Verify Module_Action assignment and the Downgrade Rule:
        If predicate review_flag is True, downgrade to HITL Validation even if object is confident!
        """
        # Case A: Confident predicate (review=False) + Confident concept object (conf >= 0.62)
        # -> Deterministic Mapped
        pred_strong = MatchResult(
            uri="http://example.org/test#crystalSpaceGroup",
            label="space group",
            confidence=0.98,
            method="Stage0-Exact",
            review_flag=False,
        )
        from gw2_ume.use_pipeline.stage6_object_resolution import ObjectResolutionResult
        obj_strong = ObjectResolutionResult(
            raw_value="Monoclinic",
            resolved_value="http://example.org/test#Monoclinic",
            is_concept=True,
            confidence=0.95,
            method="Concept-StringMatch",
        )
        score_a = self.trust_scorer.score_triple(pred_strong, obj_strong)
        self.assertEqual(score_a.module_action, "Deterministic Mapped")
        self.assertFalse(score_a.review_flag)

        # Case B: Weak/Review predicate (review=True) + Confident concept object (conf >= 0.62)
        # -> DOWNGRADED to HITL Validation!
        pred_weak = MatchResult(
            uri="http://example.org/test#crystalSpaceGroup",
            label="space group",
            confidence=0.60,
            method="FAISS-Edge",
            review_flag=True,  # Weak!
        )
        score_b = self.trust_scorer.score_triple(pred_weak, obj_strong)
        self.assertEqual(score_b.module_action, "HITL Validation")
        self.assertTrue(score_b.review_flag)
        self.assertIn("Downgraded", score_b.rationale)

        # Case C: Confident predicate + Literal object -> Literal Typed
        obj_literal = ObjectResolutionResult(
            raw_value="-154.32",
            resolved_value="-154.32",
            is_concept=False,
            confidence=1.0,
            method="Literal-Value",
        )
        score_c = self.trust_scorer.score_triple(pred_strong, obj_literal)
        self.assertEqual(score_c.module_action, "Literal Typed")
        self.assertFalse(score_c.review_flag)

        # Case D: Low confidence concept (< 0.40) -> Literal Boxed
        obj_low = ObjectResolutionResult(
            raw_value="UncertainStructure",
            resolved_value="http://example.org/test#Uncertain",
            is_concept=True,
            confidence=0.35,
            method="Concept-EmbeddingMatch",
        )
        score_d = self.trust_scorer.score_triple(pred_strong, obj_low)
        self.assertEqual(score_d.module_action, "Literal Boxed")
        self.assertTrue(score_d.review_flag)

    # -------------------------------------------------------------------------
    # Test 6: Single & Multi-Anchor Sub-Entity Routing (CRYSTAL16 Model)
    # -------------------------------------------------------------------------
    def test_06_sub_entity_anchor_routing(self):
        """Verify multi-anchor routing:
        Primary: CALCULATION_ID
        Sub-entity 1: SOLUTE_ID (anchors SOLUTE_FORMULA and SOLUTE_CHARGE)
        Sub-entity 2: TASK_ID (anchors TASK_CPU_TIME)
        Checks subject swapping and emission of Schema-Driven-SubjectLink triples.
        """
        df = pd.DataFrame({
            "CALCULATION_ID": ["CALC-001", "CALC-002"],
            "TOTAL_ENERGY": ["-154.32", "-289.45"],
            "SOLUTE_ID": ["SOL-99", "SOL-100"],
            "SOLUTE_FORMULA": ["NaCl", "TiO2"],
            "SOLUTE_CHARGE": ["0", "0"],
            "TASK_ID": ["TSK-801", "TSK-802"],
            "TASK_CPU_TIME": ["120.5", "450.2"],
        })

        roles = self.classifier.classify_table(df)
        ctx = self.checker.analyze_table(df, roles)

        # Verify anchors were detected
        self.assertIn("SOLUTE_ID", ctx.anchors)
        self.assertIn("TASK_ID", ctx.anchors)

        # Verify sibling mapping
        self.assertEqual(ctx.col_to_anchor.get("SOLUTE_FORMULA"), "SOLUTE_ID")
        self.assertEqual(ctx.col_to_anchor.get("SOLUTE_CHARGE"), "SOLUTE_ID")
        self.assertEqual(ctx.col_to_anchor.get("TASK_CPU_TIME"), "TASK_ID")

        # Execute row loop
        triples = self.executor.execute_table(df, roles, ctx)

        # 1. Verify subject swapping: SOLUTE_FORMULA triples must have subject 'SOL-99' (not 'CALC-001')
        solute_triples = [t for t in triples if t.column_name == "SOLUTE_FORMULA"]
        self.assertEqual(len(solute_triples), 2)
        self.assertEqual(solute_triples[0].subject, "SOL-99")
        self.assertEqual(solute_triples[1].subject, "SOL-100")

        # 2. Verify subject swapping: TASK_CPU_TIME triples must have subject 'TSK-801'
        task_triples = [t for t in triples if t.column_name == "TASK_CPU_TIME"]
        self.assertEqual(len(task_triples), 2)
        self.assertEqual(task_triples[0].subject, "TSK-801")
        self.assertEqual(task_triples[1].subject, "TSK-802")

        # 3. Verify Stage 3c Schema-Driven-SubjectLink triples
        link_triples = [t for t in triples if t.method == "Schema-Driven-SubjectLink"]
        self.assertGreaterEqual(len(link_triples), 4)

        # Primary CALC-001 must link to SOL-99 and TSK-801
        calc1_links = [t for t in link_triples if t.subject == "CALC-001"]
        link_objects = [t.object for t in calc1_links]
        self.assertIn("SOL-99", link_objects)
        self.assertIn("TSK-801", link_objects)

    # -------------------------------------------------------------------------
    # Test 7: Row Type Conflict Detection
    # -------------------------------------------------------------------------
    def test_07_row_type_conflict(self):
        """Verify that when a row contains predicates from disjoint domains
        (Calculation and BiologicalSample), Row_Type_Conflict is flagged.
        """
        df = pd.DataFrame({
            "CALCULATION_ID": ["CALC-001"],
            "TOTAL_ENERGY": ["-154.32"],    # domain: Calculation
            "tissue type": ["Liver Tissue"], # domain: BiologicalSample (disjoint with Calculation)
        })

        roles = self.classifier.classify_table(df)
        ctx = self.checker.analyze_table(df, roles)
        triples = self.executor.execute_table(df, roles, ctx)

        conflict_triples = [t for t in triples if "Row_Type_Conflict" in t.method]
        self.assertGreater(len(conflict_triples), 0)
        for t in conflict_triples:
            self.assertTrue(t.review_flag)
            self.assertEqual(t.module_action, "HITL Validation")

    # -------------------------------------------------------------------------
    # Test 8: Full End-to-End Pipeline Execution
    # -------------------------------------------------------------------------
    def test_08_full_end_to_end_pipeline(self):
        """Verify unified USEPipeline execution on CSV producing triples.csv and coverage_report.md."""
        csv_path = os.path.join(self.temp_dir, "test_table.csv")
        out_dir = os.path.join(self.temp_dir, "output")

        df = pd.DataFrame({
            "CALCULATION_ID": ["CALC-001", "CALC-002", "CALC-003"],
            "TOTAL_ENERGY": ["-154.32", "-289.45", "-512.10"],
            "convergence status": ["Converged", "Converged", "Failed"],
            "SOLUTE_ID": ["SOL-99", "SOL-100", "SOL-101"],
            "SOLUTE_FORMULA": ["NaCl", "TiO2", "SiO2"],
            "space group": ["Monoclinic", "Triclinic", "Monoclinic"],
        })
        df.to_csv(csv_path, index=False)

        pipeline = USEPipeline(
            ontology_graph_or_path=self.graph,
            enable_llm=False,
            use_sentence_transformers=False,
        )

        result = pipeline.run(csv_path, output_dir=out_dir)

        # Check returned result
        self.assertGreater(result.total_triples, 0)
        self.assertGreaterEqual(result.mapped_ratio, 0.80)
        self.assertIsNotNone(result.triples_csv_path)
        self.assertIsNotNone(result.coverage_report_md_path)

        # Verify triples.csv existence and headers
        self.assertTrue(os.path.exists(result.triples_csv_path))
        df_triples = pd.read_csv(result.triples_csv_path)
        expected_cols = ["subject", "predicate", "object", "confidence", "method", "review_flag", "module_action"]
        self.assertListEqual(list(df_triples.columns), expected_cols)

        # Verify coverage_report.md
        self.assertTrue(os.path.exists(result.coverage_report_md_path))
        with open(result.coverage_report_md_path, "r", encoding="utf-8") as f:
            report_content = f.read()

        self.assertIn("USE Pipeline Track 2 - Semantic Assembly & Coverage Report", report_content)
        self.assertIn("Module_Action Distribution", report_content)
        self.assertIn("Deterministic Mapped", report_content)
        self.assertIn("Literal Typed", report_content)

    # -------------------------------------------------------------------------
    # Test 9: Stage 5a LLM-Reranked Mode
    # -------------------------------------------------------------------------
    def test_09_llm_reranked_mode(self):
        """Verify Stage 5a when multiple candidates survive axiom veto and LLM is invoked."""
        # Mock LLM callable returning '1 HIGH'
        def mock_llm(prompt: str) -> str:
            return "1 HIGH"

        resolver_llm = PredicateResolver(
            self.index,
            enable_llm=True,
            llm_client=mock_llm,
        )

        # Query with text role where multiple text/string properties survive
        res = resolver_llm.resolve(
            column_name="status description note",
            column_role="Text",
            sample_values=["Converged", "Done"],
        )

        self.assertIsNotNone(res)
        self.assertEqual(res.method, "LLM-Reranked")
        self.assertEqual(res.confidence, 0.75)
        self.assertTrue(res.review_flag)

    # -------------------------------------------------------------------------
    # Test 10: Pre-Flight SHACL Validation
    # -------------------------------------------------------------------------
    def test_10_shacl_preflight_validation(self):
        """Verify pre-flight SHACL validation against custom SHACL shapes."""
        shacl_g = Graph()
        # Minimal SHACL shape requiring totalEnergy to be numeric
        shape_ttl = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix test: <http://example.org/test#> .

        test:CalculationShape a sh:NodeShape ;
            sh:targetClass test:Calculation ;
            sh:property [
                sh:path test:totalEnergy ;
                sh:datatype xsd:double ;
            ] .
        """
        shacl_g.parse(data=shape_ttl, format="turtle")

        triples = [
            Triple(
                subject="http://example.org/test#calc_01",
                predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                object="http://example.org/test#Calculation",
                confidence=1.0,
                method="TypeAssertion",
                review_flag=False,
                module_action="Deterministic Mapped",
                row_idx=0,
                column_name="type",
            ),
            Triple(
                subject="http://example.org/test#calc_01",
                predicate="http://example.org/test#totalEnergy",
                object="-154.32",
                confidence=0.98,
                method="Stage0-Exact",
                review_flag=False,
                module_action="Literal Typed",
                row_idx=0,
                column_name="TOTAL_ENERGY",
            ),
        ]

        result = self.assembler.assemble(triples, shacl_shapes_graph=shacl_g)
        self.assertIsNotNone(result.shacl_conforms)
        self.assertTrue(result.shacl_conforms)

    # -------------------------------------------------------------------------
    # Test 11: Real Priory Core Ontology Execution
    # -------------------------------------------------------------------------
    def test_11_real_priory_ontology(self):
        """Verify dynamic loading and execution against actual Priory Core ontology without domain hardcoding."""
        priory_core_path = "/Users/clementd/Documents/GitHub/gw2-priory-def/ontology/priory_core.ttl"
        if not os.path.exists(priory_core_path):
            self.skipTest("priory_core.ttl not found")

        pipeline = USEPipeline(
            ontology_graph_or_path=priory_core_path,
            use_sentence_transformers=False,
        )

        self.assertGreater(len(pipeline.index.classes), 30)
        self.assertGreater(len(pipeline.index.properties), 30)

        df = pd.DataFrame({
            "item_id": ["12452", "12453"],
            "item_name": ["Iron Broadsword", "Steel Greatsword"],
            "item_rarity": ["Fine", "Masterwork"],
        })

        result = pipeline.run(df)
        self.assertGreater(result.total_triples, 0)
        self.assertGreaterEqual(result.mapped_ratio, 0.80)

    # -------------------------------------------------------------------------
    # Test 12: SHACL Bounds & Comment Regex Introspection
    # -------------------------------------------------------------------------
    def test_12_shacl_bounds_and_comment_regex_introspection(self):
        """Verify dynamic introspection of sh:minInclusive/sh:maxInclusive and comment regex."""
        g = Graph()
        SHACL = Namespace("http://www.w3.org/ns/shacl#")
        g.bind("sh", SHACL)
        g.bind("test", TEST_NS)

        prop_shacl = TEST_NS.boundedSpeed
        g.add((prop_shacl, RDF.type, OWL.DatatypeProperty))
        g.add((prop_shacl, RDFS.label, Literal("bounded speed", datatype=XSD.string)))
        g.add((prop_shacl, RDFS.range, XSD.double))

        shape = TEST_NS.SpeedShape
        g.add((shape, RDF.type, SHACL.NodeShape))
        g.add((shape, SHACL.path, prop_shacl))
        g.add((shape, SHACL.minInclusive, Literal(1.0, datatype=XSD.double)))
        g.add((shape, SHACL.maxInclusive, Literal(120.0, datatype=XSD.double)))

        prop_comment = TEST_NS.characterLevel
        g.add((prop_comment, RDF.type, OWL.DatatypeProperty))
        g.add((prop_comment, RDFS.label, Literal("character level", datatype=XSD.string)))
        g.add((prop_comment, RDFS.comment, Literal("Item character level requirement (0-80).", datatype=XSD.string)))
        g.add((prop_comment, RDFS.range, XSD.integer))

        prop_comment_to = TEST_NS.craftingRating
        g.add((prop_comment_to, RDF.type, OWL.DatatypeProperty))
        g.add((prop_comment_to, RDFS.label, Literal("crafting rating", datatype=XSD.string)))
        g.add((prop_comment_to, RDFS.comment, Literal("Crafting skill level (0 to 500)", datatype=XSD.string)))
        g.add((prop_comment_to, RDFS.range, XSD.integer))

        idx = OntologyIndex(g, use_sentence_transformers=False)

        info_shacl = idx.properties[str(prop_shacl)]
        self.assertEqual(info_shacl.min_inclusive, 1.0)
        self.assertEqual(info_shacl.max_inclusive, 120.0)

        info_comment = idx.properties[str(prop_comment)]
        self.assertEqual(info_comment.min_inclusive, 0.0)
        self.assertEqual(info_comment.max_inclusive, 80.0)

        info_to = idx.properties[str(prop_comment_to)]
        self.assertEqual(info_to.min_inclusive, 0.0)
        self.assertEqual(info_to.max_inclusive, 500.0)

    # -------------------------------------------------------------------------
    # Test 13: Axiom-Aware Ladder Filtering
    # -------------------------------------------------------------------------
    def test_13_axiom_aware_ladder_filtering(self):
        """Verify candidate properties violating column_role axioms are NEVER returned by ladder."""
        g = Graph()
        prop_str = TEST_NS.statusNote
        g.add((prop_str, RDF.type, OWL.DatatypeProperty))
        g.add((prop_str, RDFS.label, Literal("status note", datatype=XSD.string)))
        g.add((prop_str, RDFS.range, XSD.string))

        prop_bool = TEST_NS.isActive
        g.add((prop_bool, RDF.type, OWL.DatatypeProperty))
        g.add((prop_bool, RDFS.label, Literal("is active", datatype=XSD.string)))
        g.add((prop_bool, RDFS.range, XSD.boolean))

        prop_num = TEST_NS.metricCount
        g.add((prop_num, RDF.type, OWL.DatatypeProperty))
        g.add((prop_num, RDFS.label, Literal("metric count", datatype=XSD.string)))
        g.add((prop_num, RDFS.range, XSD.integer))

        idx = OntologyIndex(g, use_sentence_transformers=False)
        resolver = PredicateResolver(idx, enable_llm=False)

        # Exact match for string property, but column role is Numeric -> MUST return None (filtered out!)
        res_str_numeric = resolver._run_ladder("status note", column_role="Numeric property")
        self.assertIsNone(res_str_numeric)

        # Exact match for boolean property, but column role is Numeric -> MUST return None
        res_bool_numeric = resolver._run_ladder("is active", column_role="Numeric property")
        self.assertIsNone(res_bool_numeric)

        # Exact match for string property with Text role -> returns property
        res_str_text = resolver._run_ladder("status note", column_role="Text")
        self.assertIsNotNone(res_str_text)
        self.assertEqual(res_str_text.uri, str(prop_str))

        # Exact match for numeric property with Numeric role -> returns property
        res_num_numeric = resolver._run_ladder("metric count", column_role="Numeric property")
        self.assertIsNotNone(res_num_numeric)
        self.assertEqual(res_num_numeric.uri, str(prop_num))

    # -------------------------------------------------------------------------
    # Test 14: Same-Range Competitor & Deterministic Fallback Arbiter
    # -------------------------------------------------------------------------
    def test_14_same_range_competitor_and_fallback_arbiter(self):
        """Verify near-tie / same-range competitor detection routes to Stage 5a Arbiter,
        and deterministic fallback arbiter returns Arbiter-Reranked when LLM is offline.
        """
        g = Graph()
        prop_a = TEST_NS.perfRatingScore
        g.add((prop_a, RDF.type, OWL.DatatypeProperty))
        g.add((prop_a, RDFS.label, Literal("performance rating score", datatype=XSD.string)))
        g.add((prop_a, RDFS.comment, Literal("System performance rating evaluation.", datatype=XSD.string)))
        g.add((prop_a, RDFS.range, XSD.integer))

        prop_b = TEST_NS.perfRatingIndex
        g.add((prop_b, RDF.type, OWL.DatatypeProperty))
        g.add((prop_b, RDFS.label, Literal("performance rating index", datatype=XSD.string)))
        g.add((prop_b, RDFS.comment, Literal("Numerical performance indicator.", datatype=XSD.string)))
        g.add((prop_b, RDFS.range, XSD.integer))

        idx = OntologyIndex(g, use_sentence_transformers=False)
        resolver = PredicateResolver(idx, enable_llm=False)

        # Both have same range (xsd:integer) and close token subset scores for query 'performance rating'
        res = resolver.resolve(
            column_name="performance rating",
            column_role="Numeric property",
            sample_values=[15, 25, 45],
        )

        self.assertIsNotNone(res)
        self.assertEqual(res.method, "Arbiter-Reranked")
        self.assertTrue(res.review_flag)
        self.assertGreaterEqual(res.confidence, 0.65)

    # -------------------------------------------------------------------------
    # Test 15: Value Distribution & SHACL Bounds Pruning
    # -------------------------------------------------------------------------
    def test_15_value_distribution_bounds_pruning(self):
        """Verify candidates whose declared bounds are exceeded by sample_values are pruned,
        allowing the correct bounds-compliant candidate to win via AxiomFilter-Unique.
        """
        g = Graph()
        # Candidate 1: level with bounds [0, 80]
        prop_lvl = TEST_NS.itemLevel
        g.add((prop_lvl, RDF.type, OWL.DatatypeProperty))
        g.add((prop_lvl, RDFS.label, Literal("rating tier level", datatype=XSD.string)))
        g.add((prop_lvl, RDFS.comment, Literal("Level requirement (0-80).", datatype=XSD.string)))
        g.add((prop_lvl, RDFS.range, XSD.integer))

        # Candidate 2: discipline with bounds [0, 500]
        prop_disc = TEST_NS.craftingRating
        g.add((prop_disc, RDF.type, OWL.DatatypeProperty))
        g.add((prop_disc, RDFS.label, Literal("rating craft discipline", datatype=XSD.string)))
        g.add((prop_disc, RDFS.comment, Literal("Discipline skill rating (0 to 500).", datatype=XSD.string)))
        g.add((prop_disc, RDFS.range, XSD.integer))

        idx = OntologyIndex(g, use_sentence_transformers=False)
        resolver = PredicateResolver(idx, enable_llm=False)

        # Sample values max is 450 -> exceeds 80! prop_lvl MUST be pruned!
        res = resolver.resolve(
            column_name="rating",
            column_role="Numeric property",
            sample_values=[100, 250, 450],
        )

        self.assertIsNotNone(res)
        self.assertEqual(res.uri, str(prop_disc))
        # Since prop_lvl was pruned due to bounds violation, exactly 1 candidate survived!
        self.assertEqual(res.method, "AxiomFilter-Unique")
        self.assertEqual(res.confidence, 0.66)
        self.assertFalse(res.review_flag)

    # -------------------------------------------------------------------------
    # Test 16: Full-Context Arbiter Verification
    # -------------------------------------------------------------------------
    def test_16_full_context_llm_arbiter(self):
        """Verify LLM prompt receives full semantic context: URI, label, synonyms, domain, range, bounds, comment, stats."""
        captured_prompts = []

        def mock_full_context_llm(prompt: str) -> str:
            captured_prompts.append(prompt)
            return "1 HIGH"

        g = Graph()
        SHACL = Namespace("http://www.w3.org/ns/shacl#")
        prop_cand1 = TEST_NS.metricA
        g.add((prop_cand1, RDF.type, OWL.DatatypeProperty))
        g.add((prop_cand1, RDFS.label, Literal("sensor metric A", datatype=XSD.string)))
        g.add((prop_cand1, SKOS.altLabel, Literal("sensor index alpha", datatype=XSD.string)))
        g.add((prop_cand1, RDFS.comment, Literal("Fine-grained sensor alpha metric reading.", datatype=XSD.string)))
        g.add((prop_cand1, RDFS.range, XSD.double))
        g.add((prop_cand1, SHACL.minInclusive, Literal(0.0, datatype=XSD.double)))
        g.add((prop_cand1, SHACL.maxInclusive, Literal(100.0, datatype=XSD.double)))

        prop_cand2 = TEST_NS.metricB
        g.add((prop_cand2, RDF.type, OWL.DatatypeProperty))
        g.add((prop_cand2, RDFS.label, Literal("sensor metric B", datatype=XSD.string)))
        g.add((prop_cand2, SKOS.altLabel, Literal("sensor index beta", datatype=XSD.string)))
        g.add((prop_cand2, RDFS.comment, Literal("Secondary sensor beta metric reading.", datatype=XSD.string)))
        g.add((prop_cand2, RDFS.range, XSD.double))
        g.add((prop_cand2, SHACL.minInclusive, Literal(0.0, datatype=XSD.double)))
        g.add((prop_cand2, SHACL.maxInclusive, Literal(100.0, datatype=XSD.double)))

        idx = OntologyIndex(g, use_sentence_transformers=False)
        resolver_llm = PredicateResolver(idx, enable_llm=True, llm_client=mock_full_context_llm)

        res = resolver_llm.resolve(
            column_name="sensor metric",
            column_role="Numeric property",
            sample_values=[12.5, 45.0, 78.2],
        )

        self.assertIsNotNone(res)
        self.assertEqual(res.method, "LLM-Reranked")
        self.assertEqual(res.confidence, 0.75)
        self.assertEqual(len(captured_prompts), 1)

        p = captured_prompts[0]
        # Verify stats
        self.assertIn("Min: 12.5", p)
        self.assertIn("Max: 78.2", p)
        self.assertIn("Role: Numeric property", p)
        # Verify candidate full context
        self.assertIn("URI: http://example.org/test#metricA", p)
        self.assertIn("Synonyms: sensor index alpha", p)
        self.assertIn("Bounds: [0.0, 100.0]", p)
        self.assertIn("Fine-grained sensor alpha metric reading", p)


if __name__ == "__main__":
    unittest.main()
