"""Universal Match Engine (UME) Master Orchestrator.

Provides the primary user-facing API for GW2 knowledge extraction, table interpretation,
neuro-symbolic ping-pong reasoning, and RDF/JSON-LD knowledge graph export.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from gw2_ume.models import (
    CandidateOntologyAxiom,
    CandidateTableInterpretation,
    EntitySpan,
    PingPongResult,
    RowRelation,
    TableGrid,
    TableInterpretationMesh,
    TextInterpretationResult,
)
from gw2_ume.normalization.llm_normalizer import (
    HeuristicNormalizer,
    LLMNormalizer,
    get_normalizer,
)
from gw2_ume.normalization.text_cleaner import (
    TextCleaner,
    extract_entity_spans,
    normalize_text,
    parse_table,
)
from gw2_ume.pipeline.enricher import KnowledgeGraphEnricher
from gw2_ume.pipeline.pingpong import NeuroSymbolicPingPongEngine, SymbolicAxiomReasoner

logger = logging.getLogger(__name__)


# ============================================================================
# UME ENGINE CLASS
# ============================================================================

class UMEEngine:
    """The central orchestrator for Guild Wars 2 Universal Match Engine (GW2-UME).

    Integrates:
    - Multi-format table parsing (Markdown, CSV, TSV, HTML, JSON)
    - Typo, colloquialism, and jargon normalization
    - Entity span and numerical modifier extraction
    - Neuro-symbolic ping-pong iterative reasoning
    - RDF/Turtle, JSON-LD, and Knowledge Graph enrichment
    - Ontology learning and candidate axiom generation
    """

    def __init__(
        self,
        normalizer: Optional[Union[LLMNormalizer, str]] = None,
        reasoner: Optional[SymbolicAxiomReasoner] = None,
        enricher: Optional[KnowledgeGraphEnricher] = None,
    ) -> None:
        """Initialize UMEEngine.

        Args:
            normalizer: LLMNormalizer instance or string identifier ('heuristic', 'local', 'gemini', 'openai', 'auto').
            reasoner: SymbolicAxiomReasoner instance.
            enricher: KnowledgeGraphEnricher instance.
        """
        if isinstance(normalizer, str):
            self.normalizer = get_normalizer(backend=normalizer)
        elif normalizer is not None:
            self.normalizer = normalizer
        else:
            self.normalizer = HeuristicNormalizer()

        self.reasoner = reasoner or SymbolicAxiomReasoner()
        self.enricher = enricher or KnowledgeGraphEnricher()
        self.pingpong_engine = NeuroSymbolicPingPongEngine(
            normalizer=self.normalizer,
            reasoner=self.reasoner,
        )

    # ------------------------------------------------------------------------
    # TABLE INTERPRETATION & PING-PONG
    # ------------------------------------------------------------------------

    def parse_table(
        self,
        table_data: Union[str, List[Any], Dict[str, Any], TableGrid],
        format_hint: Optional[str] = None,
    ) -> TableGrid:
        """Parse raw table inputs into a clean TableGrid."""
        return parse_table(table_data, format_hint=format_hint)

    def match_table(
        self,
        table_data: Union[str, List[Any], Dict[str, Any], TableGrid],
        format_hint: Optional[str] = None,
        use_pingpong: bool = True,
        max_iterations: int = 3,
    ) -> TableInterpretationMesh:
        """Match and interpret a table, returning the grounded TableInterpretationMesh.

        Args:
            table_data: Raw markdown, CSV, TSV, HTML, JSON, or TableGrid.
            format_hint: Optional format hint ('markdown', 'csv', 'tsv', 'html', 'json').
            use_pingpong: Whether to apply neuro-symbolic ping-pong validation (default: True).
            max_iterations: Max ping-pong loop iterations (default: 3).

        Returns:
            TableInterpretationMesh: Fully grounded and validated table interpretation.
        """
        grid = self.parse_table(table_data, format_hint=format_hint)
        if use_pingpong:
            res = self.pingpong_engine.run(grid, max_iterations=max_iterations)
            return res.mesh
        else:
            proposal = self.normalizer.extract_table_mentions(grid)
            return self.pingpong_engine._build_interpretation_mesh(grid, proposal)

    def pingpong_table(
        self,
        table_data: Union[str, List[Any], Dict[str, Any], TableGrid],
        max_iterations: int = 3,
        format_hint: Optional[str] = None,
    ) -> PingPongResult:
        """Run the NeuroSymbolicPingPongEngine directly on a table and return the full PingPongResult.

        Args:
            table_data: Raw table data or TableGrid.
            max_iterations: Maximum dialogue iterations (default: 3).
            format_hint: Optional format hint.

        Returns:
            PingPongResult: Complete result including iterations, history, mesh, and diagnostics.
        """
        grid = self.parse_table(table_data, format_hint=format_hint)
        return self.pingpong_engine.run(grid, max_iterations=max_iterations)

    # ------------------------------------------------------------------------
    # UNSTRUCTURED TEXT INTERPRETATION
    # ------------------------------------------------------------------------

    def normalize_text(self, text: str) -> str:
        """Normalize typos and colloquialisms in unstructured text."""
        return self.normalizer.normalize_text(text)

    def extract_spans(self, text: str) -> List[EntitySpan]:
        """Extract candidate entity spans, types, and quantities from text."""
        return self.normalizer.extract_entity_spans(text)

    def classify_text(self, text: str) -> TextInterpretationResult:
        """Extract entity spans and relations from unstructured text."""
        cleaned_text = TextCleaner.clean_text(text)
        spans = self.normalizer.extract_entity_spans(cleaned_text)

        # Build relations from spans in the same sentence
        relations: List[RowRelation] = []
        triples: List[Tuple[str, str, Any]] = []

        sentences = TextCleaner.split_sentences(cleaned_text)
        for s_idx, sentence in enumerate(sentences):
            sent_spans = [s for s in spans if s.sentence_idx == s_idx]
            if len(sent_spans) >= 2:
                # First span as candidate subject, subsequent spans as objects/ingredients
                subject_span = sent_spans[0]
                for obj_span in sent_spans[1:]:
                    rel = RowRelation(
                        row_idx=s_idx,
                        subject=subject_span.normalized_text or subject_span.text,
                        predicate="hasIngredient" if obj_span.candidate_types and obj_span.candidate_types[0] == "CraftingMaterial" else "relatesTo",
                        object=obj_span.normalized_text or obj_span.text,
                        quantity=obj_span.quantity,
                        unit=obj_span.unit,
                        confidence=0.85,
                    )
                    relations.append(rel)
                    triples.append((rel.subject, f"gw2ume:{rel.predicate}", f"gw2item:{obj_span.normalized_text or obj_span.text}"))

        return TextInterpretationResult(
            text=cleaned_text,
            spans=spans,
            relations=relations,
            triples=triples,
            summary=f"Extracted {len(spans)} entity spans and {len(relations)} relations across {len(sentences)} sentences.",
        )

    # ------------------------------------------------------------------------
    # KNOWLEDGE GRAPH & ONTOLOGY EXPORT
    # ------------------------------------------------------------------------

    def export_rdf(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
        format: str = "turtle",
    ) -> str:
        """Export interpretation to RDF string in requested format (default: 'turtle')."""
        if format.lower() == "turtle" or format.lower() == "ttl":
            return self.enricher.export_turtle(target)
        else:
            g = self.enricher.build_rdf_graph(target)
            return g.serialize(format=format)

    def export_jsonld(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> Dict[str, Any]:
        """Export interpretation to structured JSON-LD dictionary."""
        return self.enricher.export_jsonld(target)

    def export_triples(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> List[Tuple[str, str, Any]]:
        """Export raw list of (subject, predicate, object) triples."""
        if isinstance(target, PingPongResult):
            return target.mesh.triples
        elif isinstance(target, TableInterpretationMesh):
            return target.triples
        elif isinstance(target, TextInterpretationResult):
            return target.triples
        return []

    def propose_ontology_extensions(
        self,
        target: Union[TableInterpretationMesh, PingPongResult, TextInterpretationResult],
    ) -> List[CandidateOntologyAxiom]:
        """Propose candidate ontology extensions and new class/instance declarations."""
        return self.enricher.propose_ontology_extensions(target)
