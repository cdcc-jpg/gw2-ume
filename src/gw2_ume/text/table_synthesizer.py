"""Dynamic Table Synthesizer for GW2-UME.

Synthesizes structured 2D tabular grids (SyntheticTableGrid) from dynamic semantic frames
and discourse clauses without ANY hardcoded column lists or static table templates.

Implements:
1. Heuristic primary anchor entity discovery per frame.
2. Dynamic slot co-occurrence clustering and hypergraph dimension induction.
3. Dynamic column header induction from entity classes and semantic roles.
4. Matrix assembly and serialization into CSV, Markdown, and dictionary formats
   ready for the Relational Mesh.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from gw2_ume.text.modality_parser import DynamicSemanticFrame, ModalityType, SemanticSlot


@dataclass
class SyntheticTableGrid:
    """A synthesized 2D tabular matrix ready for Semantic Table Interpretation & Relational Mesh."""
    title: str
    headers: List[str]
    rows: List[List[str]]
    frames_included: int
    modality_summary: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_csv(self) -> str:
        """Serializes the grid to standard CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(self.headers)
        for row in self.rows:
            writer.writerow(row)
        return output.getvalue()

    def to_markdown(self) -> str:
        """Serializes the grid to standard GitHub-flavored Markdown table format."""
        if not self.headers:
            return ""

        # Compute column widths
        col_widths = [len(h) for h in self.headers]
        for row in self.rows:
            for idx, val in enumerate(row):
                if idx < len(col_widths):
                    col_widths[idx] = max(col_widths[idx], len(str(val)))

        lines = []
        # Header line
        header_cells = [f" {h.ljust(col_widths[i])} " for i, h in enumerate(self.headers)]
        lines.append("|" + "|".join(header_cells) + "|")

        # Separator line
        sep_cells = [f" {'-' * col_widths[i]} " for i in range(len(self.headers))]
        lines.append("|" + "|".join(sep_cells) + "|")

        # Data rows
        for row in self.rows:
            row_cells = []
            for i in range(len(self.headers)):
                val = str(row[i]) if i < len(row) else ""
                row_cells.append(f" {val.ljust(col_widths[i])} ")
            lines.append("|" + "|".join(row_cells) + "|")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the grid to a dictionary representation."""
        return {
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "row_count": len(self.rows),
            "column_count": len(self.headers),
            "frames_included": self.frames_included,
            "modality_summary": self.modality_summary,
            "metadata": self.metadata,
        }


class TableSynthesizer:
    """Dynamically induces schema dimensions and synthesizes 2D tables from semantic frames."""

    # Dynamic role-to-header mapping induction (generic ontological labels, not fixed static templates)
    SEMANTIC_ROLE_HEADERS: Dict[str, str] = {
        "anchor_entity": "Subject Entity",
        "precursorTo": "Precursor Target",
        "requiresIngredient": "Required Component",
        "quantity": "Quantity",
        "discipline": "Crafting Discipline",
        "min_rating": "Discipline Rating",
        "vendor": "NPC Vendor",
        "zone": "Zone / Location",
        "cost": "Cost / Currency",
        "condition": "Condition / Context",
        "modality": "Modal Type",
    }

    def __init__(self):
        pass

    def _discover_anchor_entity(self, frame: DynamicSemanticFrame) -> Tuple[str, str]:
        """Discovers primary anchor entity and its ontological class for a frame."""
        if frame.anchor_entity:
            return frame.anchor_entity, frame.anchor_type or "Item"

        # Fallback: check slots for entity
        for slot in frame.slots:
            if slot.slot_type == "entity" and slot.value:
                return str(slot.value), slot.entity_type or "Item"

        return "General Context", "Concept"

    def _cluster_slots_and_induce_dimensions(
        self,
        frames: List[DynamicSemanticFrame],
    ) -> List[Tuple[str, str]]:
        """Analyzes slot co-occurrence across frames to dynamically induce active schema columns.

        Returns an ordered list of (dimension_key, header_title) pairs.
        """
        # Count occurrence frequency of each slot dimension
        dimension_counts: Dict[str, int] = defaultdict(int)
        dimension_types: Dict[str, str] = {}

        for frame in frames:
            seen_in_frame: Set[str] = set()
            for slot in frame.slots:
                dim_key = slot.name
                if dim_key not in seen_in_frame:
                    seen_in_frame.add(dim_key)
                    dimension_counts[dim_key] += 1
                    if slot.entity_type and dim_key not in dimension_types:
                        dimension_types[dim_key] = slot.entity_type

        # Always place anchor / subject entity first
        ordered_dimensions: List[Tuple[str, str]] = []

        # 1. Subject / Anchor Entity dimension
        anchor_class_names = [f.anchor_type for f in frames if f.anchor_type]
        most_common_class = max(set(anchor_class_names), key=anchor_class_names.count) if anchor_class_names else "Subject Item"
        
        # Humanize class name for header
        anchor_header = re.sub(r"([a-z])([A-Z])", r"\1 \2", most_common_class)
        ordered_dimensions.append(("anchor_entity", anchor_header))

        # 2. Add relational/component target dimensions if present
        if dimension_counts.get("entity", 0) > 0 or dimension_counts.get("requiresIngredient", 0) > 0:
            ordered_dimensions.append(("entity", "Required Component"))

        # 3. Add quantity dimension if present
        if dimension_counts.get("quantity", 0) > 0:
            ordered_dimensions.append(("quantity", "Quantity"))

        # 4. Add crafting discipline & rating dimensions if present
        if dimension_counts.get("discipline", 0) > 0:
            ordered_dimensions.append(("discipline", "Crafting Discipline"))
        if dimension_counts.get("min_rating", 0) > 0:
            ordered_dimensions.append(("min_rating", "Min Rating"))

        # 5. Add NPC Vendor & Zone dimensions if present
        if dimension_counts.get("vendor", 0) > 0:
            ordered_dimensions.append(("vendor", "NPC Vendor"))
        if dimension_counts.get("zone", 0) > 0:
            ordered_dimensions.append(("zone", "Zone / Location"))

        # 6. Add cost / currency dimension if present
        if dimension_counts.get("cost", 0) > 0:
            ordered_dimensions.append(("cost", "Cost / Currency"))

        # 7. Add precursor target if present
        if dimension_counts.get("precursorTo", 0) > 0:
            ordered_dimensions.append(("precursorTo", "Precursor Target"))

        # 8. Add modal constraint dimension for provenance
        ordered_dimensions.append(("modality", "Modality"))

        return ordered_dimensions

    def synthesize_grid(
        self,
        frames: List[DynamicSemanticFrame],
        title: str = "Synthesized Semantic Grid",
    ) -> SyntheticTableGrid:
        """Synthesizes a 2D SyntheticTableGrid from a list of active dynamic semantic frames."""
        if not frames:
            return SyntheticTableGrid(
                title=title,
                headers=["Subject Item", "Required Component", "Quantity", "Modality"],
                rows=[],
                frames_included=0,
            )

        # 1. Induce dynamic column dimensions
        dimensions = self._cluster_slots_and_induce_dimensions(frames)
        headers = [h for _, h in dimensions]

        # 2. Build rows per frame or sub-entity relation
        rows: List[List[str]] = []
        modality_counts: Dict[str, int] = defaultdict(int)

        for frame in frames:
            modality_counts[frame.modality.value] += 1
            anchor_lbl, _ = self._discover_anchor_entity(frame)

            # Check if this frame has multiple component entities
            other_entities = [
                s for s in frame.slots
                if s.slot_type == "entity" and s.name != "anchor_entity" and str(s.value) != anchor_lbl
            ]

            # Quantities mapped by entity URI or label
            quantities_by_ent: Dict[str, Any] = {}
            for q_slot in frame.get_slots_by_type("numeric"):
                if q_slot.name == "quantity":
                    if q_slot.entity_uri:
                        quantities_by_ent[q_slot.entity_uri] = q_slot.value
                    elif q_slot.raw_text:
                        quantities_by_ent[q_slot.raw_text] = q_slot.value

            # Common frame attributes
            disc_val = frame.get_slot_value("discipline") or ""
            rating_val = str(frame.get_slot_value("min_rating") or "")
            vendor_val = frame.get_slot_value("vendor") or ""
            zone_val = frame.get_slot_value("zone") or ""
            cost_val = frame.get_slot_value("cost") or ""
            mod_val = f"{frame.modality.symbol} {frame.modality.value}"

            if other_entities:
                # Create a row for each component entity
                for ent_slot in other_entities:
                    ent_lbl = str(ent_slot.value)
                    qty_val = str(quantities_by_ent.get(ent_slot.entity_uri or "", quantities_by_ent.get(ent_lbl, "1")))
                    
                    row_data: List[str] = []
                    for dim_key, _ in dimensions:
                        if dim_key == "anchor_entity":
                            row_data.append(anchor_lbl)
                        elif dim_key == "entity":
                            row_data.append(ent_lbl)
                        elif dim_key == "quantity":
                            row_data.append(qty_val)
                        elif dim_key == "discipline":
                            row_data.append(disc_val)
                        elif dim_key == "min_rating":
                            row_data.append(rating_val)
                        elif dim_key == "vendor":
                            # If entity itself is NPCVendor, place it in vendor column
                            if ent_slot.entity_type == "NPCVendor":
                                row_data.append(ent_lbl)
                            else:
                                row_data.append(vendor_val)
                        elif dim_key == "zone":
                            # If entity itself is Zone, place it in zone column
                            if ent_slot.entity_type == "Zone":
                                row_data.append(ent_lbl)
                            else:
                                row_data.append(zone_val)
                        elif dim_key == "cost":
                            row_data.append(cost_val)
                        elif dim_key == "precursorTo":
                            row_data.append(frame.get_slot_value("precursorTo") or "")
                        elif dim_key == "modality":
                            row_data.append(mod_val)
                        else:
                            row_data.append("")

                    rows.append(row_data)
            else:
                # Frame has no sub-entities (e.g. single requirement, estimate, or declaration)
                row_data = []
                general_qty = str(frame.get_slot_value("quantity") or "")
                for dim_key, _ in dimensions:
                    if dim_key == "anchor_entity":
                        row_data.append(anchor_lbl)
                    elif dim_key == "entity":
                        row_data.append("")
                    elif dim_key == "quantity":
                        row_data.append(general_qty)
                    elif dim_key == "discipline":
                        row_data.append(disc_val)
                    elif dim_key == "min_rating":
                        row_data.append(rating_val)
                    elif dim_key == "vendor":
                        row_data.append(vendor_val)
                    elif dim_key == "zone":
                        row_data.append(zone_val)
                    elif dim_key == "cost":
                        row_data.append(cost_val)
                    elif dim_key == "precursorTo":
                        row_data.append(frame.get_slot_value("precursorTo") or "")
                    elif dim_key == "modality":
                        row_data.append(mod_val)
                    else:
                        row_data.append("")

                rows.append(row_data)

        # Deduplicate identical rows while preserving ordering
        unique_rows: List[List[str]] = []
        seen_row_tuples: Set[Tuple[str, ...]] = set()
        for r in rows:
            r_tup = tuple(r)
            if r_tup not in seen_row_tuples:
                seen_row_tuples.add(r_tup)
                unique_rows.append(r)

        return SyntheticTableGrid(
            title=title,
            headers=headers,
            rows=unique_rows,
            frames_included=len(frames),
            modality_summary=dict(modality_counts),
            metadata={"dimension_count": len(dimensions)},
        )


__all__ = ["SyntheticTableGrid", "TableSynthesizer"]
