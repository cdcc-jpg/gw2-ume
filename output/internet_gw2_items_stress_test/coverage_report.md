# USE Pipeline Track 2 - Semantic Assembly & Coverage Report

## 1. Executive Summary

- **Total RDF Triples Emitted:** `300`
- **Predicate Mapping Coverage:** `100.00%`
- **Strong-Matched Ratio (Confidence >= 0.70):** `66.67%`
- **Triples Requiring Review (review_flag=True):** `50`

## 2. Module_Action Distribution

| Module Action | Count | Percentage |
| :--- | :---: | :---: |
| **Deterministic Mapped** | 50 | 16.7% |
| **Literal Typed** | 200 | 66.7% |
| **HITL Validation** | 50 | 16.7% |
| **Literal Boxed** | 0 | 0.0% |

## 3. Pre-Flight SHACL Shape Validation

- **SHACL Conformance Status:** ✓ CONFORMING
```
Validation Report
Conforms: True
```

## 4. Gaps and Items Requiring HITL Review

Found **50** triples flagged for human verification:

| Subject | Predicate | Object | Confidence | Method | Action |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `4` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `5` | `https://priory.gw2/def/hasItemType` | `Trophy` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `6` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `15` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `24` | `https://priory.gw2/def/hasItemType` | `Consumable` | 0.60 | AxiomFilter-Ambiguous | HITL Validation |
| `33` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `46` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `47` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Weapon` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `56` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/BackpackItem` | 0.27 | AxiomFilter-Ambiguous+Concept-EmbeddingMatch | HITL Validation |
| `57` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/BackpackItem` | 0.27 | AxiomFilter-Ambiguous+Concept-EmbeddingMatch | HITL Validation |
| `58` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/BackpackItem` | 0.27 | AxiomFilter-Ambiguous+Concept-EmbeddingMatch | HITL Validation |
| `59` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/BackpackItem` | 0.27 | AxiomFilter-Ambiguous+Concept-EmbeddingMatch | HITL Validation |
| `60` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/BackpackItem` | 0.27 | AxiomFilter-Ambiguous+Concept-EmbeddingMatch | HITL Validation |
| `61` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/BackpackItem` | 0.27 | AxiomFilter-Ambiguous+Concept-EmbeddingMatch | HITL Validation |
| `62` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `63` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `64` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `65` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `68` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `69` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `70` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `71` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `72` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `73` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |
| `74` | `https://priory.gw2/def/hasItemType` | `https://priory.gw2/def/Armor` | 0.59 | AxiomFilter-Ambiguous+Concept-StringMatch | HITL Validation |

*(Showing first 25 of 50 flagged triples)*
