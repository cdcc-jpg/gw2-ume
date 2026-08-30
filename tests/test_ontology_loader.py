from __future__ import annotations

import sys
from pathlib import Path
import unittest

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

import tempfile
from unittest.mock import patch

from gw2_ume.ontology.loader import GW2, GW2LEG, OntologyLoader
from gw2_ume.ontology.reasoner import SymbolicAxiomReasoner
from gw2_ume.ontology.schema import (
    AxiomVerificationResult,
    DatatypeProperty,
    Individual,
    ObjectProperty,
    OntologyClass,
)


class TestOntologyLoading(unittest.TestCase):
    """Tests for parsing, loading, and binding OWL 2 ontologies."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)

    def test_default_ontologies_loaded(self) -> None:
        """Verify both core and legendary ontologies load with expected triple volume."""
        graph = self.loader.graph
        self.assertGreater(len(graph), 800, "Combined graph should contain > 800 triples.")

    def test_iri_resolution(self) -> None:
        """Verify resolving prefixed strings and full URIs to URIRefs."""
        self.assertEqual(self.loader.resolve_iri("gw2:Item"), GW2.Item)
        self.assertEqual(self.loader.resolve_iri("gw2leg:Nevermore"), GW2LEG.Nevermore)
        self.assertEqual(self.loader.resolve_iri("rdfs:subClassOf"), RDFS.subClassOf)
        self.assertEqual(self.loader.resolve_iri("owl:Class"), OWL.Class)

    def test_to_prefixed_name(self) -> None:
        """Verify converting URIRefs back to compact prefixed notation."""
        self.assertEqual(self.loader.to_prefixed_name(GW2.Item), "gw2:Item")
        self.assertEqual(self.loader.to_prefixed_name(GW2LEG.Nevermore), "gw2leg:Nevermore")
        self.assertEqual(self.loader.to_prefixed_name(GW2.requiresMaterial), "gw2:requiresMaterial")

    def test_load_turtle_string(self) -> None:
        """Verify loading custom in-memory turtle snippets."""
        custom_loader = OntologyLoader()
        snippet = """
        @prefix ex: <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        ex:TestClass a owl:Class ;
            rdfs:label "Test Class"@en .
        """
        custom_loader.load_turtle_string(snippet)
        cls_obj = custom_loader.get_class("http://example.org/TestClass")
        self.assertIsNotNone(cls_obj)
        self.assertEqual(cls_obj.label, "Test Class")

    def test_dynamic_ontology_discovery(self) -> None:
        """Verify that dynamic loading loads gw2_core.ttl first and dynamically discovers all domain extensions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            core_ttl = tmp_path / "gw2_core.ttl"
            core_ttl.write_text(
                """
                @prefix gw2: <https://schema.gw2ume.org/core#> .
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                
                gw2:Item a owl:Class ;
                    rdfs:label "Item"@en .
                gw2:Weapon a owl:Class ;
                    rdfs:subClassOf gw2:Item ;
                    rdfs:label "Weapon"@en .
                """,
                encoding="utf-8",
            )

            hope_ttl = tmp_path / "gw2_hope.ttl"
            hope_ttl.write_text(
                """
                @prefix gw2: <https://schema.gw2ume.org/core#> .
                @prefix gw2hope: <https://schema.gw2ume.org/hope#> .
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                
                gw2hope:HOPE a owl:NamedIndividual, gw2:Weapon ;
                    rdfs:label "H.O.P.E."@en .
                """,
                encoding="utf-8",
            )

            with patch.object(OntologyLoader, "default_ontologies_path", return_value=tmp_path):
                loader = OntologyLoader(auto_load_defaults=True)
                cls_item = loader.get_class("https://schema.gw2ume.org/core#Item")
                self.assertIsNotNone(cls_item)

                ind_hope = loader.get_individual("https://schema.gw2ume.org/hope#HOPE")
                self.assertIsNotNone(ind_hope)
                self.assertEqual(ind_hope.label, "H.O.P.E.")

    def test_syntax_error_resilience(self) -> None:
        """Verify that a malformed .ttl file does not crash loading of valid ontologies."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            core_ttl = tmp_path / "gw2_core.ttl"
            core_ttl.write_text(
                """
                @prefix gw2: <https://schema.gw2ume.org/core#> .
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                
                gw2:Item a owl:Class ;
                    rdfs:label "Item"@en .
                """,
                encoding="utf-8",
            )

            broken_ttl = tmp_path / "gw2_broken.ttl"
            broken_ttl.write_text(
                "THIS IS COMPLETELY INVALID TURTLE SYNTAX ::: ??? !!!",
                encoding="utf-8",
            )

            valid_ext_ttl = tmp_path / "gw2_valid_ext.ttl"
            valid_ext_ttl.write_text(
                """
                @prefix gw2: <https://schema.gw2ume.org/core#> .
                @prefix ex: <https://example.org/> .
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                
                ex:ValidObject a owl:NamedIndividual, gw2:Item ;
                    rdfs:label "Valid Object"@en .
                """,
                encoding="utf-8",
            )

            with patch.object(OntologyLoader, "default_ontologies_path", return_value=tmp_path):
                loader = OntologyLoader(auto_load_defaults=True)

                cls_item = loader.get_class("https://schema.gw2ume.org/core#Item")
                self.assertIsNotNone(cls_item)

                ind_valid = loader.get_individual("https://example.org/ValidObject")
                self.assertIsNotNone(ind_valid)
                self.assertEqual(ind_valid.label, "Valid Object")


class TestClassHierarchyAndIntrospection(unittest.TestCase):
    """Tests for class taxonomy, subClassOf inheritance, and schema dataclasses."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_list_classes(self) -> None:
        """Verify classes are discovered and mapped to OntologyClass dataclasses."""
        classes = self.loader.list_classes()
        class_iris = {c.iri for c in classes}

        self.assertIn(str(GW2.Item), class_iris)
        self.assertIn(str(GW2.Weapon), class_iris)
        self.assertIn(str(GW2.Armor), class_iris)
        self.assertIn(str(GW2.CraftingMaterial), class_iris)
        self.assertIn(str(GW2.LegendaryWeapon), class_iris)
        self.assertIn(str(GW2.PrecursorWeapon), class_iris)
        self.assertIn(str(GW2.AscendedMaterial), class_iris)
        self.assertIn(str(GW2.Currency), class_iris)
        self.assertIn(str(GW2.Vendor), class_iris)
        self.assertIn(str(GW2.MapZone), class_iris)
        self.assertIn(str(GW2.Achievement), class_iris)

    def test_get_class_details(self) -> None:
        """Verify OntologyClass fields (label, pref_label, alt_labels, comment, super_classes)."""
        cls_obj = self.loader.get_class(GW2.CraftingMaterial)
        self.assertIsNotNone(cls_obj)
        self.assertEqual(cls_obj.pref_label, "Crafting Material")
        self.assertIn("Material", cls_obj.alt_labels)
        self.assertIn("Mats", cls_obj.alt_labels)
        self.assertIn(str(GW2.Item), cls_obj.super_classes)

    def test_subclass_hierarchy(self) -> None:
        """Verify direct and transitive subclass exploration."""
        # Direct subclasses of Item
        direct_item_subs = self.loader.get_subclasses(GW2.Item, direct=True)
        self.assertIn(GW2.Weapon, direct_item_subs)
        self.assertIn(GW2.Armor, direct_item_subs)
        self.assertIn(GW2.Trinket, direct_item_subs)
        self.assertIn(GW2.CraftingMaterial, direct_item_subs)
        self.assertNotIn(GW2.LegendaryWeapon, direct_item_subs)

        # Transitive subclasses of Item
        all_item_subs = self.loader.get_subclasses(GW2.Item, direct=False)
        self.assertIn(GW2.LegendaryWeapon, all_item_subs)
        self.assertIn(GW2.PrecursorWeapon, all_item_subs)
        self.assertIn(GW2.AscendedMaterial, all_item_subs)
        self.assertIn(GW2.RefinedMaterial, all_item_subs)
        self.assertIn(GW2.RawMaterial, all_item_subs)

    def test_is_subclass_of_reasoning(self) -> None:
        """Verify symbolic is_subclass_of queries across transitive relationships."""
        # Reflexive
        self.assertTrue(self.reasoner.is_subclass_of(GW2.LegendaryWeapon, GW2.LegendaryWeapon))
        self.assertTrue(self.reasoner.is_subclass_of(GW2.Item, GW2.Item))

        # Direct
        self.assertTrue(self.reasoner.is_subclass_of(GW2.LegendaryWeapon, GW2.Weapon))
        self.assertTrue(self.reasoner.is_subclass_of(GW2.Weapon, GW2.Item))

        # Transitive
        self.assertTrue(self.reasoner.is_subclass_of(GW2.LegendaryWeapon, GW2.Item))
        self.assertTrue(self.reasoner.is_subclass_of(GW2.AscendedMaterial, GW2.Item))
        self.assertTrue(self.reasoner.is_subclass_of(GW2.MysticForgeRecipe, GW2.CraftingRecipe))

        # Negative checks
        self.assertFalse(self.reasoner.is_subclass_of(GW2.Item, GW2.Weapon))
        self.assertFalse(self.reasoner.is_subclass_of(GW2.Weapon, GW2.Armor))
        self.assertFalse(self.reasoner.is_subclass_of(GW2.CraftingMaterial, GW2.Currency))

    def test_is_instance_of_reasoning(self) -> None:
        """Verify individuals correctly inherit broad class types."""
        # Nevermore is LegendaryWeapon -> Weapon -> Item
        self.assertTrue(self.reasoner.is_instance_of(GW2LEG.Nevermore, GW2.LegendaryWeapon))
        self.assertTrue(self.reasoner.is_instance_of(GW2LEG.Nevermore, GW2.Weapon))
        self.assertTrue(self.reasoner.is_instance_of(GW2LEG.Nevermore, GW2.Item))
        self.assertFalse(self.reasoner.is_instance_of(GW2LEG.Nevermore, GW2.Armor))

        # Spiritwood Plank is AscendedMaterial -> CraftingMaterial -> Item
        self.assertTrue(self.reasoner.is_instance_of(GW2LEG.SpiritwoodPlank, GW2.AscendedMaterial))
        self.assertTrue(self.reasoner.is_instance_of(GW2LEG.SpiritwoodPlank, GW2.CraftingMaterial))
        self.assertTrue(self.reasoner.is_instance_of(GW2LEG.SpiritwoodPlank, GW2.Item))
        self.assertFalse(self.reasoner.is_instance_of(GW2LEG.SpiritwoodPlank, GW2.Currency))

    def test_class_hierarchy_tree(self) -> None:
        """Verify generation of nested class hierarchy tree."""
        tree = self.loader.get_class_hierarchy(GW2.Item)
        self.assertEqual(tree["name"], "Item")
        child_names = [c["name"] for c in tree["children"]]
        self.assertIn("Weapon", child_names)
        self.assertIn("Armor", child_names)
        self.assertIn("Crafting Material", child_names)


