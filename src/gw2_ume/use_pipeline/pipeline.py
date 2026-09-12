"""USE Track 2 Pipeline: Unified End-to-End Semantic Table Interpretation Engine.

Zero Domain Semantics in Python: Operates purely through dynamic ontology graph introspection
and statistical value shapes.
Orchestrates:
- Stage 0: Ontology setup, summaries, string and embedding indexes (stage0_setup.py)
- Stage 1: Read CSV table / DataFrame
- Stage 2: Value-based column classification (stage2_classification.py)
- Stage 3: Whole-table checks: 3a domain vote, 3b anchor detection, 3c subject-link resolution (stage3_table_checks.py)
- Stage 4: Row loop execution with anchor swapping, domain contradiction checks, subject links (stage4_row_loop.py)
  - Stage 5 & 5a: Predicate cascade ladder, suffix probes, deterministic axiom veto (stage5_cascade.py)
  - Stage 6: Concept-shaped object resolution (stage6_object_resolution.py)
  - Stage 7: Trust scoring & Module_Action assignment with downgrade rule (stage7_trust_scoring.py)
- Stage 8: Assembly into triples.csv, coverage_report.md, and optional SHACL pre-flight (stage8_assembly.py)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd
from rdflib import Graph

from gw2_ume.use_pipeline.stage0_setup import OntologyIndex
from gw2_ume.use_pipeline.stage2_classification import ColumnRole, ValueClassifier
from gw2_ume.use_pipeline.stage3_table_checks import TableCheckContext, TableChecker
from gw2_ume.use_pipeline.stage4_row_loop import RowLoopExecutor, Triple
from gw2_ume.use_pipeline.stage5_cascade import PredicateResolver
from gw2_ume.use_pipeline.stage6_object_resolution import ObjectResolver
from gw2_ume.use_pipeline.stage7_trust_scoring import TrustScorer
from gw2_ume.use_pipeline.stage8_assembly import AssemblyResult, TriplesAssembler


class USEPipeline:
    """Universal Semantic Engine (USE) Track 2 Pipeline."""

    def __init__(
        self,
        ontology_graph_or_path: Optional[Union[Graph, str, Path]] = None,
        enable_llm: bool = False,
        llm_client: Optional[Callable[[str], str]] = None,
        use_sentence_transformers: bool = True,
    ):
        self.enable_llm = enable_llm
        self.llm_client = llm_client
        self.use_sentence_transformers = use_sentence_transformers

        # Initialize components
        self.classifier = ValueClassifier()
        self.trust_scorer = TrustScorer()
        self.assembler = TriplesAssembler()

        # Initialize Stage 0 Index
        self.index = OntologyIndex(use_sentence_transformers=use_sentence_transformers)
        self.predicate_resolver = PredicateResolver(
            self.index, enable_llm=self.enable_llm, llm_client=self.llm_client
        )
        self.object_resolver = ObjectResolver(self.index)
        self.table_checker = TableChecker(self.index, self.predicate_resolver)
        self.row_executor = RowLoopExecutor(
            ontology_index=self.index,
            predicate_resolver=self.predicate_resolver,
            object_resolver=self.object_resolver,
            trust_scorer=self.trust_scorer,
        )

        if ontology_graph_or_path is not None:
            self.load_ontology(ontology_graph_or_path)

    def load_ontology(self, ontology_graph_or_path: Union[Graph, str, Path]) -> USEPipeline:
        """Loads or updates ontology graph and rebuilds Stage 0 indexes."""
        self.index.load_graph(ontology_graph_or_path)
        # Update components with the newly indexed graph
        self.predicate_resolver = PredicateResolver(
            self.index, enable_llm=self.enable_llm, llm_client=self.llm_client
        )
        self.object_resolver = ObjectResolver(self.index)
        self.table_checker = TableChecker(self.index, self.predicate_resolver)
        self.row_executor = RowLoopExecutor(
            ontology_index=self.index,
            predicate_resolver=self.predicate_resolver,
            object_resolver=self.object_resolver,
            trust_scorer=self.trust_scorer,
        )
        return self

    def run(
        self,
        data: Union[str, Path, pd.DataFrame],
        output_dir: Optional[Union[str, Path]] = None,
        shacl_shapes_graph: Optional[Graph] = None,
    ) -> AssemblyResult:
        """Executes full pipeline Stages 1 to 8 on tabular data.
        
        Args:
            data: File path to CSV or pandas DataFrame.
            output_dir: Directory where triples.csv and coverage_report.md should be written.
            shacl_shapes_graph: Optional SHACL shapes graph for pre-flight validation.

        Returns:
            AssemblyResult containing triples DataFrame, coverage report, and metrics.
        """
        # Stage 1: Ingest table
        if isinstance(data, (str, Path)):
            df = pd.read_csv(data)
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            raise TypeError(f"Expected CSV path or DataFrame, got {type(data)}")

        # Stage 2: Value-Based Column Classification
        column_roles: Dict[str, ColumnRole] = self.classifier.classify_table(df)

        # Stage 3: Whole-Table Checks (3a Domain Vote, 3b Anchors, 3c Subject Links)
        table_context: TableCheckContext = self.table_checker.analyze_table(df, column_roles)

        # Stage 4: Row Loop (Subject swap, Stage 5/5a predicates, Stage 6 objects, Stage 7 trust, Subject-Links)
        triples: List[Triple] = self.row_executor.execute_table(
            df=df,
            column_roles=column_roles,
            table_context=table_context,
        )

        # Stage 8: Assembly, CSV export, Markdown report, SHACL pre-flight
        result: AssemblyResult = self.assembler.assemble(
            triples=triples,
            output_dir=output_dir,
            shacl_shapes_graph=shacl_shapes_graph,
        )

        return result
