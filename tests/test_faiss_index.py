import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


import numpy as np
import rdflib
from rdflib import OWL, RDF, RDFS, Namespace, URIRef

from gw2_ume.indexing import (
    BaseEmbedder,
    BaseVectorIndex,
    FaissVectorIndex,
    LightweightFallbackEmbedder,
    NumpyVectorIndex,
    OntologyIndexBuilder,
    ScoredMatch,
    TextEmbedder,
    VectorIndex,
    detect_optimal_device,
    is_faiss_available,
)
from gw2_ume.ontology.loader import OntologyLoader


class TestDenseEmbedder(unittest.TestCase):
    """Tests for LightweightFallbackEmbedder and TextEmbedder."""

    def test_fallback_embedder_dimension_and_norms(self):
        dim = 128
        embedder = LightweightFallbackEmbedder(dimension=dim)
        self.assertEqual(embedder.dimension, dim)

        text = "Greatsword Weapon Master"
        vec = embedder.encode_single(text)
        self.assertEqual(vec.shape, (dim,))
        self.assertEqual(vec.dtype, np.float32)
        norm = np.linalg.norm(vec)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_fallback_embedder_batch(self):
        dim = 256
        embedder = LightweightFallbackEmbedder(dimension=dim)
        texts = ["Warrior", "Guardian", "Necromancer", "Mesmer"]
        vectors = embedder.encode(texts, batch_size=2)
        self.assertEqual(vectors.shape, (4, dim))
        self.assertEqual(vectors.dtype, np.float32)
        norms = np.linalg.norm(vectors, axis=1)
        for n in norms:
            self.assertAlmostEqual(n, 1.0, places=5)

    def test_fallback_embedder_empty_string(self):
        embedder = LightweightFallbackEmbedder(dimension=64)
        vec = embedder.encode_single("")
        self.assertEqual(vec.shape, (64,))
        # Empty batch
        empty_batch = embedder.encode([])
        self.assertEqual(empty_batch.shape, (0, 64))

    def test_fallback_embedder_deterministic_similarity(self):
        embedder = LightweightFallbackEmbedder(dimension=384)
        v_warrior1 = embedder.encode_single("Warrior Greatsword")
        v_warrior2 = embedder.encode_single("Warrior Greatsword")
        v_ranger = embedder.encode_single("Ranger Longbow Pet")

        # Identical text produces exact match
        sim_identical = float(np.dot(v_warrior1, v_warrior2))
        self.assertAlmostEqual(sim_identical, 1.0, places=5)

        # Different text produces lower similarity
        sim_diff = float(np.dot(v_warrior1, v_ranger))
        self.assertLess(sim_diff, 0.9)

    def test_text_embedder_fallback_mode(self):
        embedder = TextEmbedder(use_fallback=True, fallback_dimension=200)
        self.assertTrue(embedder.is_fallback)
        self.assertEqual(embedder.dimension, 200)
        self.assertEqual(embedder.device, "cpu")

        vec = embedder.encode_single("Axe of the Dragon")
        self.assertEqual(vec.shape, (200,))
        self.assertAlmostEqual(np.linalg.norm(vec), 1.0, places=5)

    def test_text_embedder_device_detection(self):
        device = detect_optimal_device()
        self.assertIn(device, ["mps", "cuda", "cpu"])

    def test_text_embedder_sentence_transformers(self):
        # Test default sentence transformer (cached all-MiniLM-L6-v2)
        embedder = TextEmbedder(model_name_or_path="all-MiniLM-L6-v2")
        self.assertEqual(embedder.dimension, 384)
        vec = embedder.encode_single("Exotic Armor")
        self.assertEqual(vec.shape, (384,))
        self.assertAlmostEqual(np.linalg.norm(vec), 1.0, places=4)