class TestDisjointnessAxioms(unittest.TestCase):
    """Tests for pairwise and AllDisjointClasses reasoning."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_direct_disjointness(self) -> None:
        """Verify direct owl:disjointWith checks."""
        self.assertTrue(self.reasoner.are_disjoint(GW2.CraftingMaterial, GW2.Currency))
        self.assertTrue(self.reasoner.are_disjoint(GW2.Currency, GW2.CraftingMaterial))
        self.assertTrue(self.reasoner.are_disjoint(GW2.Weapon, GW2.Armor))
        self.assertTrue(self.reasoner.are_disjoint(GW2.Weapon, GW2.Trinket))
        self.assertTrue(self.reasoner.are_disjoint(GW2.Armor, GW2.Trinket))

    def test_inherited_disjointness(self) -> None:
        """Verify disjointness inherited down subclass hierarchies."""
        # LegendaryWeapon (subclass of Weapon) and AscendedArmor (subclass of Armor) are disjoint
        self.assertTrue(self.reasoner.are_disjoint(GW2.LegendaryWeapon, GW2.AscendedArmor))
        self.assertTrue(self.reasoner.are_disjoint(GW2.PrecursorWeapon, GW2.LegendaryArmor))
        self.assertTrue(self.reasoner.are_disjoint(GW2.AscendedMaterial, GW2.Currency))
        self.assertTrue(self.reasoner.are_disjoint(GW2.LegendaryWeapon, GW2.Currency))
        self.assertTrue(self.reasoner.are_disjoint(GW2.LegendaryWeapon, GW2.Vendor))

    def test_non_disjoint_classes(self) -> None:
        """Verify classes in same branch or compatible are not disjoint."""
        self.assertFalse(self.reasoner.are_disjoint(GW2.LegendaryWeapon, GW2.Weapon))
        self.assertFalse(self.reasoner.are_disjoint(GW2.Weapon, GW2.LegendaryWeapon))
        self.assertFalse(self.reasoner.are_disjoint(GW2.Item, GW2.Weapon))
        self.assertFalse(self.reasoner.are_disjoint(GW2.LegendaryWeapon, GW2.LegendaryWeapon))


class TestPropertiesAndDomainRange(unittest.TestCase):
    """Tests for ObjectProperties, DatatypeProperties, inverse properties, and domain/range axioms."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_object_property_introspection(self) -> None:
        """Verify ObjectProperty discovery, labels, and inverse relations."""
        has_precursor = self.loader.get_object_property(GW2.hasPrecursor)
        self.assertIsNotNone(has_precursor)
        self.assertEqual(has_precursor.pref_label, "has precursor")
        self.assertEqual(has_precursor.inverse_of, str(GW2.isPrecursorOf))
        self.assertIn(str(GW2.LegendaryWeapon), has_precursor.domains)
        self.assertIn(str(GW2.PrecursorWeapon), has_precursor.ranges)

        requires_material = self.loader.get_object_property(GW2.requiresMaterial)
        self.assertIsNotNone(requires_material)
        self.assertEqual(requires_material.inverse_of, str(GW2.isMaterialFor))
        self.assertIn(str(GW2.CraftingRecipe), requires_material.domains)
        self.assertIn(str(GW2.Item), requires_material.ranges)

    def test_datatype_property_introspection(self) -> None:
        """Verify DatatypeProperty discovery, domains, and ranges."""
        vendor_cost = self.loader.get_datatype_property(GW2.vendorCost)
        self.assertIsNotNone(vendor_cost)
        self.assertIn(str(GW2.Item), vendor_cost.domains)
        self.assertIn(str(XSD.integer), vendor_cost.ranges)

        gen_num = self.loader.get_datatype_property(GW2.generationNumber)
        self.assertIsNotNone(gen_num)
        self.assertIn(str(GW2.LegendaryWeapon), gen_num.domains)
        self.assertIn(str(XSD.integer), gen_num.ranges)

    def test_get_domain_and_range(self) -> None:
        """Verify domain and range URIRef extraction."""
        domains, ranges = self.loader.get_domain_and_range(GW2.costsCurrency)
        self.assertIn(GW2.Item, domains)
        self.assertIn(GW2.Currency, ranges)

    def test_get_compatible_properties(self) -> None:
        """Verify discovery of valid ObjectProperties connecting two classes."""
        # Connecting LegendaryWeapon to PrecursorWeapon -> hasPrecursor
        props = self.reasoner.get_compatible_properties(GW2.LegendaryWeapon, GW2.PrecursorWeapon)
        prop_iris = [p.iri for p in props]
        self.assertIn(str(GW2.hasPrecursor), prop_iris)

        # Connecting Item to Currency -> costsCurrency
        props_curr = self.reasoner.get_compatible_properties(GW2.Item, GW2.Currency)
        prop_curr_iris = [p.iri for p in props_curr]
        self.assertIn(str(GW2.costsCurrency), prop_curr_iris)

        # Connecting Vendor to MapZone -> locatedIn
        props_loc = self.reasoner.get_compatible_properties(GW2.Vendor, GW2.MapZone)
        prop_loc_iris = [p.iri for p in props_loc]
        self.assertIn(str(GW2.locatedIn), prop_loc_iris)


