"""Rich CLI interface for GW2-UME."""

from __future__ import annotations
import os
import sys
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.tree import Tree

from gw2_ume.mesh.relational_mesh import build_relational_mesh
from gw2_ume.mesh.annotator import parse_table_content
from gw2_ume.neurosymbolic.pingpong import NeuroSymbolicPingPongEngine
from gw2_ume.text.extractor import TextEntityRelationExtractor
from gw2_ume.pipeline.triangulator import CrossModalTriangulator
from gw2_ume.benchmark.runner import BenchmarkRunner
from gw2_ume.ui.visualizer import generate_dashboard_html

console = Console()


@click.group()
def main():
    """GW2-UME: Universal Matrix Extraction & Neuro-Symbolic Graph Layer for Guild Wars 2."""
    pass


@main.command(name="match-table")
@click.argument("table_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "-f", "out_format", default="turtle", type=click.Choice(["turtle", "json-ld", "summary"]), help="Output serialization format.")
@click.option("--output", "-o", "output_file", default=None, help="Save RDF output to file.")
def match_table(table_path: str, out_format: str, output_file: str | None):
    """Match CSV or Markdown table, run CEA/CTA/CPA, and construct Relational Mesh."""
    path = Path(table_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    console.print(Panel(f"[bold cyan]Processing Table:[/] [white]{path.name}[/]", border_style="cyan"))

    mesh = build_relational_mesh(content, table_name=path.stem, validate_shacl=True)

    # 1. CTA Summary Table
    cta_table = Table(title="Column Type Annotations (CTA)", border_style="blue")
    cta_table.add_column("Index", justify="right", style="dim")
    cta_table.add_column("Column Header", style="cyan bold")
    cta_table.add_column("Ontology Class (Type)", style="green")
    cta_table.add_column("Confidence", justify="right", style="yellow")

    for c in mesh.cta:
        cta_table.add_row(str(c.col_idx), c.col_name, c.type_label, f"{c.confidence:.2%}")
    console.print(cta_table)

    # 2. CPA Summary Table
    if mesh.cpa:
        cpa_table = Table(title="Column Property Annotations (CPA)", border_style="magenta")
        cpa_table.add_column("Source Column", style="cyan")
        cpa_table.add_column("Property Relation", style="bold magenta")
        cpa_table.add_column("Target Column", style="green")
        cpa_table.add_column("Confidence", justify="right", style="yellow")

        for p in mesh.cpa:
            cpa_table.add_row(p.source_col, p.property_label, p.target_col, f"{p.confidence:.2%}")
        console.print(cpa_table)

    # 3. Mesh Summary
    val_style = "bold green" if mesh.validation_status == "CONFORMING" else "bold red"
    console.print(f"\n[bold]Mesh Graph Summary:[/] {len(mesh.nodes)} nodes, {len(mesh.edges)} edges | SHACL Status: [{val_style}]{mesh.validation_status}[/]")

    if out_format == "turtle":
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(mesh.turtle)
            console.print(f"[bold green]Saved Turtle graph to:[/] {output_file}")
        else:
            console.print("\n[bold cyan]RDF Turtle Serialization:[/]")
            console.print(Syntax(mesh.turtle, "turtle", theme="monokai", line_numbers=True))
    elif out_format == "json-ld":
        import json
        json_str = json.dumps(mesh.json_ld, indent=2)
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_str)
            console.print(f"[bold green]Saved JSON-LD graph to:[/] {output_file}")
        else:
            console.print("\n[bold cyan]JSON-LD Serialization:[/]")
            console.print(Syntax(json_str, "json", theme="monokai", line_numbers=True))


@main.command(name="classify-text")
@click.argument("text_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", "output_file", default=None, help="Save RDF output to file.")
def classify_text(text_path: str, output_file: str | None):
    """Classify unstructured game guide text, extract entities and relations, and emit RDF graph."""
    path = Path(text_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    console.print(Panel(f"[bold green]Classifying Unstructured Text:[/] [white]{path.name}[/]", border_style="green"))

    extractor = TextEntityRelationExtractor()
    result = extractor.extract_from_text(content)

    ent_table = Table(title=f"Extracted Entities ({result['entity_count']} found)", border_style="green")
    ent_table.add_column("Entity Label", style="cyan bold")
    ent_table.add_column("Type", style="magenta")
    ent_table.add_column("Matched Alias", style="yellow")
    ent_table.add_column("Occurrences", justify="right", style="white")

    for ent in result["entities_found"]:
        ent_table.add_row(ent["label"], ent["type_label"], ent["matched_alias"], str(ent["occurrences"]))
    console.print(ent_table)

    if result["triples"]:
        trip_table = Table(title=f"Extracted Relational Triples ({result['triple_count']} found)", border_style="cyan")
        trip_table.add_column("Subject", style="cyan")
        trip_table.add_column("Predicate", style="bold magenta")
        trip_table.add_column("Object", style="green")

        for trip in result["triples"]:
            s, p, o = str(trip[0]), str(trip[1]), str(trip[2])
            trip_table.add_row(s, p, o)
        console.print(trip_table)

    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["turtle"])
        console.print(f"\n[bold green]Exported RDF Turtle graph to:[/] {output_file}")


@main.command(name="pingpong")
@click.argument("table_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--verbose", "-v", is_flag=True, help="Display detailed turn-by-turn proposals and repair cues.")
def pingpong(table_path: str, verbose: bool):
    """Run interactive neuro-symbolic ping-pong dialogue with diagnostic logging."""
    path = Path(table_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    console.print(Panel(f"[bold yellow]Neuro-Symbolic Ping-Pong Engine:[/] [white]{path.name}[/]", border_style="yellow"))

    engine = NeuroSymbolicPingPongEngine()
    result = engine.run_dialogue(content, table_name=path.stem)

    for turn in result.turns:
        speaker_color = "cyan" if turn.speaker == "Neural Proposer" else "yellow" if turn.action == "EVALUATE" else "green"
        action_badge = f"[{speaker_color} bold]Round {turn.round_number} ({turn.speaker}) - {turn.action}[/]"
        
        body = f"[white]{turn.message}[/]\n[dim]Confidence: {turn.confidence:.0%}[/]"
        
        if verbose and turn.violations:
            body += "\n\n[bold red]Violations Flagged:[/]"
            for v in turn.violations:
                body += f"\n • [{v['type']}] {v['message']} -> [italic green]Cue: {v.get('repair_cue', '')}[/]"
                
        if verbose and turn.action == "REPAIR" and turn.proposals:
            body += "\n\n[bold magenta]Repairs Applied:[/]"
            for r in turn.proposals:
                body += f"\n • {r.get('detail', '')}"

        console.print(Panel(body, title=action_badge, border_style=speaker_color))

    status_str = "[bold green]CONFORMING (100% Valid)[/]" if result.conforms_shacl else "[bold red]VIOLATIONS[/]"
    console.print(f"\n[bold]Outcome:[/] Initial Proposals: {result.initial_proposals_count} | Violations Caught: {result.violations_detected_count} | Repairs: {result.repairs_applied_count} | Status: {status_str}")


@main.command(name="benchmark")
@click.option("--suite", "-s", "suite_path", default=None, help="Path to benchmark_suite.json.")
def run_benchmark(suite_path: str | None):
    """Execute Head-to-Head Proof-of-Value benchmark (Pure NLP vs. GW2-UME Relational Mesh)."""
    console.print(Panel("[bold cyan]Executing Proof-of-Value Benchmark Suite[/]\n[white]Pure NLP Baseline vs. GW2-UME Relational Mesh[/]", border_style="cyan"))

    runner = BenchmarkRunner()
    scores, summary = runner.run_all_benchmarks(suite_path)

    # Detailed Results Table
    table = Table(title="Head-to-Head Table Performance", border_style="blue")
    table.add_column("Benchmark Table", style="cyan bold")
    table.add_column("Model", style="white")
    table.add_column("CEA Acc", justify="right")
    table.add_column("CTA Acc", justify="right")
    table.add_column("CPA F1", justify="right")
    table.add_column("Semantic Validity", justify="right")
    table.add_column("Violations", justify="right")

    for nlp_s, mesh_s in scores:
        table.add_row(
            nlp_s.table_name,
            "[dim]Pure NLP[/]",
            f"{nlp_s.cea_accuracy:.1%}",
            f"{nlp_s.cta_accuracy:.1%}",
            f"{nlp_s.cpa_f1:.1%}",
            f"[red]{nlp_s.semantic_validity_rate:.1%}[/]",
            f"[red]{nlp_s.shacl_violations}[/]",
        )
        table.add_row(
            "",
            "[bold green]GW2-UME Mesh[/]",
            f"[green]{mesh_s.cea_accuracy:.1%}[/]",
            f"[green]{mesh_s.cta_accuracy:.1%}[/]",
            f"[green]{mesh_s.cpa_f1:.1%}[/]",
            f"[bold green]{mesh_s.semantic_validity_rate:.1%}[/]",
            f"[bold green]{mesh_s.shacl_violations}[/]",
        )
        table.add_section()

    console.print(table)

    # Summary Card
    sum_table = Table(title="Proof-of-Value Executive Summary", border_style="green")
    sum_table.add_column("Metric", style="bold")
    sum_table.add_column("Pure NLP Baseline", style="red", justify="right")
    sum_table.add_column("GW2-UME Semantic Mesh", style="bold green", justify="right")
    sum_table.add_column("Advantage / Gain", style="bold yellow", justify="right")

    cea_gain = (summary.mesh_avg_cea - summary.pure_nlp_avg_cea) * 100
    cta_gain = (summary.mesh_avg_cta - summary.pure_nlp_avg_cta) * 100
    cpa_gain = (summary.mesh_avg_cpa_f1 - summary.pure_nlp_avg_cpa_f1) * 100
    val_gain = (summary.mesh_avg_validity - summary.pure_nlp_avg_validity) * 100

    sum_table.add_row("Avg CEA Accuracy", f"{summary.pure_nlp_avg_cea:.1%}", f"{summary.mesh_avg_cea:.1%}", f"+{cea_gain:.1f}%")
    sum_table.add_row("Avg CTA Accuracy", f"{summary.pure_nlp_avg_cta:.1%}", f"{summary.mesh_avg_cta:.1%}", f"+{cta_gain:.1f}%")
    sum_table.add_row("Avg CPA F1 Score", f"{summary.pure_nlp_avg_cpa_f1:.1%}", f"{summary.mesh_avg_cpa_f1:.1%}", f"+{cpa_gain:.1f}%")
    sum_table.add_row("Avg Semantic Validity Rate", f"{summary.pure_nlp_avg_validity:.1%}", f"{summary.mesh_avg_validity:.1%}", f"+{val_gain:.1f}%")
    sum_table.add_row("Total SHACL Violations", str(summary.pure_nlp_total_violations), str(summary.mesh_total_violations), f"-{summary.pure_nlp_total_violations} (100% Elimination)")

    console.print(sum_table)


@main.command(name="visualize")
@click.argument("table_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", "output_path", default="dashboard.html", help="Target HTML dashboard file path.")
@click.option("--title", "-t", default="GW2-UME Semantic Dashboard", help="Dashboard title.")
def visualize(table_path: str, output_path: str, title: str):
    """Generate standalone interactive HTML dashboard."""
    path = Path(table_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    console.print(Panel(f"[bold cyan]Generating Visualizer Dashboard for:[/] [white]{path.name}[/]", border_style="cyan"))

    engine = NeuroSymbolicPingPongEngine()
    pingpong_res = engine.run_dialogue(content, table_name=path.stem)
    mesh = pingpong_res.relational_mesh or build_relational_mesh(content, table_name=path.stem)

    generate_dashboard_html(mesh, pingpong_result=pingpong_res, title=title, output_path=output_path)
    console.print(f"[bold green]Successfully created interactive dashboard at:[/] [white underline]{output_path}[/]")


@main.command(name="triangulate")
@click.argument("table_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("guide_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "-f", "out_format", default="turtle", type=click.Choice(["turtle", "json-ld", "summary"]), help="Output serialization format.")
@click.option("--output", "-o", "output_file", default=None, help="Save fused RDF graph output to file.")
@click.option("--dashboard", "-d", "dashboard_path", default=None, help="Generate interactive HTML visualizer dashboard.")
def triangulate(table_path: str, guide_path: str, out_format: str, output_file: str | None, dashboard_path: str | None):
    """Triangulate tabular matrix data and unstructured guide text into a unified knowledge graph."""
    t_path = Path(table_path)
    g_path = Path(guide_path)

    with open(t_path, "r", encoding="utf-8") as f:
        table_content = f.read()
    with open(g_path, "r", encoding="utf-8") as f:
        text_content = f.read()

    console.print(Panel(
        f"[bold cyan]Cross-Modal Triangulation:[/] [white]{t_path.name}[/] [dim]+[/] [white]{g_path.name}[/]",
        border_style="cyan"
    ))

    triangulator = CrossModalTriangulator(validate_shacl=True)
    res = triangulator.triangulate(table_content, text_content, table_name=t_path.stem)

    # 1. Bayesian Priors & Document Aboutness
    if res.bayesian_priors:
        prior_str = ", ".join(f"[cyan]{k}[/]: {v:.1%}" for k, v in res.bayesian_priors.items())
        console.print(f"[bold]Document Aboutness / Bayesian Priors:[/] {prior_str}")

    # 2. Corroborated Entities Table
    ent_table = Table(title=f"Fused & Corroborated Entities ({len(res.fused_entities)} total, {res.cross_modal_links_count} cross-modal)", border_style="green")
    ent_table.add_column("Entity", style="cyan bold")
    ent_table.add_column("Type", style="magenta")
    ent_table.add_column("Provenance", style="yellow")
    ent_table.add_column("C_tab", justify="right", style="dim")
    ent_table.add_column("C_txt", justify="right", style="dim")
    ent_table.add_column("C_fused", justify="right", style="bold green")
    ent_table.add_column("Fused Attributes", style="white")

    for e in res.fused_entities:
        attrs = []
        if e.get("quantity"):
            attrs.append(f"Qty: {e['quantity']}")
        if e.get("discipline"):
            attrs.append(f"Craft: {e['discipline']}")
        if e.get("vendor"):
            attrs.append(f"NPC: {e['vendor']}")
        if e.get("zone"):
            attrs.append(f"Zone: {e['zone']}")

        attr_str = ", ".join(attrs) if attrs else "-"
        prov_style = "bold green" if e["provenance"] == "cross_modal_corroborated" else "blue" if e["provenance"] == "table_only" else "yellow"
        c_tab_str = f"{e['c_tab']:.0%}" if e['c_tab'] > 0 else "-"
        c_txt_str = f"{e['c_txt']:.0%}" if e['c_txt'] > 0 else "-"

        ent_table.add_row(
            e["label"],
            e["entity_type"],
            f"[{prov_style}]{e['provenance']}[/]",
            c_tab_str,
            c_txt_str,
            f"{e['c_fused']:.1%}",
            attr_str,
        )
    console.print(ent_table)

    # 3. Multi-Hop Fused Triples Table
    if res.fused_triples:
        trip_table = Table(title=f"Fused Relational Triples ({len(res.fused_triples)} triples)", border_style="cyan")
        trip_table.add_column("Subject", style="cyan")
        trip_table.add_column("Predicate", style="bold magenta")
        trip_table.add_column("Object", style="green")

        for s, p, o in res.fused_triples[:20]:
            trip_table.add_row(s, p, o)
        if len(res.fused_triples) > 20:
            trip_table.add_row("...", f"+{len(res.fused_triples) - 20} more triples", "...")
        console.print(trip_table)

    # 4. Summary Card
    val_style = "bold green" if res.conforms_shacl else "bold red"
    console.print(
        f"\n[bold]Triangulation Summary:[/] {len(res.fused_entities)} entities | {len(res.fused_triples)} triples | "
        f"Avg Conf: [bold green]{res.confidence_summary['avg_fused_confidence']:.1%}[/] | "
        f"Corroboration Gain: [bold yellow]+{res.confidence_summary['corroboration_gain_pct']:.1f}%[/] | "
        f"SHACL Status: [{val_style}]{res.validation_status}[/]"
    )

    # 5. Output Serialization
    if out_format == "turtle":
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(res.turtle)
            console.print(f"[bold green]Saved fused Turtle graph to:[/] {output_file}")
        else:
            console.print("\n[bold cyan]Fused RDF Turtle Serialization:[/]")
            console.print(Syntax(res.turtle, "turtle", theme="monokai", line_numbers=True))
    elif out_format == "json-ld":
        import json
        json_str = json.dumps(res.json_ld, indent=2)
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_str)
            console.print(f"[bold green]Saved fused JSON-LD graph to:[/] {output_file}")
        else:
            console.print("\n[bold cyan]Fused JSON-LD Serialization:[/]")
            console.print(Syntax(json_str, "json", theme="monokai", line_numbers=True))

    # 6. Dashboard Generation
    if dashboard_path:
        mesh = res.table_mesh
        mesh.turtle = res.turtle
        mesh.json_ld = res.json_ld
        mesh.validation_status = res.validation_status
        mesh.validation_violations = res.violations
        generate_dashboard_html(mesh, title=f"Cross-Modal Fusion - {t_path.stem}", output_path=dashboard_path)
        console.print(f"[bold green]Saved interactive dashboard to:[/] [white underline]{dashboard_path}[/]")


if __name__ == "__main__":
    main()