class TestNumpyVectorIndex(unittest.TestCase):
    """Tests for pure-NumPy vectorized inner product and cosine ranking."""

    def setUp(self):
        self.dim = 4
        self.index = NumpyVectorIndex(dimension=self.dim)

        # Pre-normalized orthogonal / semi-orthogonal vectors
        self.v_item = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.v_weapon = np.array([0.8, 0.6, 0.0, 0.0], dtype=np.float32)
        self.v_recipe = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        self.v_req_mat = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

        self.payloads = [
            {
                "id": "Item",
                "iri": "https://schema.gw2ume.org/core#Item",
                "label": "Item",
                "entity_type": "Class",
                "description": "Base Item class",
                "synonyms": ["Thing", "Object"],
            },
            {
                "id": "Weapon",
                "iri": "https://schema.gw2ume.org/core#Weapon",
                "label": "Weapon",
                "entity_type": "Class",
                "description": "Equippable weapon",
                "synonyms": ["Armament"],
            },
            {
                "id": "CraftingRecipe",
                "iri": "https://schema.gw2ume.org/core#CraftingRecipe",
                "label": "Crafting Recipe",
                "entity_type": "Class",
                "description": "Formula for crafting items",
                "synonyms": ["Recipe"],
            },
            {
                "id": "requiresMaterial",
                "iri": "https://schema.gw2ume.org/core#requiresMaterial",
                "label": "requiresMaterial",
                "entity_type": "ObjectProperty",
                "description": "Crafting ingredient link",
                "domain": ["CraftingRecipe"],
                "range": ["CraftingMaterial"],
            },
        ]

        vectors = np.vstack([self.v_item, self.v_weapon, self.v_recipe, self.v_req_mat])
        self.index.add(vectors, self.payloads)

    def test_length_and_dimension(self):
        self.assertEqual(len(self.index), 4)
        self.assertEqual(self.index.dimension, 4)

    def test_search_top_k_exact_cosine_ranking(self):
        # Query closest to Item ([1, 0, 0, 0])
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        matches = self.index.search(q, top_k=2)

        self.assertEqual(len(matches), 2)
        # Top 1 must be Item (score = 1.0)
        self.assertEqual(matches[0].id, "Item")
        self.assertAlmostEqual(matches[0].score, 1.0, places=5)
        self.assertEqual(matches[0].entity_type, "Class")

        # Top 2 must be Weapon (score = 0.8)
        self.assertEqual(matches[1].id, "Weapon")
        self.assertAlmostEqual(matches[1].score, 0.8, places=5)
        self.assertEqual(matches[1].entity_type, "Class")

    def test_search_with_filter_type(self):
        # Query with direction [0, 0, 0, 1] (towards requiresMaterial)
        q = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

        # Filter by ObjectProperty
        prop_matches = self.index.search(q, top_k=5, filter_type="ObjectProperty")
        self.assertEqual(len(prop_matches), 1)
        self.assertEqual(prop_matches[0].id, "requiresMaterial")
        self.assertAlmostEqual(prop_matches[0].score, 1.0, places=5)

        # Filter by Class (case-insensitive)
        class_matches = self.index.search(q, top_k=5, filter_type="class")
        self.assertEqual(len(class_matches), 3)
        for m in class_matches:
            self.assertEqual(m.entity_type, "Class")

        # Filter with non-matching type
        none_matches = self.index.search(q, top_k=5, filter_type="NonExistentType")
        self.assertEqual(len(none_matches), 0)

    def test_search_with_multiple_filter_types(self):
        q = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32)
        matches = self.index.search(q, top_k=10, filter_type=["Class", "ObjectProperty"])
        self.assertEqual(len(matches), 4)

    def test_search_edge_cases(self):
        empty_index = NumpyVectorIndex(dimension=4)
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.assertEqual(empty_index.search(q, top_k=5), [])
        self.assertEqual(self.index.search(q, top_k=0), [])
        self.assertEqual(self.index.search(q, top_k=-1), [])

    def test_scored_match_to_dict(self):
        sm = ScoredMatch(
            id="Item",
            iri="https://schema.gw2ume.org/core#Item",
            label="Item",
            score=0.99,
            metadata={"synonyms": ["Thing"]},
            entity_type="Class",
        )
        d = sm.to_dict()
        self.assertEqual(d["id"], "Item")
        self.assertEqual(d["score"], 0.99)
        self.assertEqual(d["entity_type"], "Class")
        self.assertEqual(d["metadata"]["synonyms"], ["Thing"])

    def test_dimension_mismatch_error(self):
        bad_vec = np.array([[1.0, 2.0]], dtype=np.float32)
        with self.assertRaises(ValueError):
            self.index.add(bad_vec, [{"id": "bad"}])

        with self.assertRaises(ValueError):
            self.index.search(bad_vec[0], top_k=5)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_index.npz"
            self.index.save(save_path)
            self.assertTrue(save_path.exists())

            loaded = NumpyVectorIndex.load(save_path)
            self.assertEqual(len(loaded), 4)
            self.assertEqual(loaded.dimension, 4)

            q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
            matches = loaded.search(q, top_k=2)
            self.assertEqual(len(matches), 2)
            self.assertEqual(matches[0].id, "Item")
            self.assertAlmostEqual(matches[0].score, 1.0, places=5)


