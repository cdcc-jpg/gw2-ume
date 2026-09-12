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
- **3-Phase Neuro-Symbolic STI Engine (USE Architecture)**:
  - **Phase 1: Deterministic Extensional & Structural Anchors**: Grounds high-confidence columns using extensional graph coverage, regex signatures (chat codes, URIs, IDs), and SKOS lexical synonyms with zero LLM overhead.
  - **Phase 2: Sudoku Relational Propagation & Subject Clustering**: Groups multi-entity columns by candidate subject classes (`priory:Item`, `priory:DisciplineRecipe`), propagates domain/range constraints, and resolves ambiguous columns by relational elimination.
  - **Phase 3: Gemma Arbiter LLM (Constrained Stochastic Disambiguation)**: Invokes an SLM/LLM arbiter only on residual opaque/adversarial columns, strictly bounded by the ontology property candidates.
  - **Zero Domain Semantics in Python**: 100% of vocabularies, labels, predicates, and constraints are dynamically discovered from the ontology graph (`gw2_core.ttl`, `gw2-priory-ref`, `gw2-priory-def`).
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
│   │   ├── wild_community_crafting_table.csv  # Realistic community guide table (compound cells, no IDs)
│   │   ├── adversarial_table.csv              # Obfuscated multi-entity adversarial test table (100x16)
│   │   ├── legendary_nevermore_steps.csv      # Real 4-tier precursor collection table
│   │   ├── mystic_forge_tribute_matrix.csv     # 4-ingredient Mystic Forge recipe table
│   │   ├── crafting_discipline_materials.csv   # Artificer, Weaponsmith, Huntsman recipes
│   │   ├── unstructured_guide_nevermore.txt    # Real messy guide text with colloquial slang
│   │   ├── ambiguous_crafting_matrix.csv       # Polysemous terms and vague headers
│   │   └── noisy_scraped_tribute.csv           # Typos, OCR noise, and missing cells
│   └── benchmarks/
│       ├── ground_truth_wild_community_schema.json # Ground truth for wild community benchmark
│       ├── ground_truth_adversarial_schema.json # Ground truth schema for adversarial benchmark
│       ├── ground_truth_nevermore.json         # Ground truth CEA/CTA/CPA & constraints
│       └── benchmark_suite.json                # Benchmark suite configuration
├── ontologies/                                 # OWL 2 Turtle domain ontologies (from def and ref)
│   ├── gw2_core.ttl                            # Core classes, properties, disjointness axioms
│   └── gw2_legendary.ttl                       # Legendary crafting, precursor chains, recipes
├── scripts/
│   ├── run_wild_table_benchmark.py             # Wild community guide benchmark runner
│   ├── generate_adversarial_table.py           # Adversarial benchmark dataset synthesizer
│   └── run_table_annotation_experiment.py     # 3-Phase USE architecture benchmark runner
├── src/
│   └── gw2_ume/
│       ├── use_pipeline/                       # Full USE/USEY Track 2 Pipeline (Stages 0 to 8)
│       │   ├── stage0_setup.py                 # Dynamic ontology indexing & class/property summaries
│       │   ├── stage2_classification.py        # Value-based statistical column classification (zero header bias)
│       │   ├── stage3_table_checks.py          # Table-domain majority vote, sub-entity anchors & subject links
│       │   ├── stage4_row_loop.py              # Row execution, anchor subject swap, domain conflict checks
│       │   ├── stage5_cascade.py               # 6-step predicate cascade ladder, suffix reprobes & Stage 5a axiom veto
│       │   ├── stage6_object_resolution.py     # Concept object resolution for categoricals
│       │   ├── stage7_trust_scoring.py         # Trust scoring (Literal Typed, Deterministic Mapped, HITL, Boxed)
│       │   ├── stage8_assembly.py              # Assembly, triples.csv export, coverage report, SHACL pre-flight
│       │   └── pipeline.py                     # Unified USEPipeline runner
│       ├── ontology/                           # Ontology loader, schema introspection, & reasoner
│       │   ├── loader.py                       # Dynamic graph loader (gw2-priory-def & gw2-priory-ref)
│       │   ├── reasoner.py
│       │   ├── schema.py
│       │   └── vocab.py
│       ├── pipeline/                           # Neuro-symbolic ping-pong, USE annotator & UME engine
│       │   ├── engine.py
│       │   ├── pingpong.py
│       │   ├── enricher.py
│       │   └── semantic_table_annotator.py    # 3-Phase USE STI annotator (zero hardcoded rules)
│       ├── normalization/                      # LLM & heuristic normalizers, text cleaners
│       │   ├── llm_normalizer.py
│       │   └── text_cleaner.py                 # Multimodal cell decomposer & text normalizer
│       ├── indexing/                           # Dense embedding, FAISS & Numpy vector indices
│       │   ├── embedder.py
│       │   ├── faiss_index.py
│       │   └── builder.py
│       ├── mesh/                               # Relational mesh models & annotators
│       │   ├── models.py                       # RelationalMesh, MeshNode, MeshEdge, CEA/CTA/CPA
│       │   ├── annotator.py                    # Dense + lexical CEA, CTA, CPA annotator
│       │   └── relational_mesh.py              # W3C RDF Turtle serializer & SHACL validator
│       └── cli.py                              # Terminal CLI interface
├── tests/                                      # Full unit and integration test suite
│   ├── test_use_track2_pipeline.py             # 11 unit tests for full USE/USEY Track 2 pipeline
│   ├── test_wild_table_semantic_enrichment.py  # Wild table multimodal decomposition & mesh tests
│   ├── test_semantic_table_annotator.py        # 3-Phase annotator & adversarial robustness tests
│   └── ...
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

