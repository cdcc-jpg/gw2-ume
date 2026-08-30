# Strict Domain Agnosticism & Prohibition of Hardcoded Shortcuts

## 1. Core Mandate: Data & Ontology-Driven Execution Only
* **Strict Prohibition of Hardcoded Fallbacks**: Under NO circumstances should any model or assistant introduce hardcoded entity lookups, static weapon/armor branches, fixed column schemas, hardcoded tabular templates, or dummy node injections to obtain quick test passes or artificially please the user.
* **Root Cause Principle**: If an entity, relation, or table pattern fails to resolve or validate:
  1. Update the **declarative semantic schema** (OWL 2 TBox/ABox `.ttl` files or SHACL shapes).
  2. Improve the **generalized heuristic algorithm** (e.g. Least Common Subsumer, Vector Index lookup, or Dynamic Slot Clustering).
  3. **NEVER** write a hardcoded `if/elif` exception or static string fallback in Python business logic.

---

## 2. Forbidden Anti-Patterns
1. **No Static Table Templates**: Table generators and NLP extractors must dynamically discover semantic dimensions and induce column headers via ontology class introspection, never via static hardcoded lists (e.g. `['SubjectItem', 'RequiredComponent', ...]`).
2. **No Hardcoded Topic/Weapon Switchboards**: Code must not contain `if "nevermore" in text` or static dictionary maps of specific weapons/precursors. Precursor chains and recipe trees must be derived dynamically from ontology properties (`PROP_PRECURSOR_TO`, `PROP_REQUIRES_INGREDIENT`).
3. **No Dummy Node / Slot Fabrication**: Never inject artificial filler nodes (e.g. `mystic_component_1..4`) to artificially satisfy SHACL shapes.
4. **No Brittle Keyword Substring Routing**: CTA (Column Type Annotation) and CPA (Column Property Annotation) must rely on Least Common Subsumer (LCS) type support and OWL domain/range signatures, not fragile substring checks (e.g. `if "craft" in col.lower()`).

---

## 3. Generalization Guarantee
Every parser, extractor, and relational mesh component must function seamlessly across unseen items, expansions, currencies, stat combinations, drop rates, and vendors without source code modifications.
