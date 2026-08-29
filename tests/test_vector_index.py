import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import unittest
import numpy as np

from gw2_ume.retrieval.vector_index import (
    DeterministicDenseEmbedder,
    IndexedClass,
    IndexedEntity,
    IndexedProperty,
    RetrievalResult,
    VectorIndex,
    char_ngram_similarity,
    char_ngrams,
    cosine_similarity,
    get_default_vector_index,
    jaro_similarity,
    jaro_winkler_similarity,
    levenshtein_distance,
    levenshtein_similarity,
    lexical_similarity,
    token_jaccard_similarity,
    tokenize,
)
from gw2_ume.mesh.annotator import (
    annotate_table,
    match_cell_entity,
    normalize_text,
    parse_table_content,
)
from gw2_ume.matching.cea import CellEntityAnnotator
from gw2_ume.matching.cta import ColumnTypeAnnotator
from gw2_ume.matching.cpa import ColumnPropertyAnnotator
from gw2_ume.matching.models import TableGrid


class TestLexicalSimilarityMetrics(unittest.TestCase):
    """Test suite for string tokenization, edit distances, n-grams, and Jaro-Winkler."""

    def test_tokenize(self):
        text = "Nevermore: The Raven Spirit (Tier 3) -- 250x Spiritwood!"
        tokens = tokenize(text)
        self.assertEqual(tokens, ["nevermore", "the", "raven", "spirit", "tier", "3", "250x", "spiritwood"])
        self.assertEqual(tokenize(""), [])

    def test_char_ngrams(self):
        ngs = char_ngrams("Bolt", n=3)
        self.assertIn("^bo", ngs)
        self.assertIn("olt", ngs)
        self.assertIn("lt$", ngs)

        short_ngs = char_ngrams("a", n=3)
        self.assertEqual(short_ngs, {"^a$"})

    def test_levenshtein_distance_and_similarity(self):
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)
        self.assertEqual(levenshtein_distance("raven", "raven"), 0)
        self.assertEqual(levenshtein_distance("", "test"), 4)
        self.assertEqual(levenshtein_distance("test", ""), 4)

        self.assertAlmostEqual(levenshtein_similarity("raven", "raven"), 1.0)
        self.assertAlmostEqual(levenshtein_similarity("", ""), 1.0)
        self.assertGreater(levenshtein_similarity("nevermore", "n3vermore"), 0.8)
        self.assertLess(levenshtein_similarity("artificer", "weaponsmith"), 0.3)

    def test_jaro_and_jaro_winkler_similarity(self):
        # Standard test case
        sim_exact = jaro_similarity("martha", "martha")
        self.assertAlmostEqual(sim_exact, 1.0)

        jw_exact = jaro_winkler_similarity("martha", "martha")
        self.assertAlmostEqual(jw_exact, 1.0)

        # Empty strings
        self.assertEqual(jaro_similarity("", ""), 1.0)
        self.assertEqual(jaro_similarity("a", ""), 0.0)

        # Transposition test
        jw_trans = jaro_winkler_similarity("martha", "marhta")
        self.assertGreater(jw_trans, 0.94)

        # Typo prefix preservation test
        jw_prefix = jaro_winkler_similarity("spiritwood", "spiritwod")
        self.assertGreater(jw_prefix, 0.95)

        # Disjoint strings
        jw_disjoint = jaro_winkler_similarity("artificer", "necromancer")
        self.assertLess(jw_disjoint, 0.6)

    def test_token_jaccard_similarity(self):
        self.assertAlmostEqual(token_jaccard_similarity("Spiritwood Plank", "Spiritwood Plank"), 1.0)
        self.assertAlmostEqual(token_jaccard_similarity("Spiritwood Plank", "Plank Spiritwood"), 1.0)
        self.assertAlmostEqual(token_jaccard_similarity("Spiritwood Plank", "Plank of Spiritwood"), 2 / 3)
        self.assertAlmostEqual(token_jaccard_similarity("Spiritwood Plank", "Deldrimor Steel Ingot"), 0.0)
        self.assertEqual(token_jaccard_similarity("", ""), 1.0)

    def test_char_ngram_similarity(self):
        self.assertAlmostEqual(char_ngram_similarity("Nevermore", "Nevermore"), 1.0)
        self.assertGreater(char_ngram_similarity("Nevermore", "Nevermor"), 0.65)
        self.assertLess(char_ngram_similarity("Nevermore", "Kudzu"), 0.1)

    def test_cosine_similarity(self):
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        v_zero = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0)
        self.assertAlmostEqual(cosine_similarity(v1, v3), 0.0)
        self.assertEqual(cosine_similarity(v1, v_zero), 0.0)
        self.assertEqual(cosine_similarity(None, v1), 0.0)

    def test_lexical_similarity_hybrid(self):
        # Exact match
        self.assertAlmostEqual(lexical_similarity("Nevermore", "Nevermore"), 1.0)

        # Alias match
        self.assertAlmostEqual(
            lexical_similarity("raven staff", "Nevermore", aliases=["raven staff", "n3vermore"]),
            1.0,
        )

        # Fuzzy OCR noise match
        score = lexical_similarity("n3vermore", "Nevermore")
        self.assertGreater(score, 0.80)

        # Non-matching
        score_diff = lexical_similarity("Grandmaster Craftsman Hobbs", "The Living Ravens")
        self.assertLess(score_diff, 0.40)