class TestRelationValidation(unittest.TestCase):
    """Tests for validating proposed triples against ontology domain, range, and disjointness axioms."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_valid_object_property_relation(self) -> None:
        """Verify valid relations pass validation with truthy result and tuple unpacking."""
        res = self.reasoner.validate_relation(GW2LEG.Nevermore, GW2.hasPrecursor, GW2LEG.TheLivingRavens)
        self.assertTrue(res)
        self.assertTrue(res.is_valid)

        # Unpacking syntax support
        is_valid, message = res
        self.assertTrue(is_valid)
        self.assertIn("valid", message.lower())

    def test_domain_violation(self) -> None:
        """Verify domain violation when subject is incompatible with property domain."""
        # Miyani (Vendor) cannot have property hasPrecursor (domain: LegendaryWeapon)
        res = self.reasoner.validate_relation(GW2LEG.Miyani, GW2.hasPrecursor, GW2LEG.TheLivingRavens)
        self.assertFalse(res)
        self.assertFalse(res.is_valid)
        self.assertIn("Domain violation", res.message)
        self.assertIn("DomainConstraintViolation", res.violated_axioms)

    def test_range_violation(self) -> None:
        """Verify range violation when object is incompatible with property range."""
        # Nevermore hasPrecursor cannot point to Coin (Currency)
        res = self.reasoner.validate_relation(GW2LEG.Nevermore, GW2.hasPrecursor, GW2.Coin)
        self.assertFalse(res)
        self.assertIn("Range violation", res.message)
        self.assertIn("RangeConstraintViolation", res.violated_axioms)

    def test_object_property_rejects_literal(self) -> None:
        """Verify ObjectProperty fails when provided a literal value."""
        res = self.reasoner.validate_relation(GW2LEG.Nevermore, GW2.hasPrecursor, Literal("The Living Ravens"))
        self.assertFalse(res)
        self.assertIn("requires an individual/URI object", res.message)
        self.assertIn("ObjectPropertyRequiresURI", res.violated_axioms)

    def test_valid_datatype_property(self) -> None:
        """Verify valid datatype property assignments."""
        res = self.reasoner.validate_relation(GW2LEG.Nevermore, GW2.generationNumber, 2)
        self.assertTrue(res)
        self.assertTrue(res.is_valid)

    def test_invalid_datatype_mismatch(self) -> None:
        """Verify datatype mismatch for integer properties given non-integer strings."""
        res = self.reasoner.validate_relation(GW2LEG.Nevermore, GW2.generationNumber, "Second Generation")
        self.assertFalse(res)
        self.assertIn("Datatype mismatch", res.message)
        self.assertIn("DatatypeMismatchViolation", res.violated_axioms)


class TestIndividualsAndSynonyms(unittest.TestCase):
    """Tests for individual search, synonym/altLabel resolution, and instance property queries."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)

    def test_find_by_exact_and_alt_labels(self) -> None:
        """Verify searching individuals by primary label and colloquial altLabel synonyms."""
        # Search "Spiritwood" -> Spiritwood Plank
        matches = self.loader.find_individuals_by_label("Spiritwood")
        self.assertTrue(len(matches) > 0)
        iris = [m.iri for m in matches]
        self.assertIn(str(GW2LEG.SpiritwoodPlank), iris)

        # Search "Amalgams" -> Amalgamated Gemstone
        amalgam_matches = self.loader.find_individuals_by_label("Amalgams")
        self.assertTrue(len(amalgam_matches) > 0)
        self.assertIn(str(GW2LEG.AmalgamatedGemstone), [m.iri for m in amalgam_matches])

        # Search "Clovers" -> Mystic Clover
        clover_matches = self.loader.find_individuals_by_label("Clovers")
        self.assertTrue(len(clover_matches) > 0)
        self.assertIn(str(GW2LEG.MysticClover), [m.iri for m in clover_matches])

        # Search "Runestones" -> Icy Runestone
        runestone_matches = self.loader.find_individuals_by_label("Runestones")
        self.assertTrue(len(runestone_matches) > 0)
        self.assertIn(str(GW2LEG.IcyRunestone), [m.iri for m in runestone_matches])

    def test_miyani_vendor_details(self) -> None:
        """Verify vendor Miyani properties, location in Lion's Arch, and comments."""
        miyani = self.loader.get_individual(GW2LEG.Miyani)
        self.assertIsNotNone(miyani)
        self.assertEqual(miyani.pref_label, "Miyani")
        self.assertIn(str(GW2.Vendor), miyani.types)
        self.assertIn(str(GW2LEG.LionsArch), miyani.properties.get(str(GW2.locatedIn), []))

    def test_generation_2_weapons_present(self) -> None:
        """Verify Generation 2 legendary weapons are declared with generationNumber 2."""
        gen2_weapons = [
            GW2LEG.Nevermore,
            GW2LEG.Astralaria,
            GW2LEG.HOPE,
            GW2LEG.TheShiningBlade,
            GW2LEG.ChukaAndChampawat,
            GW2LEG.Exordium,
            GW2LEG.Sharur,
        ]
        for w_iri in gen2_weapons:
            ind = self.loader.get_individual(w_iri)
            self.assertIsNotNone(ind, f"Missing individual for {w_iri}")
            self.assertIn(str(GW2.LegendaryWeapon), ind.types)
            gen_vals = ind.data_properties.get(str(GW2.generationNumber), [])
            self.assertIn(2, gen_vals)


