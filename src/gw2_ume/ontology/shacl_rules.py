"""SHACL shape definitions and validation rules for GW2-UME."""

from __future__ import annotations
from typing import Tuple, Dict, Any, List
import rdflib
from rdflib import Graph
import pyshacl

SHACL_RULES_TURTLE = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gw2: <https://gw2ume.org/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

gw2:PrecursorStaffShape a sh:NodeShape ;
    sh:targetClass gw2:PrecursorWeapon ;
    sh:property [
        sh:path gw2:craftedByDiscipline ;
        sh:minCount 1 ;
        sh:message "Precursor weapons must specify a crafting discipline." ;
    ] ;
    sh:property [
        sh:path gw2:requiresIngredient ;
        sh:minCount 1 ;
        sh:message "Precursor weapons must have at least one required ingredient." ;
    ] .

gw2:MysticForgeRecipeShape a sh:NodeShape ;
    sh:targetClass gw2:MysticForgeRecipe ;
    sh:property [
        sh:path gw2:requiresIngredient ;
        sh:minCount 4 ;
        sh:maxCount 4 ;
        sh:message "A Mystic Forge recipe for a legendary weapon must require exactly 4 ingredients." ;
    ] .

gw2:ItemQuantityShape a sh:NodeShape ;
    sh:targetClass gw2:Item ;
    sh:property [
        sh:path gw2:ingredientQuantity ;
        sh:datatype xsd:integer ;
        sh:minInclusive 1 ;
        sh:message "Ingredient quantity must be a positive integer >= 1." ;
    ] .

gw2:VendorLocationShape a sh:NodeShape ;
    sh:targetClass gw2:NPCVendor ;
    sh:property [
        sh:path gw2:locatedInZone ;
        sh:minCount 1 ;
        sh:message "Every NPC vendor must have an associated geographic zone." ;
    ] .
"""


def get_shacl_graph() -> Graph:
    """Returns the SHACL validation graph."""
    g = Graph()
    g.parse(data=SHACL_RULES_TURTLE, format="turtle")
    return g


def validate_mesh_shacl(data_graph: Graph) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """Validates an RDFLib data graph against the GW2 SHACL shapes.

    Returns:
        conforms (bool): True if graph satisfies all shapes.
        report_text (str): Human-readable validation text.
        violations (list): Structured list of violation details.
    """
    shacl_graph = get_shacl_graph()
    conforms, results_graph, results_text = pyshacl.validate(
        data_graph=data_graph,
        shacl_graph=shacl_graph,
        inference="rdfs",
        abort_on_first=False,
        meta_shacl=False,
        debug=False,
    )

    violations = []
    # Parse results graph for structured violation details
    query = """
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT ?focusNode ?resultMessage ?resultPath ?severity
    WHERE {
        ?report sh:result ?result .
        ?result sh:focusNode ?focusNode .
        OPTIONAL { ?result sh:resultMessage ?resultMessage }
        OPTIONAL { ?result sh:resultPath ?resultPath }
        OPTIONAL { ?result sh:resultSeverity ?severity }
    }
    """
    for row in results_graph.query(query):
        violations.append({
            "focus_node": str(row[0]),
            "message": str(row[1]) if row[1] else "Constraint violation",
            "path": str(row[2]) if row[2] else "",
            "severity": str(row[3]) if row[3] else "Violation",
        })

    return conforms, results_text, violations


__all__ = ["SHACL_RULES_TURTLE", "get_shacl_graph", "validate_mesh_shacl"]