### 6. Run 3-Phase Adversarial Table Interpretation Benchmark
```bash
python3 scripts/run_table_annotation_experiment.py --table data/sample_tables/adversarial_table.csv
```

---

## 📊 Proof-of-Value Benchmark Results

### 1. Curated Crafting Matrices & Precursor Steps
Evaluated across 5 curated Guild Wars 2 benchmark datasets comparing an unconstrained statistical NLP baseline (TF-IDF + fuzzy matching without ontology reasoning) against the **GW2-UME Semantic Mesh** (Vector Index + Levenshtein/Jaccard + Constraint Solver + SHACL validation) against ground-truth annotations:

| Metric | Unconstrained Statistical Baseline | GW2-UME Semantic Mesh | Advantage / Gain |
| :--- | :---: | :---: | :---: |
| **Avg CEA Accuracy** | 26.3% | **58.5%** | **+32.2%** |
| **Avg CTA Accuracy** | 0.0% | **68.0%** | **+68.0%** |
| **Avg CPA F1 Score** | 0.0% | **31.7%** | **+31.7%** |
| **Avg Semantic Validity Rate** | 11.3% | **100.0%** | **+88.7%** |
| **Total SHACL Violations** | 1,377 | **0** | **100% Elimination on Curated Tables** |
| **Hallucinated Entities** | 662 | **0** | **100% Elimination on Curated Tables** |

### 2. 3-Phase Adversarial Multi-Entity Benchmark (USE Architecture)
Evaluates the `SemanticTableAnnotator` against an adversarial, multi-entity table ($100 \times 16$) containing deceptive traps ("false friends"), opaque machine-generated headers, colloquial synonyms, and standard properties across multiple intertwined entities (`priory:DisciplineRecipe` and `priory:Item`):