class TestNevermorePrecursorProgressionAndRecipes(unittest.TestCase):
    """Tests for Nevermore precursor progression tiers, collection steps, and Mystic Forge recipe tree."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_nevermore_precursor_chain(self) -> None:
        """Verify complete precursor chain resolution: Tier 1 -> Tier 2 -> Tier 3 -> Tier 4 -> Nevermore."""
        chain = self.reasoner.get_precursor_chain(GW2LEG.Nevermore)
        chain_prefixed = [self.loader.to_prefixed_name(x) for x in chain]

        expected_chain = [
            "gw2leg:RavenswoodBranch",
            "gw2leg:RavenswoodStaff",
            "gw2leg:TheRavenSpirit",
            "gw2leg:TheLivingRavens",
            "gw2leg:Nevermore",
        ]
        self.assertEqual(chain_prefixed, expected_chain)

    def test_nevermore_collection_steps_and_rewards(self) -> None:
        """Verify each tier collection achievement links to its respective precursor reward."""
        steps_and_rewards = [
            (GW2LEG.NevermoreI_RavenswoodBranch, GW2LEG.RavenswoodBranch),
            (GW2LEG.NevermoreII_RavenswoodStaff, GW2LEG.RavenswoodStaff),
            (GW2LEG.NevermoreIII_TheRavenSpirit, GW2LEG.TheRavenSpirit),
            (GW2LEG.NevermoreIV_TheLivingRavens, GW2LEG.TheLivingRavens),
        ]
        for ach_iri, reward_iri in steps_and_rewards:
            # Check achievement rewards item
            ach_ind = self.loader.get_individual(ach_iri)
            self.assertIsNotNone(ach_ind)
            self.assertIn(str(reward_iri), ach_ind.properties.get(str(GW2.rewardsItem), []))

            # Check item is rewardForAchievement
            item_ind = self.loader.get_individual(reward_iri)
            self.assertIsNotNone(item_ind)
            self.assertIn(str(ach_iri), item_ind.properties.get(str(GW2.rewardForAchievement), []))

    def test_nevermore_mystic_forge_recipe(self) -> None:
        """Verify 4-ingredient Mystic Forge recipe for Nevermore."""
        recipe = self.loader.get_individual(GW2LEG.NevermoreMysticForgeRecipe)
        self.assertIsNotNone(recipe)
        self.assertIn(str(GW2.MysticForgeRecipe), recipe.types)
        self.assertIn(str(GW2LEG.Nevermore), recipe.properties.get(str(GW2.producesItem), []))

        ingredients = recipe.properties.get(str(GW2.requiresMaterial), [])
        self.assertEqual(len(ingredients), 4)
        self.assertIn(str(GW2LEG.TheLivingRavens), ingredients)
        self.assertIn(str(GW2LEG.GiftOfNevermore), ingredients)
        self.assertIn(str(GW2LEG.MysticTribute), ingredients)
        self.assertIn(str(GW2LEG.GiftOfMastery), ingredients)

    def test_sub_gift_recipes(self) -> None:
        """Verify sub-gift recipes: Gift of Nevermore, Mystic Tribute, and Gift of Mastery."""
        # Gift of Nevermore Recipe
        gon_recipe = self.loader.get_individual(GW2LEG.GiftOfNevermoreRecipe)
        self.assertIsNotNone(gon_recipe)
        gon_ingredients = gon_recipe.properties.get(str(GW2.requiresMaterial), [])
        self.assertIn(str(GW2LEG.GiftOfWood), gon_ingredients)
        self.assertIn(str(GW2LEG.GiftOfEnergy), gon_ingredients)
        self.assertIn(str(GW2LEG.GiftOfInsight), gon_ingredients)
        self.assertIn(str(GW2LEG.IcyRunestone), gon_ingredients)

        # Mystic Tribute Recipe
        tribute_recipe = self.loader.get_individual(GW2LEG.MysticTributeRecipe)
        self.assertIsNotNone(tribute_recipe)
        tribute_ingredients = tribute_recipe.properties.get(str(GW2.requiresMaterial), [])
        self.assertIn(str(GW2LEG.MysticClover), tribute_ingredients)
        self.assertIn(str(GW2LEG.AmalgamatedGemstone), tribute_ingredients)
        self.assertIn(str(GW2LEG.GiftOfCondensedMagic), tribute_ingredients)
        self.assertIn(str(GW2LEG.GiftOfCondensedMight), tribute_ingredients)

        # Gift of Mastery Recipe
        mastery_recipe = self.loader.get_individual(GW2LEG.GiftOfMasteryRecipe)
        self.assertIsNotNone(mastery_recipe)
        mastery_ingredients = mastery_recipe.properties.get(str(GW2.requiresMaterial), [])
        self.assertIn(str(GW2LEG.BloodstoneShard), mastery_ingredients)
        self.assertIn(str(GW2LEG.ObsidianShard), mastery_ingredients)
        self.assertIn(str(GW2LEG.GiftOfExploration), mastery_ingredients)
        self.assertIn(str(GW2LEG.GiftOfBattle), mastery_ingredients)


class TestPathFindingAndReasoning(unittest.TestCase):
    """Tests for multi-hop graph path finding between weapons, gifts, and materials."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_find_connecting_paths_nevermore_to_materials(self) -> None:
        """Verify path finding resolves paths connecting Nevermore to Bloodstone Shard and Icy Runestone."""
        # Nevermore -> NevermoreMysticForgeRecipe -> GiftOfMastery -> GiftOfMasteryRecipe -> BloodstoneShard (4 hops)
        paths_bloodstone = self.reasoner.find_connecting_paths(
            GW2LEG.Nevermore,
            GW2LEG.BloodstoneShard,
            max_hops=4,
            directed=False,
        )
        self.assertTrue(len(paths_bloodstone) > 0, "Should find semantic paths between Nevermore and Bloodstone Shard.")

        # Nevermore -> NevermoreMysticForgeRecipe -> GiftOfNevermore -> GiftOfNevermoreRecipe -> IcyRunestone (4 hops)
        paths_runestone = self.reasoner.find_connecting_paths(
            GW2LEG.Nevermore,
            GW2LEG.IcyRunestone,
            max_hops=4,
            directed=False,
        )
        self.assertTrue(len(paths_runestone) > 0, "Should find semantic paths between Nevermore and Icy Runestone.")

    def test_cardinality_check(self) -> None:
        """Verify cardinality check utility."""
        res_valid = self.reasoner.check_cardinality(GW2LEG.Nevermore, GW2.hasPrecursor, count=1)
        self.assertTrue(res_valid)


