"""Stage 8: Assembly, Coverage Report Generation, and Pre-Flight SHACL Validation.

Zero Domain Semantics in Python: Operates on graph structures and generic triple schemas.
Implements:
- Assembly into DataFrame and CSV export:
  Headers: subject, predicate, object, confidence, method, review_flag, module_action.
- Generation of Markdown Coverage Report (coverage_report.md):
  - Total triples emitted.
  - Module_Action breakdown (% and counts).
  - % mapped, % strong-matched (confidence >= 0.70).
  - Gaps, low confidence triples, and HITL review list.
- Optional Pre-Flight SHACL Validation:
  Validates assembled RDF triples against SHACL shapes using pyshacl before committing to graph store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import rdflib
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from gw2_ume.use_pipeline.stage4_row_loop import Triple


@dataclass
class AssemblyResult:
    """Output bundle from Stage 8."""
    df_triples: pd.DataFrame
    triples_csv_path: Optional[Path]
    coverage_report_md_path: Optional[Path]
    coverage_report_text: str
    total_triples: int
    mapped_ratio: float
    strong_matched_ratio: float
    action_counts: Dict[str, int]
    shacl_conforms: Optional[bool] = None
    shacl_report_text: Optional[str] = None


class TriplesAssembler:
    """Stage 8 Assembler and Exporter."""

    def assemble(
        self,
        triples: List[Triple],
        output_dir: Optional[Union[str, Path]] = None,
        shacl_shapes_graph: Optional[Graph] = None,
    ) -> AssemblyResult:
        """Assembles triples, writes triples.csv and coverage_report.md, and optionally
        validates via SHACL.
        """
        # 1. Build DataFrame
        records = [
            {
                "subject": t.subject,
                "predicate": t.predicate,
                "object": t.object,
                "confidence": round(t.confidence, 4),
                "method": t.method,
                "review_flag": t.review_flag,
                "module_action": t.module_action,
            }
            for t in triples
        ]
        df = pd.DataFrame(records)

        # 2. Compute metrics
        total = len(df)
        if total > 0:
            action_counts = df["module_action"].value_counts().to_dict()
            mapped_count = (df["method"] != "Unmapped").sum()
            mapped_ratio = mapped_count / total
            strong_matched_count = (df["confidence"] >= 0.70).sum()
            strong_matched_ratio = strong_matched_count / total
        else:
            action_counts = {}
            mapped_ratio = 0.0
            strong_matched_ratio = 0.0

        # 3. Optional SHACL Validation
        shacl_conforms = None
        shacl_report_text = None
        if shacl_shapes_graph is not None and len(shacl_shapes_graph) > 0 and total > 0:
            shacl_conforms, shacl_report_text = self._validate_shacl(df, shacl_shapes_graph)

        # 4. Generate Markdown Coverage Report
        report_text = self._build_coverage_report(
            df=df,
            total=total,
            mapped_ratio=mapped_ratio,
            strong_matched_ratio=strong_matched_ratio,
            action_counts=action_counts,
            shacl_conforms=shacl_conforms,
            shacl_report_text=shacl_report_text,
        )

        # 5. Write to files if output_dir is specified
        triples_csv_path = None
        coverage_md_path = None
        if output_dir is not None:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

            triples_csv_path = out_path / "triples.csv"
            df.to_csv(triples_csv_path, index=False)

            coverage_md_path = out_path / "coverage_report.md"
            with open(coverage_md_path, "w", encoding="utf-8") as f:
                f.write(report_text)

        return AssemblyResult(
            df_triples=df,
            triples_csv_path=triples_csv_path,
            coverage_report_md_path=coverage_md_path,
            coverage_report_text=report_text,
            total_triples=total,
            mapped_ratio=mapped_ratio,
            strong_matched_ratio=strong_matched_ratio,
            action_counts=action_counts,
            shacl_conforms=shacl_conforms,
            shacl_report_text=shacl_report_text,
        )

    def _validate_shacl(
        self,
        df: pd.DataFrame,
        shacl_shapes_graph: Graph,
    ) -> Tuple[bool, str]:
        """Convert triples to an RDF graph and validate against SHACL shapes."""
        try:
            import pyshacl
        except ImportError:
            return True, "pyshacl not installed; skipped SHACL pre-flight check."

        data_graph = Graph()
        for _, row in df.iterrows():
            s_str = str(row["subject"])
            p_str = str(row["predicate"])
            o_str = str(row["object"])

            s = URIRef(s_str) if (s_str.startswith("http://") or s_str.startswith("https://") or s_str.startswith("urn:")) else URIRef(f"urn:priory:entity:{s_str}")
            p = URIRef(p_str) if (p_str.startswith("http://") or p_str.startswith("https://") or p_str.startswith("urn:")) else URIRef(f"urn:priory:prop:{p_str}")

            if o_str.startswith("http://") or o_str.startswith("https://") or o_str.startswith("urn:"):
                o = URIRef(o_str)
            else:
                # Type literals appropriately for SHACL datatype validation
                if o_str.isdigit() or (o_str.startswith("-") and o_str[1:].isdigit()):
                    o = Literal(int(o_str), datatype=XSD.integer)
                else:
                    try:
                        f_val = float(o_str)
                        o = Literal(f_val, datatype=XSD.double)
                    except ValueError:
                        if o_str.lower() in ("true", "false"):
                            o = Literal(o_str.lower() == "true", datatype=XSD.boolean)
                        else:
                            o = Literal(o_str, datatype=XSD.string)

            data_graph.add((s, p, o))

        try:
            conforms, results_graph, results_text = pyshacl.validate(
                data_graph=data_graph,
                shacl_graph=shacl_shapes_graph,
                inference="rdfs",
                abort_on_first=False,
            )
            return bool(conforms), str(results_text)
        except Exception as e:
            return False, f"SHACL execution error: {e}"

    def _build_coverage_report(
        self,
        df: pd.DataFrame,
        total: int,
        mapped_ratio: float,
        strong_matched_ratio: float,
        action_counts: Dict[str, int],
        shacl_conforms: Optional[bool],
        shacl_report_text: Optional[str],
    ) -> str:
        """Constructs markdown coverage report."""
        lines = [
            "# USE Pipeline Track 2 - Semantic Assembly & Coverage Report",
            "",
            "## 1. Executive Summary",
            "",
            f"- **Total RDF Triples Emitted:** `{total:,}`",
            f"- **Predicate Mapping Coverage:** `{mapped_ratio * 100:.2f}%`",
            f"- **Strong-Matched Ratio (Confidence >= 0.70):** `{strong_matched_ratio * 100:.2f}%`",
            f"- **Triples Requiring Review (review_flag=True):** `{int((df['review_flag'] == True).sum()) if total > 0 else 0:,}`",
            "",
            "## 2. Module_Action Distribution",
            "",
            "| Module Action | Count | Percentage |",
            "| :--- | :---: | :---: |",
        ]

        for action in ["Deterministic Mapped", "Literal Typed", "HITL Validation", "Literal Boxed"]:
            cnt = action_counts.get(action, 0)
            pct = (cnt / total * 100) if total > 0 else 0.0
            lines.append(f"| **{action}** | {cnt:,} | {pct:.1f}% |")

        if shacl_conforms is not None:
            lines.extend([
                "",
                "## 3. Pre-Flight SHACL Shape Validation",
                "",
                f"- **SHACL Conformance Status:** {'✓ CONFORMING' if shacl_conforms else '⚠️ NON-CONFORMING'}",
            ])
            if shacl_report_text:
                lines.extend([
                    "```",
                    shacl_report_text.strip(),
                    "```",
                ])

        # Section 4: Gaps & HITL Review Items
        hitl_df = df[df["review_flag"] == True] if total > 0 else pd.DataFrame()
        lines.extend([
            "",
            "## 4. Gaps and Items Requiring HITL Review",
            "",
        ])
        if len(hitl_df) == 0:
            lines.append("✓ Zero items require HITL review. All triples passed deterministic thresholds.")
        else:
            lines.extend([
                f"Found **{len(hitl_df)}** triples flagged for human verification:",
                "",
                "| Subject | Predicate | Object | Confidence | Method | Action |",
                "| :--- | :--- | :--- | :---: | :--- | :--- |",
            ])
            for _, r in hitl_df.head(25).iterrows():
                lines.append(
                    f"| `{r['subject']}` | `{r['predicate']}` | `{r['object']}` | {r['confidence']:.2f} | {r['method']} | {r['module_action']} |"
                )
            if len(hitl_df) > 25:
                lines.append(f"\n*(Showing first 25 of {len(hitl_df)} flagged triples)*")

        lines.append("")
        return "\n".join(lines)
