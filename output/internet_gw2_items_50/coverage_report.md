# USE Pipeline Track 2 - Semantic Assembly & Coverage Report

## 1. Executive Summary

- **Total RDF Triples Emitted:** `300`
- **Predicate Mapping Coverage:** `100.00%`
- **Strong-Matched Ratio (Confidence >= 0.70):** `66.67%`
- **Triples Requiring Review (review_flag=True):** `100`

## 2. Module_Action Distribution

| Module Action | Count | Percentage |
| :--- | :---: | :---: |
| **Deterministic Mapped** | 50 | 16.7% |
| **Literal Typed** | 150 | 50.0% |
| **HITL Validation** | 100 | 33.3% |
| **Literal Boxed** | 0 | 0.0% |

## 3. Pre-Flight SHACL Shape Validation

- **SHACL Conformance Status:** ✓ CONFORMING
```
Validation Report
Conforms: True
```

## 4. Gaps and Items Requiring HITL Review

Found **100** triples flagged for human verification:

| Subject | Predicate | Object | Confidence | Method | Action |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `4` | `https://priory.gw2/def/gw2Id` | `4` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `4` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `5` | `https://priory.gw2/def/gw2Id` | `5` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `5` | `https://priory.gw2/def/hasItemType` | `Trophy` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `6` | `https://priory.gw2/def/gw2Id` | `6` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `6` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `15` | `https://priory.gw2/def/gw2Id` | `15` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `15` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `24` | `https://priory.gw2/def/gw2Id` | `24` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `24` | `https://priory.gw2/def/hasItemType` | `Consumable` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `33` | `https://priory.gw2/def/gw2Id` | `33` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `33` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `46` | `https://priory.gw2/def/gw2Id` | `46` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `46` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `47` | `https://priory.gw2/def/gw2Id` | `47` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `47` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `56` | `https://priory.gw2/def/gw2Id` | `56` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `56` | `https://priory.gw2/def/hasItemType` | `Back` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `57` | `https://priory.gw2/def/gw2Id` | `57` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `57` | `https://priory.gw2/def/hasItemType` | `Back` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `58` | `https://priory.gw2/def/gw2Id` | `58` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `58` | `https://priory.gw2/def/hasItemType` | `Back` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `59` | `https://priory.gw2/def/gw2Id` | `59` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `59` | `https://priory.gw2/def/hasItemType` | `Back` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `60` | `https://priory.gw2/def/gw2Id` | `60` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |

*(Showing first 25 of 100 flagged triples)*