| Header Challenge Type | Example Headers | True Property | Annotation Accuracy | Resolution Phase |
| :--- | :--- | :--- | :---: | :--- |
| **Deceptive / False Friend** | `armor_defense` (contains weapon power) | `priory:minWeaponPower` | **100.0% (4/4)** | Phase 2 (Range & Uniqueness) |
| **Deceptive / False Friend** | `item_rank` (contains copper vendor coins) | `priory:hasVendorValue` | **100.0% (4/4)** | Phase 2 (Extensional Range) |
| **Deceptive / False Friend** | `gold_price` (contains level values 0-80) | `priory:requiredLevel` | **100.0% (4/4)** | Phase 2 (Relational Propagation) |
| **Opaque Machine Header** | `col_02` (numeric item ID) | `priory:gw2Id` | **100.0% (4/4)** | Phase 1 (Extensional ID Match) |
| **Opaque Machine Header** | `col_04` (semi-colon flags `"AccountBound;NoSell"`) | `priory:itemFlags` | **100.0% (4/4)** | Phase 3 (Gemma Arbiter) |
| **Colloquial Synonym** | `artwork_uri` | `priory:icon` | **100.0% (4/4)** | Phase 1 (Regex & SKOS altLabel) |
| **Colloquial Synonym** | `ping_code` | `priory:chatCode` | **100.0% (4/4)** | Phase 1 (Regex `[&...]`) |
| **Multi-Entity Discovery** | `priory:producesItem` (`Recipe` $\rightarrow$ `Item`) | Relation Axiom | **100.0% (20/20)** | Inter-Entity Relational Verifier |

- **Overall Property Annotation Accuracy (CPA)**: **16/16 (100.0%)**
- **Subject Entity Clustering Accuracy (CTA)**: **16/16 (100.0%)**
- **Deceptive Header Traps Caught & Overridden**: **4/4 (100.0%)**
- **Execution Latency**: **~0.026 seconds** (deterministic phases handle 94% of decisions; LLM arbiter invoked solely on high-entropy residual columns).
- **Zero Domain Semantics in Python**: Graph-driven schema discovery.

### 3. Wild Community Guide Benchmark (Zero Database IDs & Multimodal Decomposition)
Evaluates `RelationalMesh` and multimodal cell decomposition against a real-world, messy community crafting guide ($20 \times 7$) spanning *Nevermore*, *H.O.P.E.*, *Astralaria*, *Sunrise*, and *Mystic Tribute*. In contrast to synthetic benchmarks with internal database primary keys (`gw2Id`, `gw2RecipeId`), this wild table features compound unstructured cells, colloquial merchant notes, and zero numerical database IDs:

| Challenge Modality | Wild Cell Example | Decomposition & Enrichment Result | W3C RDF Graph Edge |
| :--- | :--- | :--- | :--- |
| **Compound Multi-Ingredients** | `"3x Spiritwood Plank + 3x Deldrimor Steel Ingot"` | Unpacks discrete ingredients and integer quantities | `priory:requiresIngredient` |
| **Discipline & Skill Threshold** | `"Artificer (450)"`, `"Huntsman 500"` | Segregates discipline concept from numeric rating literal | `priory:requiresDiscipline`, `priory:requiresDisciplineRating` |
| **Vendor Merchant & Geographic Zone** | `"Hobbs in Lion's Arch"` | Links vendor NPC entity to geographic map zone | `priory:obtainedFromVendor`, `priory:locatedInZone` |
| **Mixed Monetary Currencies** | `"5g + 10003 karma"`, `"10g + 500 karma"` | Disaggregates liquid coins from token currencies | `priory:costsCurrency` |
| **Zero Database IDs** | No `gw2Id` or `gw2RecipeId` columns | Grounds entities purely via dense vector + lexical CEA | Canonical `item:`, `vendor:`, `zone:` URIs |

#### Benchmark Performance (`output/wild_table_benchmark_results.json`):
- **CEA Precision (Cell Entity Linking)**: **82.6% (128/155)**
- **CTA Accuracy (Column Types)**: **100.0% (7/7)**
- **CPA Coverage (Relation Edges)**: **100.0% (6/6)**
- **SHACL Shape Validation**: **CONFORMING (0 violations)**
- **Knowledge Graph Scale**: **289 Mesh Nodes, 203 Mesh Edges, 21,933 RDF Triples** (`output/wild_community_mesh.ttl`)
- **Execution Latency**: **~27 seconds** (including full dense vector embedding search and graph reasoning)

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
