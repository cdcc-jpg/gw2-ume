"""USE/USEY Track 2 Pipeline Architecture for Structured Tabular Ingestion.

Zero Domain Semantics in Python.
Stages:
- Stage 0: One-Time Setup & Multi-Tier Indexing (stage0_setup.py)
- Stage 2: Value-Based Column Classification (stage2_classification.py)
- Stage 3: Whole-Table Checks & Sub-Entity Anchors (stage3_table_checks.py)
- Stage 4: Row Loop & Subject Linking (stage4_row_loop.py)
- Stage 5 & 5a: Predicate Cascade Ladder, Suffix Reprobes, & Axiom Veto (stage5_cascade.py)
- Stage 6: Concept Object Resolution (stage6_object_resolution.py)
- Stage 7: Trust Scoring & Module_Action Assignment (stage7_trust_scoring.py)
- Stage 8: Assembly, triples.csv, Coverage Report & SHACL Commit (stage8_assembly.py)
- Unified Pipeline Runner: USEPipeline (pipeline.py)
"""

from gw2_ume.use_pipeline.stage0_setup import OntologyIndex
from gw2_ume.use_pipeline.stage2_classification import ColumnRole, ValueClassifier
from gw2_ume.use_pipeline.stage3_table_checks import TableCheckContext, TableChecker
from gw2_ume.use_pipeline.stage4_row_loop import RowLoopExecutor, Triple
from gw2_ume.use_pipeline.stage5_cascade import MatchResult, PredicateResolver
from gw2_ume.use_pipeline.stage6_object_resolution import ObjectResolutionResult, ObjectResolver
from gw2_ume.use_pipeline.stage7_trust_scoring import TrustScorer
from gw2_ume.use_pipeline.stage8_assembly import AssemblyResult, TriplesAssembler
from gw2_ume.use_pipeline.pipeline import USEPipeline

__all__ = [
    "USEPipeline",
    "OntologyIndex",
    "ColumnRole",
    "ValueClassifier",
    "TableCheckContext",
    "TableChecker",
    "RowLoopExecutor",
    "Triple",
    "MatchResult",
    "PredicateResolver",
    "ObjectResolutionResult",
    "ObjectResolver",
    "TrustScorer",
    "AssemblyResult",
    "TriplesAssembler",
]
