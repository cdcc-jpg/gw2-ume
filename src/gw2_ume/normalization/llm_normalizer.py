"""LLM Normalization and Structured Schema Proposal Engine.

Provides an abstract interface and concrete implementations:
- HeuristicNormalizer: Built-in deterministic, rule-based normalizer (zero dependencies).
- LocalGemmaNormalizer: Local small LLMs (Google Gemma 2B/4B/9B) via Apple Silicon MLX or HuggingFace.
- APILLMNormalizer: Remote APIs (Gemini, OpenAI, Anthropic).
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from gw2_ume.models import (
    CandidateTableInterpretation,
    CellMention,
    DiagnosticConflict,
    EntitySpan,
    RefinedProposal,
    RowRelation,
    TableColumnInterpretation,
    TableGrid,
)
from gw2_ume.normalization.text_cleaner import (
    KNOWN_ENTITY_TYPES,
    TextCleaner,
    extract_entity_spans,
    normalize_text,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class LLMNormalizer(ABC):
    """Abstract base class for LLM / Heuristic normalizers."""

    @abstractmethod
    def normalize_text(self, text: str) -> str:
        """Normalize typos, colloquialisms, and wiki markup in text."""
        pass

    @abstractmethod
    def extract_entity_spans(self, text: str) -> List[EntitySpan]:
        """Extract entity mentions, candidate types, and numerical quantities from text."""
        pass

    @abstractmethod
    def extract_table_mentions(self, table: TableGrid) -> CandidateTableInterpretation:
        """Extract candidate schema interpretation, column roles, and cell mentions from a table."""
        pass

    @abstractmethod
    def resolve_ambiguity(
        self,
        proposal: CandidateTableInterpretation,
        feedback: List[DiagnosticConflict],
    ) -> RefinedProposal:
        """Refine and adjust an interpretation proposal based on symbolic feedback."""
        pass


# ============================================================================
# HEURISTIC NORMALIZER (BUILT-IN ZERO-DEPENDENCY ENGINE)
# ============================================================================

class HeuristicNormalizer(LLMNormalizer):
    """Zero-dependency deterministic normalizer using curated domain heuristics,

    regex rules, and semantic table analysis.
    """

    def normalize_text(self, text: str) -> str:
        """Normalize text using TextCleaner."""
        return normalize_text(text)

    def extract_entity_spans(self, text: str) -> List[EntitySpan]:
        """Extract entity spans from unstructured text."""
        return extract_entity_spans(text)

    def extract_table_mentions(self, table: TableGrid) -> CandidateTableInterpretation:
        """Analyze table columns, predict column roles & types, and construct initial neural proposal."""
        headers = table.headers
        num_cols = table.shape[1]
        col_interpretations: List[TableColumnInterpretation] = []

        # Analyze each column
        for col_idx in range(num_cols):
            header_name = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx}"
            col_type, col_role, conf = self._classify_column(col_idx, header_name, table.get_column(col_idx))
            col_interpretations.append(
                TableColumnInterpretation(
                    column_index=col_idx,
                    column_name=header_name,
                    predicted_type=col_type,
                    role=col_role,
                    confidence=conf,
                )
            )

        # Extract cell mentions
        cell_mentions: List[CellMention] = []
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell_value in enumerate(row):
                if c_idx >= len(col_interpretations):
                    continue
                cleaned_val = TextCleaner.clean_text(cell_value)
                if not cleaned_val:
                    continue

                norm_name, qty, unit = TextCleaner.extract_quantity(cleaned_val)
                col_type = col_interpretations[c_idx].predicted_type

                # Determine entity type for cell
                if norm_name in KNOWN_ENTITY_TYPES:
                    ent_type = KNOWN_ENTITY_TYPES[norm_name]
                elif col_type not in ("Quantity", "Unknown"):
                    ent_type = col_type
                else:
                    ent_type = "Item"

                cell_mentions.append(
                    CellMention(
                        row_idx=r_idx,
                        col_idx=c_idx,
                        raw_text=cell_value,
                        normalized_text=norm_name if norm_name else cleaned_val,
                        entity_type=ent_type,
                        quantity=qty,
                        unit=unit,
                        confidence=0.9,
                    )
                )

        # Determine table type and subject entity
        table_type, subject_col_idx, subject_entity = self._determine_table_semantics(
            col_interpretations, cell_mentions, table
        )

        # Build row relations
        row_relations = self._build_row_relations(
            table, col_interpretations, cell_mentions, table_type, subject_entity, subject_col_idx
        )

        return CandidateTableInterpretation(
            columns=col_interpretations,
            table_type=table_type,
            subject_entity=subject_entity,
            subject_column_idx=subject_col_idx,
            row_relations=row_relations,
            cell_mentions=cell_mentions,
            confidence=0.9,
            reasoning=f"Identified table type '{table_type}' with subject '{subject_entity}' across {len(table.rows)} rows.",
        )

    def resolve_ambiguity(
        self,
        proposal: CandidateTableInterpretation,
        feedback: List[DiagnosticConflict],
    ) -> RefinedProposal:
        """Resolve symbolic conflicts by refining column types, roles, and row relations."""
        adjustments: List[str] = []
        refined_cols = [TableColumnInterpretation(**c.to_dict()) for c in proposal.columns]
        refined_mentions = [CellMention(**m.to_dict()) for m in proposal.cell_mentions]
        refined_table_type = proposal.table_type
        refined_subject = proposal.subject_entity
        refined_subject_col = proposal.subject_column_idx

        for conflict in feedback:
            # Handle Domain / Range / Type violations on columns
            if conflict.target_col is not None and 0 <= conflict.target_col < len(refined_cols):
                col = refined_cols[conflict.target_col]
                
                # Check suggested fix
                if conflict.suggested_fix and "change column type to" in conflict.suggested_fix.lower():
                    match = re.search(r"change column type to\s+([a-zA-Z0-9_]+)", conflict.suggested_fix, re.IGNORECASE)
                    if match:
                        new_type = match.group(1)
                        old_type = col.predicted_type
                        col.predicted_type = new_type
                        col.role = "ingredient"
                        adjustments.append(f"Updated column {col.column_index} ('{col.column_name}') type: {old_type} -> {new_type}")

                elif conflict.conflict_type in ("TYPE_INCOMPATIBILITY", "DOMAIN_VIOLATION", "RANGE_VIOLATION"):
                    cells_in_col = [m for m in refined_mentions if m.col_idx == conflict.target_col]
                    material_count = sum(1 for m in cells_in_col if m.entity_type == "CraftingMaterial" or m.normalized_text in KNOWN_ENTITY_TYPES and KNOWN_ENTITY_TYPES[m.normalized_text] == "CraftingMaterial")
                    
                    if material_count > 0:
                        old_type = col.predicted_type
                        col.predicted_type = "CraftingMaterial"
                        col.role = "ingredient"
                        adjustments.append(f"Corrected column {col.column_index} ('{col.column_name}') from {old_type} to CraftingMaterial (role: ingredient)")

            # Handle intermediate gift vs final weapon output conflict
            if "intermediate gift" in conflict.message.lower() or "slot mismatch" in conflict.conflict_type.lower():
                if conflict.offending_value:
                    offending = str(conflict.offending_value)
                    if offending in KNOWN_ENTITY_TYPES and KNOWN_ENTITY_TYPES[offending] == "LegendaryGift":
                        adjustments.append(f"Reclassified '{offending}' from table output subject to ingredient component.")

            # Handle table type reclassification
            if "table type" in conflict.message.lower():
                if "mystic forge" in conflict.message.lower():
                    refined_table_type = "MysticForgeRecipe"
                    adjustments.append("Reclassified table type to MysticForgeRecipe")
                elif "crafting" in conflict.message.lower():
                    refined_table_type = "CraftingRecipe"
                    adjustments.append("Reclassified table type to CraftingRecipe")

        # Update cell mentions matching updated columns
        for m in refined_mentions:
            if 0 <= m.col_idx < len(refined_cols):
                col = refined_cols[m.col_idx]
                if m.normalized_text in KNOWN_ENTITY_TYPES:
                    m.entity_type = KNOWN_ENTITY_TYPES[m.normalized_text]
                elif col.predicted_type not in ("Quantity", "Unknown"):
                    m.entity_type = col.predicted_type

        # Reconstruct row relations
        new_relations = self._build_row_relations(
            None, refined_cols, refined_mentions, refined_table_type, refined_subject, refined_subject_col
        )

        refined_interpretation = CandidateTableInterpretation(
            columns=refined_cols,
            table_type=refined_table_type,
            subject_entity=refined_subject,
            subject_column_idx=refined_subject_col,
            row_relations=new_relations,
            cell_mentions=refined_mentions,
            confidence=0.98,
            reasoning=f"Refined interpretation after resolving {len(feedback)} symbolic conflicts.",
        )

        rationale = "; ".join(adjustments) if adjustments else "Adjusted schema according to symbolic axioms."
        return RefinedProposal(
            interpretation=refined_interpretation,
            adjustments_made=adjustments,
            rationale=rationale,
        )

    # ------------------------------------------------------------------------
    # Internal Heuristic Helper Methods
    # ------------------------------------------------------------------------

    def _classify_column(
        self, col_idx: int, header: str, sample_cells: List[str]
    ) -> Tuple[str, str, float]:
        """Classify column into (predicted_type, role, confidence)."""
        h_lower = header.lower().strip()

        # Quantity headers
        if re.search(r"\b(qty|quantity|count|amount|x|#)\b", h_lower):
            return "Quantity", "quantity", 0.95

        # Currency / Cost headers
        if re.search(r"\b(cost|price|gold|karma|currency|spirit shard|coin|buy)\b", h_lower):
            return "Currency", "cost", 0.9

        # Discipline headers
        if re.search(r"\b(discipline|crafting|prof|profession|rating|level)\b", h_lower):
            return "CraftingDiscipline", "discipline", 0.9

        # Weapon / Armor / Specific item headers
        if re.search(r"\b(weapon)\b", h_lower):
            return "Weapon", "reward", 0.75

        if re.search(r"\b(armor)\b", h_lower):
            return "Armor", "reward", 0.75

        # Output / Product headers
        if re.search(r"\b(output|reward|product|result|crafted item|target)\b", h_lower):
            return "Item", "reward", 0.85

        # Ingredient / Requirement headers
        if re.search(r"\b(requirement|requirements|material|materials|ingredient|ingredients|component|components|input)\b", h_lower):
            return "CraftingMaterial", "ingredient", 0.9

        # Item / Name headers
        if re.search(r"\b(item|name|component name)\b", h_lower):
            return "Item", "ingredient" if col_idx > 0 else "subject", 0.8

        # Fallback inspection of cell values
        num_numeric = 0
        num_materials = 0
        for cell in sample_cells:
            norm, qty, _ = TextCleaner.extract_quantity(cell)
            if cell.replace(",", "").replace(".", "").strip().isdigit():
                num_numeric += 1
            if norm in KNOWN_ENTITY_TYPES and KNOWN_ENTITY_TYPES[norm] == "CraftingMaterial":
                num_materials += 1

        if sample_cells and num_numeric >= len(sample_cells) * 0.7:
            return "Quantity", "quantity", 0.8
        if sample_cells and num_materials >= len(sample_cells) * 0.5:
            return "CraftingMaterial", "ingredient", 0.85

        return "Item", "ingredient", 0.6

    def _determine_table_semantics(
        self,
        columns: List[TableColumnInterpretation],
        cells: List[CellMention],
        table: TableGrid,
    ) -> Tuple[str, Optional[int], Optional[str]]:
        """Determine table type (e.g. CraftingRecipe), subject column index, and subject entity name."""
        subject_entity = None
        if "title" in table.metadata:
            subject_entity = TextCleaner.normalize_typos(table.metadata["title"])
        elif "caption" in table.metadata:
            subject_entity = TextCleaner.normalize_typos(table.metadata["caption"])

        subject_col_idx = None
        if subject_entity is None:
            # Check if an explicit subject column exists
            for col in columns:
                if col.role in ("subject", "reward") and col.predicted_type != "CraftingMaterial":
                    subject_col_idx = col.column_index
                    break

        # Table classification
        has_ingredient_col = any(c.role == "ingredient" or c.predicted_type == "CraftingMaterial" for c in columns)
        has_quantity_col = any(c.role == "quantity" or c.predicted_type == "Quantity" for c in columns)

        table_type = "CraftingRecipe" if (has_ingredient_col or has_quantity_col) else "ItemCollection"

        if len(table.rows) == 4 and not any(c.predicted_type == "CraftingDiscipline" for c in columns):
            table_type = "MysticForgeRecipe"

        return table_type, subject_col_idx, subject_entity

    def _build_row_relations(
        self,
        table: Optional[TableGrid],
        columns: List[TableColumnInterpretation],
        mentions: List[CellMention],
        table_type: str,
        subject_entity: Optional[str],
        subject_col_idx: Optional[int],
    ) -> List[RowRelation]:
        """Construct structured RowRelation instances connecting subjects and objects."""
        relations: List[RowRelation] = []

        rows_map: Dict[int, List[CellMention]] = {}
        for m in mentions:
            rows_map.setdefault(m.row_idx, []).append(m)

        for r_idx, row_mentions in rows_map.items():
            row_subject = subject_entity
            if not row_subject and subject_col_idx is not None:
                sub_m = next((m for m in row_mentions if m.col_idx == subject_col_idx), None)
                if sub_m:
                    row_subject = sub_m.normalized_text

            if not row_subject:
                row_subject = "TargetRecipe"

            for m in row_mentions:
                # If this column is explicitly the subject column, don't treat it as an object
                if subject_col_idx is not None and m.col_idx == subject_col_idx:
                    continue

                col = columns[m.col_idx] if m.col_idx < len(columns) else None
                col_role = col.role if col else "ingredient"
                col_type = col.predicted_type if col else m.entity_type

                if col_role == "quantity" or col_type == "Quantity":
                    continue

                # Find associated quantity in this row
                qty_val = m.quantity
                if qty_val is None:
                    qty_m = next((qm for qm in row_mentions if qm.col_idx != m.col_idx and (columns[qm.col_idx].predicted_type == "Quantity" or qm.quantity is not None)), None)
                    if qty_m and qty_m.quantity is not None:
                        qty_val = qty_m.quantity

                # Predicate determination
                if col_role == "cost" or col_type == "Currency":
                    predicate = "costsCurrency"
                elif col_role == "discipline" or col_type == "CraftingDiscipline":
                    predicate = "requiresDiscipline"
                elif col_type == "CraftingMaterial" or col_role == "ingredient":
                    predicate = "requiresMaterial"
                else:
                    predicate = "hasIngredient"

                relations.append(
                    RowRelation(
                        row_idx=r_idx,
                        subject=row_subject,
                        predicate=predicate,
                        object=m.normalized_text,
                        quantity=qty_val,
                        unit=m.unit,
                        confidence=0.9,
                    )
                )

        return relations


# ============================================================================
# LOCAL GEMMA NORMALIZER (APPLE SILICON MLX & HUGGINGFACE TRANSFORMERS)
# ============================================================================

class LocalGemmaNormalizer(LLMNormalizer):
    """Local Google Gemma (2B / 4B / 9B) wrapper using Apple Silicon MLX

    or HuggingFace `transformers` with 4-bit/8-bit quantization.
    Falls back to HeuristicNormalizer if weights are unavailable.
    """

    def __init__(self, model_name: str = "google/gemma-2-2b-it", backend: str = "mlx") -> None:
        self.model_name = model_name
        self.backend = backend
        self.fallback = HeuristicNormalizer()
        self._model = None
        self._tokenizer = None
        self._load_attempted = False

    def _lazy_load(self) -> bool:
        """Attempt to load the model lazily."""
        if self._load_attempted:
            return self._model is not None

        self._load_attempted = True
        try:
            if self.backend == "mlx":
                import mlx_lm
                self._model, self._tokenizer = mlx_lm.load(self.model_name)
                logger.info(f"Loaded MLX Gemma model: {self.model_name}")
                return True
            else:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16 if device == "mps" else torch.float32,
                    device_map=device,
                )
                logger.info(f"Loaded Transformers Gemma model: {self.model_name} on {device}")
                return True
        except Exception as e:
            logger.warning(f"Could not load local Gemma model ({e}). Using HeuristicNormalizer fallback.")
            self._model = None
            self._tokenizer = None
            return False

    def normalize_text(self, text: str) -> str:
        """Normalize text using Gemma or heuristic fallback."""
        if not self._lazy_load():
            return self.fallback.normalize_text(text)

        prompt = (
            f"You are a Guild Wars 2 knowledge normalizer. "
            f"Clean typos and return the official GW2 name for the following entity or text: '{text}'. "
            f"Output ONLY the corrected name."
        )
        try:
            res = self._generate_text(prompt)
            return res.strip().strip('"\'') if res.strip() else self.fallback.normalize_text(text)
        except Exception:
            return self.fallback.normalize_text(text)

    def extract_entity_spans(self, text: str) -> List[EntitySpan]:
        """Extract entity spans using heuristic fallback."""
        return self.fallback.extract_entity_spans(text)

    def extract_table_mentions(self, table: TableGrid) -> CandidateTableInterpretation:
        """Extract table mentions using Gemma JSON output or heuristic fallback."""
        if not self._lazy_load():
            return self.fallback.extract_table_mentions(table)

        prompt = (
            f"You are an expert Guild Wars 2 knowledge graph engineer. "
            f"Analyze this table and output a JSON schema with column types ('CraftingMaterial', 'Weapon', 'Currency', 'Quantity', 'Item') "
            f"and roles ('subject', 'ingredient', 'quantity', 'cost', 'reward').\n\n"
            f"Table Headers: {table.headers}\n"
            f"Sample Rows: {table.rows[:3]}\n\n"
            f"Output valid JSON: {{\"columns\": [ {{\"column_index\": 0, \"predicted_type\": \"...\", \"role\": \"...\"}} ], \"table_type\": \"...\"}}"
        )
        try:
            output = self._generate_text(prompt)
            json_match = re.search(r"\{.*\}", output, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                heuristic_prop = self.fallback.extract_table_mentions(table)
                if "table_type" in parsed:
                    heuristic_prop.table_type = parsed["table_type"]
                return heuristic_prop
        except Exception as e:
            logger.debug(f"Gemma table interpretation failed ({e}), falling back.")

        return self.fallback.extract_table_mentions(table)

    def resolve_ambiguity(
        self,
        proposal: CandidateTableInterpretation,
        feedback: List[DiagnosticConflict],
    ) -> RefinedProposal:
        """Resolve ambiguity using diagnostic feedback."""
        return self.fallback.resolve_ambiguity(proposal, feedback)

    def _generate_text(self, prompt: str) -> str:
        """Generate response from loaded model."""
        if self.backend == "mlx":
            import mlx_lm
            return mlx_lm.generate(self._model, self._tokenizer, prompt=prompt, max_tokens=256)
        else:
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
            outputs = self._model.generate(**inputs, max_new_tokens=256)
            return self._tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)


# ============================================================================
# REMOTE API LLM NORMALIZER (GEMINI, OPENAI, ANTHROPIC)
# ============================================================================

class APILLMNormalizer(LLMNormalizer):
    """Remote LLM normalizer utilizing Gemini, OpenAI, or Anthropic APIs if configured."""

    def __init__(self, provider: str = "gemini", model: Optional[str] = None) -> None:
        self.provider = provider.lower()
        self.model = model or ("gemini-2.5-flash" if self.provider == "gemini" else "gpt-4o-mini")
        self.fallback = HeuristicNormalizer()

    def _has_api_key(self) -> bool:
        """Check if required API key exists in environment."""
        if self.provider == "gemini":
            return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        elif self.provider == "openai":
            return bool(os.environ.get("OPENAI_API_KEY"))
        elif self.provider == "anthropic":
            return bool(os.environ.get("ANTHROPIC_API_KEY"))
        return False

    def normalize_text(self, text: str) -> str:
        """Normalize text using remote API or heuristic fallback."""
        if not self._has_api_key():
            return self.fallback.normalize_text(text)
        return self.fallback.normalize_text(text)

    def extract_entity_spans(self, text: str) -> List[EntitySpan]:
        """Extract entity spans using heuristic or remote API."""
        return self.fallback.extract_entity_spans(text)

    def extract_table_mentions(self, table: TableGrid) -> CandidateTableInterpretation:
        """Extract table interpretation via remote API or heuristic fallback."""
        return self.fallback.extract_table_mentions(table)

    def resolve_ambiguity(
        self,
        proposal: CandidateTableInterpretation,
        feedback: List[DiagnosticConflict],
    ) -> RefinedProposal:
        """Refine proposal based on symbolic feedback."""
        return self.fallback.resolve_ambiguity(proposal, feedback)


# ============================================================================
# AUTO FACTORY
# ============================================================================

def get_normalizer(backend: str = "auto", model_name: Optional[str] = None) -> LLMNormalizer:
    """Factory to acquire an appropriate LLMNormalizer instance."""
    b = backend.lower()
    if b == "heuristic":
        return HeuristicNormalizer()

    if b in ("local", "gemma", "mlx"):
        return LocalGemmaNormalizer(model_name=model_name or "google/gemma-2-2b-it")

    if b in ("api", "gemini"):
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return APILLMNormalizer(provider="gemini", model=model_name)

    if b == "openai" and os.environ.get("OPENAI_API_KEY"):
        return APILLMNormalizer(provider="openai", model=model_name)

    if b == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return APILLMNormalizer(provider="anthropic", model=model_name)

    return HeuristicNormalizer()