class TestAttributeAndCurrencyExtensions(unittest.TestCase):
    """Tests for dynamic loading of GW2 attributes, stat combinations, and extended currencies."""

    def setUp(self) -> None:
        self.loader = OntologyLoader(auto_load_defaults=True)
        self.reasoner = SymbolicAxiomReasoner(self.loader)

    def test_attribute_and_combination_classes(self) -> None:
        """Verify Attribute, AttributeCombination, and ExpansionRelease classes are loaded."""
        from gw2_ume.ontology.vocab import PRIORY
        cls_attr = self.loader.get_class(str(PRIORY.Attribute))
        self.assertIsNotNone(cls_attr)
        self.assertEqual(cls_attr.pref_label, "Combat Attribute")

        cls_combo = self.loader.get_class(str(PRIORY.AttributeCombination))
        self.assertIsNotNone(cls_combo)
        self.assertEqual(cls_combo.pref_label, "Attribute Combination")

        cls_exp = self.loader.get_class(str(PRIORY.ExpansionRelease))
        self.assertIsNotNone(cls_exp)
        self.assertEqual(cls_exp.pref_label, "Expansion Release")

    def test_attribute_individuals(self) -> None:
        """Verify combat attribute individuals (Power, Precision, Agony Resistance, etc.)."""
        from gw2_ume.ontology.vocab import ATTRIBUTE
        power_ind = self.loader.get_individual(str(ATTRIBUTE.power))
        self.assertIsNotNone(power_ind)
        self.assertEqual(power_ind.label, "Power")

        ar_ind = self.loader.get_individual(str(ATTRIBUTE.agony_resistance))
        self.assertIsNotNone(ar_ind)
        self.assertEqual(ar_ind.label, "Agony Resistance")
        self.assertIn("AR", ar_ind.alt_labels)

    def test_stat_combination_individuals(self) -> None:
        """Verify attribute combinations (Berserker, Viper, Harrier, Marauder, Diviner)."""
        from gw2_ume.ontology.vocab import STAT, PRIORY, ATTRIBUTE, EXPANSION
        berserker = self.loader.get_individual(str(STAT.berserker))
        self.assertIsNotNone(berserker)
        self.assertEqual(berserker.pref_label, "Berserker's")
        self.assertIn("Zojja's", berserker.alt_labels)
        self.assertIn(str(ATTRIBUTE.power), berserker.properties.get(str(PRIORY.hasPrimaryAttribute), []))
        self.assertIn(str(ATTRIBUTE.precision), berserker.properties.get(str(PRIORY.hasSecondaryAttribute), []))
        self.assertIn(str(ATTRIBUTE.ferocity), berserker.properties.get(str(PRIORY.hasSecondaryAttribute), []))

        viper = self.loader.get_individual(str(STAT.viper))
        self.assertIsNotNone(viper)
        self.assertEqual(viper.pref_label, "Viper's")
        self.assertIn("Yassith's", viper.alt_labels)
        self.assertIn(str(ATTRIBUTE.power), viper.properties.get(str(PRIORY.hasPrimaryAttribute), []))
        self.assertIn(str(ATTRIBUTE.condition_damage), viper.properties.get(str(PRIORY.hasPrimaryAttribute), []))

    def test_extended_currencies(self) -> None:
        """Verify extended currencies (Unbound Magic, Volatile Magic, Magnetite Shard, etc.)."""
        from gw2_ume.ontology.vocab import CURRENCY, PRIORY
        unbound = self.loader.get_individual(str(CURRENCY.unbound_magic))
        self.assertIsNotNone(unbound)
        self.assertEqual(unbound.pref_label, "Unbound Magic")
        self.assertIn(str(PRIORY.Currency), unbound.types)

        volatile = self.loader.get_individual(str(CURRENCY.volatile_magic))
        self.assertIsNotNone(volatile)
        self.assertEqual(volatile.pref_label, "Volatile Magic")

        magnetite = self.loader.get_individual(str(CURRENCY.magnetite_shard))
        self.assertIsNotNone(magnetite)
        self.assertEqual(magnetite.pref_label, "Magnetite Shard")

    def test_dynamic_entity_catalog_registration(self) -> None:
        """Verify dynamic registration of attribute combinations and currencies into ENTITY_CATALOG."""
        from gw2_ume.ontology.schema import ENTITY_CATALOG
        self.assertIn("berserker", ENTITY_CATALOG)
        self.assertEqual(ENTITY_CATALOG["berserker"]["label"], "Berserker's")
        self.assertEqual(ENTITY_CATALOG["berserker"]["type_label"], "AttributeCombination")
        self.assertEqual(ENTITY_CATALOG["berserker"]["exotic_prefix"], "Berserker's")
        self.assertEqual(ENTITY_CATALOG["berserker"]["ascended_prefix"], "Zojja's")

        self.assertIn("viper", ENTITY_CATALOG)
        self.assertEqual(ENTITY_CATALOG["viper"]["label"], "Viper's")

        self.assertIn("unbound_magic", ENTITY_CATALOG)
        self.assertEqual(ENTITY_CATALOG["unbound_magic"]["label"], "Unbound Magic")
        self.assertEqual(ENTITY_CATALOG["unbound_magic"]["type_label"], "Currency")


if __name__ == "__main__":
    unittest.main()
