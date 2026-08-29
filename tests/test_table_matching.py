"""Unit tests for Cell Entity Annotation (CEA), Column Type Annotation (CTA), and Column Property Annotation (CPA)."""

import unittest
from gw2_ume.ontology.namespaces import (
    GW2,
    CLASS_THING,
    CLASS_ITEM,
    CLASS_EQUIPMENT,
    CLASS_WEAPON,
    CLASS_MATERIAL,
    CLASS_CURRENCY,
    CLASS_NPC,
    CLASS_PET,
    CLASS_LEGENDARY_STEP,
    PROP_REQUIRES_MATERIAL,
    PROP_COSTS_CURRENCY,
    PROP_SOLD_BY_NPC,
)
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner
from gw2_ume.retrieval.vector_index import VectorIndex
from gw2_ume.matching.cleaning import clean_cell_text
from gw2_ume.matching.models import TableGrid
from gw2_ume.matching.cea import CellEntityAnnotator
from gw2_ume.matching.cta import ColumnTypeAnnotator
from gw2_ume.matching.cpa import ColumnPropertyAnnotator


class TestTableMatching(unittest.TestCase):
    """Test suite for STI components: CEA, CTA, and CPA."""

    def setUp(self) -> None:
        """Set up ontology taxonomy, entities, and vector index."""
        self.reasoner = SymbolicAxiomReasoner()

        # Build class hierarchy
        # Thing -> Item -> EquipmentItem -> Weapon -> (Sword, Dagger, Staff)
        # Thing -> Item -> MaterialItem
        # Thing -> Item -> Currency
        # Thing -> NPC
        # Thing -> RangerPet
        # Thing -> LegendaryCraftingStep
        self.reasoner.register_class(CLASS_ITEM, CLASS_THING, label="Item", description="Game item")
        self.reasoner.register_class(CLASS_EQUIPMENT, CLASS_ITEM, label="Equipment Item", description="Equippable item")
        self.reasoner.register_class(CLASS_WEAPON, CLASS_EQUIPMENT, label="Weapon", description="Combat weapon")
        self.reasoner.register_class(f"{CLASS_WEAPON}/Sword", CLASS_WEAPON, label="Sword")
        self.reasoner.register_class(f"{CLASS_WEAPON}/Dagger", CLASS_WEAPON, label="Dagger")
        self.reasoner.register_class(f"{CLASS_WEAPON}/Staff", CLASS_WEAPON, label="Staff")

        self.reasoner.register_class(CLASS_MATERIAL, CLASS_ITEM, label="Material Item", description="Crafting ingredient")
        self.reasoner.register_class(CLASS_CURRENCY, CLASS_ITEM, label="Currency", description="In-game currency")
        self.reasoner.register_class(CLASS_NPC, CLASS_THING, label="NPC", description="Non-player character")
        self.reasoner.register_class(CLASS_PET, CLASS_THING, label="Ranger Pet", description="Ranger companion")
        self.reasoner.register_class(CLASS_LEGENDARY_STEP, CLASS_THING, label="Legendary Step", description="Legendary crafting tier")

        # Disjointness
        self.reasoner.register_disjoint_classes(CLASS_EQUIPMENT, CLASS_MATERIAL)
        self.reasoner.register_disjoint_classes(CLASS_NPC, CLASS_ITEM)
        self.reasoner.register_disjoint_classes(CLASS_PET, CLASS_ITEM)

        # Properties
        self.reasoner.register_property(
            PROP_REQUIRES_MATERIAL,
            domain_iri=CLASS_ITEM,
            range_iri=CLASS_MATERIAL,
            label="requires material",
            description="Specifies material required for crafting",
        )
        self.reasoner.register_property(
            PROP_COSTS_CURRENCY,
            domain_iri=CLASS_ITEM,
            range_iri=CLASS_CURRENCY,
            label="costs currency",
            description="Specifies currency cost",
        )
        self.reasoner.register_property(
            PROP_SOLD_BY_NPC,
            domain_iri=CLASS_ITEM,
            range_iri=CLASS_NPC,
            label="sold by NPC",
            description="Vendor selling the item",
        )

        # Vector Index
        self.vector_index = VectorIndex()

        # Add classes to index
        for cls in self.reasoner.get_all_classes():
            labels = self.reasoner.get_class_labels(cls)
            self.vector_index.add_class(cls, label=labels[0])

        # Add properties to index
        for prop in self.reasoner.get_all_properties():
            labels = self.reasoner.get_property_labels(prop)
            self.vector_index.add_property(prop, label=labels[0])

        # Register entities in reasoner & vector index
        # 1. Weapons
        self.vector_index.add_entity(
            "http://gw2.wiki/item/Bolt",
            label="Bolt",
            types=[f"{CLASS_WEAPON}/Sword"],
            description="Legendary Sword precursor",
        )
        self.reasoner.register_entity("http://gw2.wiki/item/Bolt", [f"{CLASS_WEAPON}/Sword"], label="Bolt")

        self.vector_index.add_entity(
            "http://gw2.wiki/item/Incinerator",
            label="Incinerator",
            types=[f"{CLASS_WEAPON}/Dagger"],
            description="Legendary Dagger",
        )
        self.reasoner.register_entity("http://gw2.wiki/item/Incinerator", [f"{CLASS_WEAPON}/Dagger"], label="Incinerator")

        self.vector_index.add_entity(
            "http://gw2.wiki/item/Nevermore",
            label="Nevermore",
            types=[f"{CLASS_WEAPON}/Staff"],
            description="Legendary Staff",
        )
        self.reasoner.register_entity("http://gw2.wiki/item/Nevermore", [f"{CLASS_WEAPON}/Staff"], label="Nevermore")

        # 2. Materials
        self.vector_index.add_entity(
            "http://gw2.wiki/item/SpiritwoodPlank",
            label="Spiritwood Plank",
            types=[CLASS_MATERIAL],
            description="Ascended crafting wood material",
        )
        self.reasoner.register_entity("http://gw2.wiki/item/SpiritwoodPlank", [CLASS_MATERIAL], label="Spiritwood Plank")

        self.vector_index.add_entity(
            "http://gw2.wiki/item/ElonianLeatherSquare",
            label="Elonian Leather Square",
            types=[CLASS_MATERIAL],
            description="Ascended crafting leather material",
        )
        self.reasoner.register_entity("http://gw2.wiki/item/ElonianLeatherSquare", [CLASS_MATERIAL], label="Elonian Leather Square")

        self.vector_index.add_entity(
            "http://gw2.wiki/item/MysticClover",
            label="Mystic Clover",
            types=[CLASS_MATERIAL],
            description="Mystic forge material for legendaries",
        )
        self.reasoner.register_entity("http://gw2.wiki/item/MysticClover", [CLASS_MATERIAL], label="Mystic Clover")

        # 3. Triples
        self.reasoner.register_triple("http://gw2.wiki/item/Bolt", PROP_REQUIRES_MATERIAL, "http://gw2.wiki/item/MysticClover")
        self.reasoner.register_triple("http://gw2.wiki/item/Incinerator", PROP_REQUIRES_MATERIAL, "http://gw2.wiki/item/MysticClover")
        self.reasoner.register_triple("http://gw2.wiki/item/Nevermore", PROP_REQUIRES_MATERIAL, "http://gw2.wiki/item/SpiritwoodPlank")

    def test_cell_text_cleaning(self) -> None:
        """Verify cell cleaner strips quantities, tiers, currencies, and wiki formatting."""
        cases = [
            ("[[Spiritwood Plank]] x10", "Spiritwood Plank"),
            ("10x [[Elonian Leather Square]]", "Elonian Leather Square"),
            ("The Raven (Tier 1)", "The Raven"),
            ("100g 50s [[Mystic Clover]]", "Mystic Clover"),
            ("<span>Bolt</span> (5 ea)", "Bolt"),
            ("Nevermore [[Nevermore|Staff]]", "Nevermore Staff"),
            ("10 🪙 Mystic Clover x250", "Mystic Clover"),
            ("Tier 4 Superior Sigil", "Superior Sigil"),
        ]
        for raw, expected in cases:
            cleaned = clean_cell_text(raw)
            self.assertEqual(cleaned, expected, f"Failed on raw text: '{raw}'")

    def test_cell_entity_annotation_cea(self) -> None:
        """Verify CEA matches cleaned cells to top-k ontology entity candidates."""
        cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)

        cell_res = cea.annotate_cell("[[Spiritwood Plank]] x20", row_idx=0, col_idx=1)
        self.assertEqual(cell_res.cleaned_text, "Spiritwood Plank")
        self.assertIsNotNone(cell_res.top_candidate)
        self.assertEqual(cell_res.top_candidate.entity_iri, "http://gw2.wiki/item/SpiritwoodPlank")
        self.assertIn(CLASS_MATERIAL, cell_res.top_candidate.types)
        self.assertGreater(cell_res.top_candidate.score, 0.9)

        # Full table annotation
        grid = TableGrid(
            headers=["Weapon", "Material"],
            rows=[
                ["[[Bolt]]", "10x [[Mystic Clover]]"],
                ["[[Nevermore]]", "20x [[Spiritwood Plank]]"],
            ],
        )
        table_ann = cea.annotate_table(grid)
        self.assertEqual(len(table_ann), 4)
        self.assertEqual(table_ann[(0, 0)].top_candidate.label, "Bolt")
        self.assertEqual(table_ann[(0, 1)].top_candidate.label, "Mystic Clover")
        self.assertEqual(table_ann[(1, 0)].top_candidate.label, "Nevermore")
        self.assertEqual(table_ann[(1, 1)].top_candidate.label, "Spiritwood Plank")

    def test_column_type_annotation_cta_hierarchy_lcs(self) -> None:
        """Verify CTA aggregates candidate types and generalizes via Least Common Subsumer (LCS)."""
        cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)
        cta = ColumnTypeAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)

        # Column 0 has Bolt (Sword), Incinerator (Dagger), Nevermore (Staff)
        # Their LCS in hierarchy is Weapon
        table = TableGrid(
            headers=["Output", "Required Material"],
            rows=[
                ["Bolt", "Mystic Clover"],
                ["Incinerator", "Mystic Clover"],
                ["Nevermore", "Spiritwood Plank"],
            ],
        )
        cea_map = cea.annotate_table(table)
        cta_results = cta.annotate_table(table, cea_map)

        # Check Col 0: Weapon should be the top inferred class or strong candidate
        col_0_types = cta_results[0]
        self.assertTrue(len(col_0_types) > 0)
        top_iris = [ct.class_iri for ct in col_0_types[:3]]
        self.assertIn(CLASS_WEAPON, top_iris)
        self.assertEqual(col_0_types[0].cell_support_ratio, 1.0)

        # Check Col 1: MaterialItem should be top candidate
        col_1_types = cta_results[1]
        self.assertEqual(col_1_types[0].class_iri, CLASS_MATERIAL)
        self.assertEqual(col_1_types[0].cell_support_ratio, 1.0)

    def test_column_property_annotation_cpa(self) -> None:
        """Verify CPA discovers object properties linking column pairs based on triples and types."""
        cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)
        cta = ColumnTypeAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        cpa = ColumnPropertyAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)

        table = TableGrid(
            headers=["Crafted Weapon", "Required Material"],
            rows=[
                ["Bolt", "Mystic Clover"],
                ["Nevermore", "Spiritwood Plank"],
            ],
        )
        cea_map = cea.annotate_table(table)
        cta_map = cta.annotate_table(table, cea_map)
        cpa_map = cpa.annotate_table(table, cta_map, cea_map)

        # Pair (0, 1): Crafted Weapon -> Required Material
        self.assertIn((0, 1), cpa_map)
        pair_props = cpa_map[(0, 1)]
        self.assertTrue(len(pair_props) > 0)
        best_prop = pair_props[0]
        self.assertEqual(best_prop.property_iri, PROP_REQUIRES_MATERIAL)
        self.assertEqual(best_prop.row_support_count, 2)
        self.assertGreater(best_prop.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
