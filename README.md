# GW2-UME: Universal Matrix Extraction & Neuro-Symbolic Semantic Layer for Guild Wars 2

[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![RDFLib](https://img.shields.io/badge/RDFLib-7.x-orange.svg)](https://rdflib.readthedocs.io/)
[![SHACL](https://img.shields.io/badge/W3C-SHACL%20Validated-brightgreen.svg)](https://www.w3.org/TR/shacl/)

**GW2-UME** is a neuro-symbolic semantic extraction framework and relational mesh engine designed for complex domain matrices in Guild Wars 2. It integrates **Hybrid Dense Retrieval + Ontological Constraint Checking** to transform guide text, semi-structured tables, and scraped game matrices into formal W3C RDF knowledge graphs validated with OWL 2 ontologies and SHACL shape rules.

*Validated on curated GW2 domain crafting tables and semi-structured matrices.*

---

## 🌟 Core Features

- **Tabular Semantic Annotation (STI)**:
  - **CEA (Cell Entity Annotation)**: Links raw cell mentions to canonical ontology entities using dense embedding retrieval and lexical matching.
  - **CTA (Column Type Annotation)**: Infers ontology class types for tabular columns (`PrecursorWeapon`, `CraftingMaterial`, `CraftingDiscipline`, `Vendor`, `MapZone`, `IngredientQuantity`) via Least Common Subsumer (LCS) hierarchy analysis.
  - **CPA (Column Property Annotation)**: Predicts directed relational predicates between columns based on dynamic ontological domain/range compatibility.
- **Relational Mesh Construction**:
  - Constructs multi-tier directed graphs linking collection steps, components, vendors, disciplines, and map zones.
  - Models sequential precursor progression chains (Tier 1 $\rightarrow$ Tier 2 $\rightarrow$ Tier 3 $\rightarrow$ Tier 4).
  - Serializes to W3C **RDF Turtle** and **JSON-LD**.
- **Dynamic Ontology Signature Extraction**:
  - Automatically extracts disjoint types (`owl:disjointWith`, `owl:AllDisjointClasses`) and predicate domain/range signatures (`rdfs:domain`, `rdfs:range`) directly from loaded RDF/OWL ontology graphs.
- **Neuro-Symbolic Ping-Pong Engine**:
  - Structured multi-pass feedback dialogue between a **Neural Proposer** (statistical/LLM proposal generation) and a **Symbolic Validator** (OWL 2 reasoner & SHACL shape constraints).
  - Automated diagnostic feedback loop resolving polysemy, header mismatches, and domain/range constraint violations.
- **Interactive HTML Visualizer**:
  - Standalone HTML dashboard with an interactive node-link graph canvas, annotated table view, ping-pong trace timeline, and Turtle / JSON-LD export.

---

## 📁 Repository Structure

```text
gw2-ume/
├── data/
│   ├── sample_tables/
│   │   ├── legendary_nevermore_steps.csv      # Real 4-tier precursor collection table
│   │   ├── mystic_forge_tribute_matrix.csv     # 4-ingredient Mystic Forge recipe table
│   │   ├── crafting_discipline_materials.csv   # Artificer, Weaponsmith, Huntsman recipes
│   │   ├── unstructured_guide_nevermore.txt    # Real messy guide text with colloquial slang
│   │   ├── ambiguous_crafting_matrix.csv       # Polysemous terms and vague headers
│   │   └── noisy_scraped_tribute.csv           # Typos, OCR noise, and missing cells
│   └── benchmarks/
│       ├── ground_truth_nevermore.json         # Ground truth CEA/CTA/CPA & constraints
│       └── benchmark_suite.json                # Benchmark suite configuration
├── ontologies/                                 # OWL 2 Turtle domain ontologies
│   ├── gw2_core.ttl                            # Core classes, properties, disjointness axioms
│   └── gw2_legendary.ttl                       # Legendary crafting, precursor chains, recipes
├── src/
│   └── gw2_ume/
│       ├── ontology/                           # Ontology loader, schema introspection, & reasoner
│       │   ├── loader.py
│       │   ├── reasoner.py
│       │   ├── schema.py
│       │   └── vocab.py
│       ├── pipeline/                           # Neuro-symbolic ping-pong & UME engine
│       │   ├── engine.py
│       │   ├── pingpong.py
│       │   └── enricher.py
│       ├── normalization/                      # LLM & heuristic normalizers, text cleaners
│       │   ├── llm_normalizer.py
│       │   └── text_cleaner.py
│       ├── indexing/                           # Dense embedding, FAISS & Numpy vector indices
│       │   ├── embedder.py
│       │   ├── faiss_index.py
│       │   └── builder.py
│       ├── mesh/                               # Relational mesh models & annotators
│       │   ├── models.py
│       │   ├── annotator.py
│       │   └── relational_mesh.py
│       └── cli.py                              # Terminal CLI interface
├── tests/                                      # Full unit and integration test suite
├── pyproject.toml
└── README.md
```

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/clementd/gw2-ume.git
cd gw2-ume

# Install locally in editable mode
pip install -e .
```

---

## 💻 CLI Usage

The `gw2-ume` CLI provides a unified terminal interface:

### 1. Match Table & Build Relational Mesh
```bash
gw2-ume match-table data/sample_tables/legendary_nevermore_steps.csv --format turtle --output output.ttl
```

### 2. Classify Unstructured Text Guide
```bash
gw2-ume classify-text data/sample_tables/unstructured_guide_nevermore.txt --output guide.ttl
```

### 3. Run Neuro-Symbolic Ping-Pong Dialogue
```bash
gw2-ume pingpong data/sample_tables/ambiguous_crafting_matrix.csv --verbose
```

### 4. Execute Head-to-Head Proof-of-Value Benchmark
```bash
gw2-ume benchmark
```

### 5. Generate Standalone HTML Visualizer Dashboard
```bash
gw2-ume visualize data/sample_tables/legendary_nevermore_steps.csv --output dashboard.html
```

---

## 📊 Proof-of-Value Benchmark Results

Evaluated across 5 curated GW2 benchmark datasets comparing an unconstrained statistical NLP baseline (TF-IDF + fuzzy matching without ontology reasoning) against the **GW2-UME Semantic Mesh** (Vector Index + Levenshtein/Jaccard + Constraint Solver + SHACL validation) against ground-truth annotations:

| Metric | Unconstrained Statistical Baseline | GW2-UME Semantic Mesh | Advantage / Gain |
| :--- | :---: | :---: | :---: |
| **Avg CEA Accuracy** | 26.3% | **58.5%** | **+32.2%** |
| **Avg CTA Accuracy** | 0.0% | **68.0%** | **+68.0%** |
| **Avg CPA F1 Score** | 0.0% | **31.7%** | **+31.7%** |
| **Avg Semantic Validity Rate** | 11.3% | **100.0%** | **+88.7%** |
| **Total SHACL Violations** | 1,377 | **0** | **100% Elimination on Curated Tables** |
| **Hallucinated Entities** | 662 | **0** | **100% Elimination on Curated Tables** |

### Why Ontological Constraints Matter:
1. **Polysemy Disambiguation**: Resolves ambiguous mentions (e.g. *"Raven"* as companion pet vs. precursor staff vs. NPC Havroun) using column-level type hierarchies and domain/range checking.
2. **Noise Resistance**: Rebinds OCR artifacts and colloquial slang to canonical entities in the ontology graph.
3. **Axiomatic Consistency**: Enforces domain-specific invariants (e.g. recipe input slot limits, discipline matching, positive integer quantities).

---

## 🔍 Capabilities, Scope & Limitations

### Current Capabilities
- Hybrid retrieval coupling dense text embeddings (FAISS / Numpy vector indices) with fuzzy string matching.
- Dynamic introspection of OWL 2 axioms (`owl:disjointWith`, `owl:AllDisjointClasses`, `rdfs:domain`, `rdfs:range`, `rdfs:subClassOf`) directly from RDF graphs.
- Multi-turn neuro-symbolic ping-pong dialogue loop refining ambiguous neural proposals through structured diagnostic feedback.
- W3C SHACL shape validation and standards-compliant RDF Turtle and JSON-LD serialization.

### Limitations & Validation Scope
- **Domain Scope**: Validated primarily on curated Guild Wars 2 crafting matrices, precursor chains, and wiki tables.
- **Ontology Dependency**: Requires a structured OWL/RDFS schema to formulate domain constraints and validation rules.
- **Irregular Table Layouts**: Best suited for standard tabular grids, key-value tables, and clean matrix layouts; deeply nested or merged-header tables require upstream normalization.

---

## 🗺️ Roadmap

- **SemTab Challenge Benchmarking**: Benchmark the system against standardized Semantic Table Interpretation (SemTab) challenge datasets.
- **Automated Multi-Domain Schema Induction**: Extend ontology loading to support arbitrary OWL/RDFS and Wikidata schemas with zero code modification.
- **Broad Knowledge Base Grounding**: Expand entity linking integration to general-domain knowledge graphs (Wikidata, DBpedia, Schema.org).

---

## 🧪 Testing

Run all unit and integration tests using Python's built-in `unittest`:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 📜 License

MIT License. See `LICENSE` for details.