class TestDeterministicDenseEmbedder(unittest.TestCase):
    """Test deterministic dense hash embeddings."""

    def setUp(self):
        self.embedder = DeterministicDenseEmbedder(dim=128)

    def test_embedding_shape_and_norm(self):
        vec = self.embedder.embed("Ravenswood Branch")
        self.assertEqual(vec.shape, (128,))
        self.assertEqual(vec.dtype, np.float32)
        self.assertAlmostEqual(np.linalg.norm(vec), 1.0, places=5)

    def test_empty_string(self):
        vec = self.embedder.embed("")
        self.assertEqual(vec.shape, (128,))
        self.assertEqual(np.linalg.norm(vec), 0.0)

    def test_determinism(self):
        v1 = self.embedder.embed("Elonian Leather Square")
        v2 = self.embedder.embed("Elonian Leather Square")
        np.testing.assert_array_almost_equal(v1, v2)

    def test_semantic_proximity(self):
        v_orig = self.embedder.embed("Spiritwood Plank")
        v_typo = self.embedder.embed("Spiritwod Plank")
        v_unrelated = self.embedder.embed("Grandmaster Hobbs in Lion's Arch")

        sim_typo = cosine_similarity(v_orig, v_typo)
        sim_unrelated = cosine_similarity(v_orig, v_unrelated)

        self.assertGreater(sim_typo, 0.75)
        self.assertLess(sim_unrelated, sim_typo)

    def test_batch_encode(self):
        texts = ["Bolt", "The Bifrost", "Nevermore"]
        arr = self.embedder.encode(texts)
        self.assertEqual(arr.shape, (3, 128))
        norms = np.linalg.norm(arr, axis=1)
        for n in norms:
            self.assertAlmostEqual(n, 1.0, places=5)

        single = self.embedder.encode_single("Bolt")
        np.testing.assert_array_almost_equal(arr[0], single)


class TestVectorIndex(unittest.TestCase):
    """Test multimodal VectorIndex indexing, searching, and catalog population."""

    def setUp(self):
        self.index = VectorIndex(embedding_dim=128)

    def test_add_and_search_entities(self):
        self.index.add_entity(
            iri="https://gw2ume.org/resource/ravenswood_branch",
            label="Ravenswood Branch",
            types=["PrecursorWeapon"],
            description="Tier 1 precursor staff for Nevermore",
            aliases=["branch", "tier 1 precursor"],
        )
        self.index.add_entity(
            iri="https://gw2ume.org/resource/spiritwood_plank",
            label="Spiritwood Plank",
            types=["CraftingMaterial"],
            description="Ascended wood material",
            aliases=["spiritwood"],
        )

        # Exact match query
        results = self.index.search_entities("Ravenswood Branch", top_k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].label, "Ravenswood Branch")
        self.assertAlmostEqual(results[0].score, 0.95, delta=0.06)

        # Alias query
        results_alias = self.index.search_entities("spiritwood", top_k=2)
        self.assertEqual(results_alias[0].label, "Spiritwood Plank")
        self.assertGreater(results_alias[0].score, 0.90)

        # Type filter
        filtered = self.index.search_entities("branch", type_filter="CraftingMaterial")
        self.assertTrue(all("CraftingMaterial" in r.types for r in filtered))

        filtered_ok = self.index.search_entities("branch", type_filter="PrecursorWeapon")
        self.assertEqual(len(filtered_ok), 1)
        self.assertEqual(filtered_ok[0].label, "Ravenswood Branch")

    def test_search_classes_and_properties(self):
        self.index.add_class(
            iri="https://priory.gw2/def/CraftingDiscipline",
            label="Crafting Discipline",
            description="Crafting trade profession",
            aliases=["discipline", "craft", "profession"],
        )
        self.index.add_property(
            iri="https://priory.gw2/def/requiresIngredient",
            label="requiresIngredient",
            description="Item requires component ingredient",
            aliases=["requires ingredient", "material", "component"],
        )

        class_res = self.index.search_classes("discipline", top_k=1)
        self.assertEqual(len(class_res), 1)
        self.assertEqual(class_res[0].iri, "https://priory.gw2/def/CraftingDiscipline")
        self.assertGreater(class_res[0].score, 0.85)

        prop_res = self.index.search_properties("requires ingredient", top_k=1)
        self.assertEqual(len(prop_res), 1)
        self.assertEqual(prop_res[0].iri, "https://priory.gw2/def/requiresIngredient")
        self.assertGreater(prop_res[0].score, 0.85)

    def test_populate_defaults(self):
        default_index = get_default_vector_index()
        self.assertGreater(len(default_index.entities), 20)
        self.assertGreater(len(default_index.classes), 10)
        self.assertGreater(len(default_index.properties), 5)

        # Search known entities from ENTITY_CATALOG
        res_nevermore = default_index.search_entities("Nevermore", top_k=1)
        self.assertEqual(res_nevermore[0].label, "Nevermore")

        res_hobbs = default_index.search_entities("Hobbs", top_k=1)
        self.assertIn("Hobbs", res_hobbs[0].label)


