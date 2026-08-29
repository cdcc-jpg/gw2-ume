"""Unit tests for Relational Mesh Constraint Solver in gw2-ume."""

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
from gw2_ume.matching.models import TableGrid
from gw2_ume.matching.cea import CellEntityAnnotator
from gw2_ume.matching.cta import ColumnTypeAnnotator
from gw2_ume.matching.cpa import ColumnPropertyAnnotator
from gw2_ume.matching.mesh_solver import RelationalMeshSolver


class TestRelationalMeshSolver(unittest.TestCase):
    """Comprehensive test suite for the Relational Mesh Constraint Solver."""

    def setUp(self) -> None:
        """Initialize test ontology and vector index."""
        self.reasoner = SymbolicAxiomReasoner()

        # Taxonomy
        self.reasoner.register_class(CLASS_ITEM, CLASS_THING, label="Item")
        self.reasoner.register_class(CLASS_EQUIPMENT, CLASS_ITEM, label="Equipment Item")
        self.reasoner.register_class(CLASS_WEAPON, CLASS_EQUIPMENT, label="Weapon")
        self.reasoner.register_class(CLASS_MATERIAL, CLASS_ITEM, label="Material Item")
        self.reasoner.register_class(CLASS_CURRENCY, CLASS_ITEM, label="Currency")
        self.reasoner.register_class(CLASS_NPC, CLASS_THING, label="NPC")
        self.reasoner.register_class(CLASS_PET, CLASS_THING, label="Ranger Pet")
        self.reasoner.register_class(CLASS_LEGENDARY_STEP, CLASS_ITEM, label="Legendary Crafting Step")

        # Disjointness
        self.reasoner.register_disjoint_classes(CLASS_PET, CLASS_ITEM)
        self.reasoner.register_disjoint_classes(CLASS_NPC, CLASS_ITEM)
        self.reasoner.register_disjoint_classes(CLASS_EQUIPMENT, CLASS_MATERIAL)

        # Properties
        self.reasoner.register_property(
            PROP_REQUIRES_MATERIAL,
            domain_iri=CLASS_ITEM,
            range_iri=CLASS_MATERIAL,
            label="requires material",
        )
        self.reasoner.register_property(
            PROP_COSTS_CURRENCY,
            domain_iri=CLASS_ITEM,
            range_iri=CLASS_CURRENCY,
            label="costs currency",
        )
        self.reasoner.register_property(
            PROP_SOLD_BY_NPC,
            domain_iri=CLASS_ITEM,
            range_iri=CLASS_NPC,
            label="sold by NPC",
        )

        # Vector Index
        self.vector_index = VectorIndex()

        for cls in self.reasoner.get_all_classes():
            labels = self.reasoner.get_class_labels(cls)
            self.vector_index.add_class(cls, label=labels[0])

        for prop in self.reasoner.get_all_properties():
            labels = self.reasoner.get_property_labels(prop)
            self.vector_index.add_property(prop, label=labels[0])

        # Polysemous "Raven" entities
        # 1. The Raven Spirit (Legendary Crafting Step for Nevermore IV)
        self.vector_index.add_entity(
            "http://gw2.wiki/legendary/TheRavenSpirit",
            label="Raven",
            types=[CLASS_LEGENDARY_STEP],
            description="Legendary Spirit crafted with Spiritwood Planks for Nevermore",
            aliases=["The Raven", "Raven Spirit", "Nevermore IV: The Raven"],
        )
        self.reasoner.register_entity(
            "http://gw2.wiki/legendary/TheRavenSpirit",
            [CLASS_LEGENDARY_STEP],
            label="Raven",
        )

        # 2. Juvenile Raven (Ranger Pet)
        self.vector_index.add_entity(
            "http://gw2.wiki/pet/JuvenileRaven",
            label="Raven",
            types=[CLASS_PET],
            description="Charming terrestrial pet found in Wayfarer Foothills",
            aliases=["Juvenile Raven", "Raven Pet"],
        )
        self.reasoner.register_entity(
            "http://gw2.wiki/pet/JuvenileRaven",
            [CLASS_PET],
            label="Raven",
        )

        # 3. Raven Havroun (NPC)
        self.vector_index.add_entity(
            "http://gw2.wiki/npc/RavenHavrounWeibe",
            label="Raven",
            types=[CLASS_NPC],
            description="Norn NPC Havroun of Raven in Hoelbrak",
            aliases=["Havroun of Raven", "Raven Havroun"],
        )
        self.reasoner.register_entity(
            "http://gw2.wiki/npc/RavenHavrounWeibe",
            [CLASS_NPC],
            label="Raven",
        )

        # Materials
        self.vector_index.add_entity(
            "http://gw2.wiki/item/SpiritwoodPlank",
            label="Spiritwood Plank",
            types=[CLASS_MATERIAL],
            description="Crafting wood material",
        )
        self.reasoner.register_entity(
            "http://gw2.wiki/item/SpiritwoodPlank",
            [CLASS_MATERIAL],
            label="Spiritwood Plank",
        )

        self.vector_index.add_entity(
            "http://gw2.wiki/item/ElonianLeatherSquare",
            label="Elonian Leather Square",
            types=[CLASS_MATERIAL],
            description="Crafting leather material",
        )
        self.reasoner.register_entity(
            "http://gw2.wiki/item/ElonianLeatherSquare",
            [CLASS_MATERIAL],
            label="Elonian Leather Square",
        )

        # NPCs
        self.vector_index.add_entity(
            "http://gw2.wiki/npc/GrandmasterCraftsmanHobbs",
            label="Hobbs",
            types=[CLASS_NPC],
            description="Legendary crafting vendor in Lion's Arch",
            aliases=["Grandmaster Craftsman Hobbs"],
        )
        self.reasoner.register_entity(
            "http://gw2.wiki/npc/GrandmasterCraftsmanHobbs",
            [CLASS_NPC],
            label="Hobbs",
        )

        # Direct Triples
        self.reasoner.register_triple(
            "http://gw2.wiki/legendary/TheRavenSpirit",
            PROP_REQUIRES_MATERIAL,
            "http://gw2.wiki/item/SpiritwoodPlank",
        )
        self.reasoner.register_triple(
            "http://gw2.wiki/legendary/TheRavenSpirit",
            PROP_SOLD_BY_NPC,
            "http://gw2.wiki/npc/GrandmasterCraftsmanHobbs",
        )

    def test_polysemous_entity_disambiguation_raven(self) -> None:
        """Verify solver disambiguates 'Raven' to TheRavenSpirit using relational mesh and neighbor Spiritwood Plank."""
        cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)
        cta = ColumnTypeAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        cpa = ColumnPropertyAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        solver = RelationalMeshSolver(reasoner=self.reasoner)

        table = TableGrid(
            headers=["Crafting Step", "Required Material"],
            rows=[
                ["Raven", "Spiritwood Plank x10"],
            ],
        )

        cea_map = cea.annotate_table(table)
        # Verify that CEA returned multiple candidates for "Raven"
        raven_cands = cea_map[(0, 0)].candidates
        self.assertGreaterEqual(len(raven_cands), 2)
        cand_iris = [c.entity_iri for c in raven_cands]
        self.assertIn("http://gw2.wiki/legendary/TheRavenSpirit", cand_iris)
        self.assertIn("http://gw2.wiki/pet/JuvenileRaven", cand_iris)

        cta_map = cta.annotate_table(table, cea_map)
        cpa_map = cpa.annotate_table(table, cta_map, cea_map)

        # Run Solver
        mesh = solver.solve(table, cea_map, cta_map, cpa_map)

        # Check Cell Resolution for (0, 0)
        resolved_raven = mesh.cell_annotations[(0, 0)]
        self.assertEqual(
            resolved_raven.entity_iri,
            "http://gw2.wiki/legendary/TheRavenSpirit",
            "Solver failed to disambiguate 'Raven' to TheRavenSpirit!",
        )

        # Check Extracted Triple
        self.assertEqual(len(mesh.row_triples), 1)
        triple = mesh.row_triples[0]
        self.assertEqual(triple.subject_iri, "http://gw2.wiki/legendary/TheRavenSpirit")
        self.assertEqual(triple.predicate_iri, PROP_REQUIRES_MATERIAL)
        self.assertEqual(triple.object_iri, "http://gw2.wiki/item/SpiritwoodPlank")
        self.assertEqual(triple.triple_origin, "direct_ontology")

    def test_missing_and_vague_column_headers(self) -> None:
        """Verify solver correctly interprets table with vague headers ('Thing', 'Mats')."""
        cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)
        cta = ColumnTypeAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        cpa = ColumnPropertyAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        solver = RelationalMeshSolver(reasoner=self.reasoner)

        table = TableGrid(
            headers=["Thing", "Mats"],
            rows=[
                ["The Raven", "Spiritwood Plank"],
            ],
        )

        cea_map = cea.annotate_table(table)
        cta_map = cta.annotate_table(table, cea_map)
        cpa_map = cpa.annotate_table(table, cta_map, cea_map)
        mesh = solver.solve(table, cea_map, cta_map, cpa_map)

        self.assertEqual(
            mesh.cell_annotations[(0, 0)].entity_iri,
            "http://gw2.wiki/legendary/TheRavenSpirit",
        )
        self.assertEqual(
            mesh.column_relations[(0, 1)].property_iri,
            PROP_REQUIRES_MATERIAL,
        )
        self.assertGreater(mesh.overall_confidence, 0.7)

    def test_multi_column_table_mesh(self) -> None:
        """Verify joint mesh on 3-column table: [Step, Material, Vendor]."""
        cea = CellEntityAnnotator(vector_index=self.vector_index, reasoner=self.reasoner)
        cta = ColumnTypeAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        cpa = ColumnPropertyAnnotator(reasoner=self.reasoner, vector_index=self.vector_index)
        solver = RelationalMeshSolver(reasoner=self.reasoner)

        table = TableGrid(
            headers=["Crafting Step", "Required Material", "Vendor"],
            rows=[
                ["Raven", "Spiritwood Plank", "Hobbs"],
            ],
        )

        cea_map = cea.annotate_table(table)
        cta_map = cta.annotate_table(table, cea_map)
        cpa_map = cpa.annotate_table(table, cta_map, cea_map)
        mesh = solver.solve(table, cea_map, cta_map, cpa_map)

        # Check cell annotations
        self.assertEqual(mesh.cell_annotations[(0, 0)].entity_iri, "http://gw2.wiki/legendary/TheRavenSpirit")
        self.assertEqual(mesh.cell_annotations[(0, 1)].entity_iri, "http://gw2.wiki/item/SpiritwoodPlank")
        self.assertEqual(mesh.cell_annotations[(0, 2)].entity_iri, "http://gw2.wiki/npc/GrandmasterCraftsmanHobbs")

        # Check extracted triples: (Raven, requiresMaterial, SpiritwoodPlank) and (Raven, soldByNPC, Hobbs)
        predicates = {t.predicate_iri for t in mesh.row_triples}
        self.assertIn(PROP_REQUIRES_MATERIAL, predicates)
        self.assertIn(PROP_SOLD_BY_NPC, predicates)


if __name__ == "__main__":
    unittest.main()