class TestVectorIndexWrapper(unittest.TestCase):
    """Tests for VectorIndex wrapper and factory."""

    def test_create_and_load_vector_index(self):
        index = VectorIndex(dimension=16)
        self.assertEqual(index.dimension, 16)
        self.assertFalse(index.is_faiss if not is_faiss_available() else False)

        vecs = np.random.randn(5, 16).astype(np.float32)
        payloads = [
            {
                "id": f"node_{i}",
                "iri": f"http://ex.org/{i}",
                "label": f"Node {i}",
                "entity_type": "Class",
            }
            for i in range(5)
        ]
        index.add(vecs, payloads)
        self.assertEqual(len(index), 5)

        q = vecs[0]
        matches = index.search(q, top_k=3)
        self.assertEqual(len(matches), 3)
        self.assertEqual(matches[0].id, "node_0")
        self.assertAlmostEqual(matches[0].score, 1.0, places=4)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "wrapper_index.npz"
            index.save(file_path)

            loaded = VectorIndex.load(file_path)
            self.assertEqual(len(loaded), 5)
            self.assertEqual(loaded.dimension, 16)

    def test_faiss_vector_index_raises_when_unavailable(self):
        if not is_faiss_available():
            with self.assertRaises(ImportError):
                FaissVectorIndex(dimension=16)