class TestTableAnnotationWithVectorIndex(unittest.TestCase):
    """Test table cell and column annotation backed by VectorIndex."""

    def test_match_cell_entity_with_vector_index(self):
        # Exact match
        match = match_cell_entity("Ravenswood Branch", "Precursor")
        self.assertIsNotNone(match)
        uri, label, type_label, conf = match
        self.assertEqual(label, "Ravenswood Branch")
        self.assertEqual(type_label, "PrecursorWeapon")
        self.assertGreaterEqual(conf, 0.90)

        # Fuzzy / alias match with context
        match_fuzzy = match_cell_entity("Artificer", "Crafting Discipline")
        self.assertIsNotNone(match_fuzzy)
        self.assertEqual(match_fuzzy[1], "Artificer")
        self.assertEqual(match_fuzzy[2], "CraftingDiscipline")

        # Vendor matching
        match_vendor = match_cell_entity("Hobbs", "NPC Vendor")
        self.assertIsNotNone(match_vendor)
        self.assertIn("Hobbs", match_vendor[1])
        self.assertEqual(match_vendor[2], "NPCVendor")

        # Numbers in quantity column should return None
        self.assertIsNone(match_cell_entity("250", "Quantity"))
        self.assertIsNone(match_cell_entity("450", "Min Rating"))

    def test_annotate_table_pipeline(self):
        headers = ["Step", "Item", "Discipline", "Rating", "Vendor", "Zone"]
        rows = [
            ["Tier 1", "Ravenswood Branch", "Artificer", "450", "Grandmaster Hobbs", "Lion's Arch"],
            ["Tier 2", "Ravenswood Staff", "Artificer", "450", "Grandmaster Hobbs", "Lion's Arch"],
        ]

        cta, cea, cpa = annotate_table(headers, rows)

        # CTA checks
        self.assertEqual(len(cta), 6)
        cta_types = {c.col_idx: c.type_label for c in cta}
        self.assertIn(cta_types[0], ["CollectionStep", "CollectionTier"])
        self.assertIn(cta_types[1], ["PrecursorWeapon", "ComponentItem", "Item"])
        self.assertEqual(cta_types[2], "CraftingDiscipline")
        self.assertEqual(cta_types[3], "DisciplineRating")
        self.assertEqual(cta_types[4], "NPCVendor")
        self.assertEqual(cta_types[5], "Zone")
        self.assertIn(cta_types[1], ["PrecursorWeapon", "ComponentItem", "Item"])
        self.assertEqual(cta_types[2], "CraftingDiscipline")
        self.assertEqual(cta_types[3], "DisciplineRating")
        self.assertEqual(cta_types[4], "NPCVendor")
        self.assertEqual(cta_types[5], "Zone")

        # CEA checks
        self.assertGreater(len(cea), 6)
        cea_labels = [c.label for c in cea]
        self.assertIn("Ravenswood Branch", cea_labels)
        self.assertIn("Artificer", cea_labels)

        # CPA checks
        self.assertGreater(len(cpa), 2)
        cpa_props = [c.property_label for c in cpa]
        self.assertIn("craftedByDiscipline", cpa_props)
        self.assertIn("locatedInZone", cpa_props)


class TestMatchingComponentsWithVectorIndex(unittest.TestCase):
    """Test CEA, CTA, CPA classes dynamic vector index integration."""

    def test_cea_default_index(self):
        cea = CellEntityAnnotator()
        res = cea.annotate_cell("Nevermore", row_idx=0, col_idx=0)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.label, "Nevermore")

    def test_cta_default_index(self):
        cea = CellEntityAnnotator()
        cta = ColumnTypeAnnotator()

        grid = TableGrid(
            headers=["Crafting Discipline"],
            rows=[["Artificer"], ["Huntsman"], ["Weaponsmith"]],
        )
        cea_map = cea.annotate_table(grid)
        cta_map = cta.annotate_table(grid, cea_map)

        self.assertIn(0, cta_map)
        self.assertTrue(len(cta_map[0]) > 0)


if __name__ == "__main__":
    unittest.main()
