"""Unit tests for Dynamic Modality Parser and Dynamic Table Synthesizer."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gw2_ume.text.modality_parser import (
    ModalityParser,
    ModalityType,
    SemanticSlot,
    DynamicSemanticFrame,
    DiscourseClause,
    ModalityParseResult,
)
from gw2_ume.text.table_synthesizer import (
    TableSynthesizer,
    SyntheticTableGrid,
)
from gw2_ume.text.extractor import TextEntityRelationExtractor
from gw2_ume.pipeline.triangulator import CrossModalTriangulator


class TestModalityParserAndTableSynthesizer(unittest.TestCase):
    """Tests discourse segmentation, 4-way modal logic classification, fluff pruning, and table synthesis."""

    def setUp(self):
        self.parser = ModalityParser()
        self.synthesizer = TableSynthesizer()
        self.extractor = TextEntityRelationExtractor()

    def test_4way_modal_logic_classification(self):
        """Verifies accurate 4-way modal logic classification."""
        # 1. DEONTIC_RULE (□)
        deontic_sample = "You must craft Ravenswood Branch using 3 Spiritwood Planks."
        mod, conf, cues = self.parser.classify_modality(deontic_sample)
        self.assertEqual(mod, ModalityType.DEONTIC_RULE)
        self.assertGreater(conf, 0.8)

        # 2. EPISTEMIC_ESTIMATE (◇)
        epistemic_sample = "To fully gear a character, it will cost around 250-300 gold."
        mod, conf, cues = self.parser.classify_modality(epistemic_sample)
        self.assertEqual(mod, ModalityType.EPISTEMIC_ESTIMATE)
        self.assertGreater(conf, 0.8)

        # 3. HYPOTHETICAL (⇒)
        hypo_sample = "If you choose to craft heavy armor, you need level 500 Armorsmith."
        mod, conf, cues = self.parser.classify_modality(hypo_sample)
        self.assertEqual(mod, ModalityType.HYPOTHETICAL)
        self.assertGreater(conf, 0.8)

        # 4. BOULETIC_FLUFF (⚡)
        fluff_sample = "In my opinion, I realized that this is a super long post and I prefer to skip it."
        mod, conf, cues = self.parser.classify_modality(fluff_sample)
        self.assertEqual(mod, ModalityType.BOULETIC_FLUFF)
        self.assertGreater(conf, 0.8)

    def test_bouletic_fluff_filtering(self):
        """Verifies that subjective author commentary is filtered/pruned from active frames."""
        mixed_text = (
            "I was mulling over my first character and I realised this guide is long.\n"
            "You must talk to Grandmaster Craftsman Hobbs at Lion's Arch.\n"
            "In my experience, crafting is super fun and I love it.\n"
            "Crafting Tier 1 requires 3 Spiritwood Planks with Artificer 450."
        )
        res = self.parser.parse(mixed_text, filter_fluff=True)
        self.assertEqual(len(res.pruned_fluff_clauses), 2)
        self.assertEqual(len(res.active_frames), 2)

        # Active frames should only contain the invariant rules
        anchor_labels = [f.anchor_entity for f in res.active_frames]
        self.assertTrue(any("Hobbs" in (a or "") or "Branch" in (a or "") or "Spiritwood" in (a or "") for a in anchor_labels))

    def test_case_sensitive_short_token_matching(self):
        """Verifies case-sensitive matching for short/common tokens like 'hope' vs 'H.O.P.E.'."""
        # 1. Lowercase English verb 'hope' should NOT match H.O.P.E. legendary weapon
        verb_text = "I hope that you have enough crafting materials to finish your gear."
        res_verb = self.parser.parse(verb_text, filter_fluff=False)
        hope_entities_verb = [
            s.value for f in res_verb.all_clauses if f.frame
            for s in f.frame.slots if s.value in ("H.O.P.E.", "HOPE")
        ]
        self.assertEqual(len(hope_entities_verb), 0, "Common verb 'hope' must not trigger H.O.P.E. weapon entity.")

        # 2. Uppercase acronym 'H.O.P.E.' or 'HOPE' SHOULD match
        weapon_text = "You can craft H.O.P.E. by combining the prototype pistol with alchemical gifts."
        res_weapon = self.parser.parse(weapon_text, filter_fluff=True)
        hope_entities_weapon = [
            s.value for f in res_weapon.active_frames
            for s in f.slots if "H.O.P.E." in str(s.value) or "Hope" in str(s.value) or s.raw_text == "H.O.P.E."
        ]
        self.assertGreater(len(hope_entities_weapon), 0, "Exact acronym 'H.O.P.E.' must match weapon entity.")

    def test_dynamic_slot_extraction(self):
        """Verifies dynamic slot extraction: quantities, disciplines, ratings, vendors, and zones."""
        clause = "For Tier 1 (Ravenswood Branch), craft using 3 Spiritwood Planks with Artificer 450 and talk to Hobbs in Lion's Arch."
        slots, a_lbl, a_uri, a_type = self.parser.extract_semantic_slots(clause, ModalityType.DEONTIC_RULE)

        slot_names = [s.name for s in slots]
        self.assertIn("quantity", slot_names)
        self.assertIn("discipline", slot_names)
        self.assertIn("min_rating", slot_names)

        # Check values
        qty_slot = next(s for s in slots if s.name == "quantity")
        self.assertEqual(qty_slot.value, 3)

        disc_slot = next(s for s in slots if s.name == "discipline")
        self.assertEqual(disc_slot.value, "Artificer")

        rating_slot = next(s for s in slots if s.name == "min_rating")
        self.assertEqual(rating_slot.value, 450)

    def test_dynamic_table_synthesizer_zero_hardcoding(self):
        """Verifies dynamic column induction and 2D grid synthesis without static table schemas."""
        sample_guide = (
            "First off, talk to Grandmaster Craftsman Hobbs at Lion's Arch.\n"
            "For Tier 1 (Ravenswood Branch), you need 3 Spiritwood Planks and Artificer 450.\n"
            "Obtain the Essence of the Raven from Shaman Sigurlina in Wayfarer Foothills.\n"
            "Crafting Tier 2 (The Mnemonic Device) requires 10 Amalgamated Gemstones.\n"
            "This will cost around 250 gold."
        )

        parse_res = self.parser.parse(sample_guide, filter_fluff=True)
        grid = self.synthesizer.synthesize_grid(parse_res.active_frames, title="Nevermore Synthesis")

        self.assertIsInstance(grid, SyntheticTableGrid)
        self.assertGreater(len(grid.headers), 3)
        self.assertGreater(len(grid.rows), 3)

        # Ensure headers were induced dynamically (e.g. contain Quantity, Discipline, Modality)
        self.assertIn("Modality", grid.headers)
        self.assertIn("Quantity", grid.headers)

        # Test CSV & Markdown export
        csv_out = grid.to_csv()
        self.assertIn("Quantity", csv_out)
        self.assertIn("Ravenswood Branch", csv_out)

        md_out = grid.to_markdown()
        self.assertIn("|", md_out)
        self.assertIn("DEONTIC_RULE", md_out)

    def test_extractor_integration_with_synthesizer(self):
        """Verifies TextEntityRelationExtractor produces synthetic table grid and modality metadata."""
        text = "You must craft Ravenswood Branch with 3 Spiritwood Planks using Artificer 450."
        res = self.extractor.extract_from_text(text)

        self.assertIn("synthetic_grid", res)
        self.assertIn("modality_parse_result", res)
        self.assertIsInstance(res["synthetic_grid"], SyntheticTableGrid)
        self.assertEqual(res["synthetic_grid"].frames_included, 1)

    def test_cross_modal_triangulation_with_dynamic_derivations(self):
        """Verifies CrossModalTriangulator dynamically derives document aboutness and precursor chains."""
        table_csv = "Item,Component,Quantity,Discipline\nRavenswood Branch,Spiritwood Plank,3,Artificer"
        guide_text = (
            "To craft Nevermore, talk to Grandmaster Craftsman Hobbs at Lion's Arch. "
            "Ravenswood Branch requires 3 Spiritwood Planks with Artificer 450."
        )
        triangulator = CrossModalTriangulator(validate_shacl=True)
        res = triangulator.triangulate(table_csv, guide_text, table_name="test_dyn_nevermore")

        self.assertEqual(res.validation_status, "CONFORMING")
        self.assertGreater(len(res.fused_entities), 2)
        self.assertGreater(len(res.fused_triples), 2)


if __name__ == "__main__":
    unittest.main()