class TestOntologyIndexBuilder(unittest.TestCase):
    """Tests for OntologyIndexBuilder concept extraction, embedding, search, and persistence."""

    @classmethod
    def setUpClass(cls):
        # Create a small in-memory RDF Graph representing GW2 concepts
        cls.graph = rdflib.Graph()
        GW2 = Namespace("https://schema.gw2ume.org/core#")
        cls.graph.bind("gw2", GW2)
        cls.graph.bind("owl", OWL)
        cls.graph.bind("rdfs", RDFS)

        # Classes
        cls.graph.add((GW2.Item, RDF.type, OWL.Class))
        cls.graph.add((GW2.Item, RDFS.label, rdflib.Literal("Item", lang="en")))
        cls.graph.add((GW2.Item, RDFS.comment, rdflib.Literal("A distinct item in GW2.", lang="en")))

        cls.graph.add((GW2.Weapon, RDF.type, OWL.Class))
        cls.graph.add((GW2.Weapon, RDFS.subClassOf, GW2.Item))
        cls.graph.add((GW2.Weapon, RDFS.label, rdflib.Literal("Weapon", lang="en")))
        cls.graph.add((GW2.Weapon, RDFS.comment, rdflib.Literal("Equippable offensive weapon.", lang="en")))

        cls.graph.add((GW2.LegendaryWeapon, RDF.type, OWL.Class))
        cls.graph.add((GW2.LegendaryWeapon, RDFS.subClassOf, GW2.Weapon))
        cls.graph.add((GW2.LegendaryWeapon, RDFS.label, rdflib.Literal("Legendary Weapon", lang="en")))
        cls.graph.add((GW2.LegendaryWeapon, RDFS.comment, rdflib.Literal("Top tier weapon with stat swapping.", lang="en")))

        # Properties
        cls.graph.add((GW2.requiresMaterial, RDF.type, OWL.ObjectProperty))
        cls.graph.add((GW2.requiresMaterial, RDFS.label, rdflib.Literal("requiresMaterial", lang="en")))
        cls.graph.add((GW2.requiresMaterial, RDFS.comment, rdflib.Literal("Crafting material requirement.", lang="en")))
        cls.graph.add((GW2.requiresMaterial, RDFS.domain, GW2.Item))
        cls.graph.add((GW2.requiresMaterial, RDFS.range, GW2.Item))

        cls.graph.add((GW2.vendorCost, RDF.type, OWL.DatatypeProperty))
        cls.graph.add((GW2.vendorCost, RDFS.label, rdflib.Literal("vendorCost", lang="en")))
        cls.graph.add((GW2.vendorCost, RDFS.comment, rdflib.Literal("Cost in coin charged by vendor.", lang="en")))
        cls.graph.add((GW2.vendorCost, RDFS.domain, GW2.Item))

        # Individuals
        cls.graph.add((GW2.Artificer, RDF.type, OWL.NamedIndividual))
        cls.graph.add((GW2.Artificer, RDF.type, GW2.Item))
        cls.graph.add((GW2.Artificer, RDFS.label, rdflib.Literal("Artificer", lang="en")))
        cls.graph.add((GW2.Artificer, RDFS.comment, rdflib.Literal("Crafting discipline that crafts magical staves and scepters.", lang="en")))

        # Use fallback embedder for deterministic speed in test
        cls.embedder = LightweightFallbackEmbedder(dimension=128)
        cls.builder = OntologyIndexBuilder(
            graph=cls.graph,
            embedder=cls.embedder,
            auto_build=True,
        )

    def test_builder_indexed_count(self):
        # 3 classes + 1 ObjectProperty + 1 DatatypeProperty + 1 Individual = 6
        self.assertGreaterEqual(len(self.builder.index), 6)

    def test_search_concept(self):
        results = self.builder.search_concept("Legendary Weapon", top_k=3)
        self.assertGreater(len(results), 0)
        labels = [r.label for r in results]
        self.assertIn("Legendary Weapon", labels)
        top_match = results[0]
        self.assertIsInstance(top_match, ScoredMatch)
        self.assertGreater(top_match.score, 0.0)

    def test_search_class_filter(self):
        results = self.builder.search_class("Weapon", top_k=5)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.entity_type, "Class")

    def test_search_relation(self):
        results = self.builder.search_relation("requires material", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].id, "requiresMaterial")
        self.assertIn(results[0].entity_type, ["ObjectProperty", "DatatypeProperty", "Property"])

    def test_search_individual(self):
        results = self.builder.search_individual("Artificer crafting staves", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].id, "Artificer")
        self.assertEqual(results[0].entity_type, "Individual")

    def test_search_object_and_datatype_property(self):
        obj_matches = self.builder.search_object_property("requires material", top_k=3)
        self.assertGreater(len(obj_matches), 0)
        self.assertEqual(obj_matches[0].entity_type, "ObjectProperty")

        data_matches = self.builder.search_datatype_property("vendor cost", top_k=3)
        self.assertGreater(len(data_matches), 0)
        self.assertEqual(data_matches[0].entity_type, "DatatypeProperty")

    def test_add_custom_entity(self):
        self.builder.add_custom_entity(
            iri="https://schema.gw2ume.org/core#CustomSword",
            label="Custom Sword",
            entity_type="Individual",
            description="A unique customized legendary greatsword.",
            synonyms=["Custom Blade", "Greatsword"],
        )
        results = self.builder.search_individual("Custom Sword blade", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].label, "Custom Sword")

    def test_builder_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "ontology_vector_index.npz"
            self.builder.save(save_path)
            self.assertTrue(save_path.exists())

            loaded_builder = OntologyIndexBuilder.load(save_path, embedder=self.embedder)
            self.assertEqual(len(loaded_builder.index), len(self.builder.index))

            results = loaded_builder.search_concept("Legendary Weapon", top_k=3)
            self.assertGreater(len(results), 0)
            self.assertEqual(results[0].label, "Legendary Weapon")


class TestOntologyCoreFullBuild(unittest.TestCase):
    """Integration test loading default core + legendary ontologies."""

    def test_core_ontology_indexing(self):
        loader = OntologyLoader(auto_load_defaults=True)
        self.assertGreater(len(loader.get_graph()), 0)

        embedder = LightweightFallbackEmbedder(dimension=256)
        builder = OntologyIndexBuilder(loader=loader, embedder=embedder, auto_build=True)
        self.assertGreater(len(builder.index), 50)

        # Search for key GW2 concepts
        results = builder.search_concept("Precursor Weapon", top_k=5)
        self.assertGreater(len(results), 0)

        # Search for relationships
        rel_results = builder.search_relation("requires material", top_k=5)
        self.assertGreater(len(rel_results), 0)


if __name__ == "__main__":
    unittest.main()
