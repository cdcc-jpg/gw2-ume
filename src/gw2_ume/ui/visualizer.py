"""Interactive HTML Visualizer and Semantic Dashboard for GW2-UME."""

from __future__ import annotations
import json
import html
from typing import Optional, Dict, Any, List
from pathlib import Path

from gw2_ume.mesh.models import RelationalMesh
from gw2_ume.neurosymbolic.pingpong import PingPongResult


def generate_dashboard_html(
    mesh: RelationalMesh,
    pingpong_result: Optional[PingPongResult] = None,
    title: str = "GW2-UME Semantic Dashboard",
    output_path: Optional[str] = None,
) -> str:
    """Generates a standalone, interactive HTML dashboard visualizing the Relational Mesh and Ping-Pong trace."""

    # Serialize nodes and edges for client-side graph rendering
    nodes_data = [
        {
            "id": n.id,
            "label": n.label,
            "type": n.node_type,
            "uri": n.uri,
            "row": n.row_idx,
            "col": n.col_idx,
            "properties": n.properties,
        }
        for n in mesh.nodes
    ]

    edges_data = [
        {
            "source": e.source_id,
            "target": e.target_id,
            "label": e.property_label,
            "uri": e.property_uri,
            "confidence": e.confidence,
        }
        for e in mesh.edges
    ]

    cta_data = [c.to_dict() for c in mesh.cta]
    cea_data = [c.to_dict() for c in mesh.cea]
    cpa_data = [p.to_dict() for p in mesh.cpa]

    pingpong_data = pingpong_result.to_dict() if pingpong_result else {
        "table_name": mesh.table_name,
        "turns": [],
        "initial_proposals_count": len(mesh.cea),
        "violations_detected_count": len(mesh.validation_violations),
        "repairs_applied_count": 0,
        "final_verified_triples_count": len(mesh.edges),
        "conforms_shacl": mesh.validation_status == "CONFORMING",
    }

    # Prepare JSON payloads
    payload_json = json.dumps({
        "tableName": mesh.table_name,
        "headers": mesh.headers,
        "rows": mesh.rows,
        "cta": cta_data,
        "cea": cea_data,
        "cpa": cpa_data,
        "nodes": nodes_data,
        "edges": edges_data,
        "pingpong": pingpong_data,
        "validationStatus": mesh.validation_status,
        "violations": mesh.validation_violations,
        "turtle": mesh.turtle,
        "jsonld": mesh.json_ld,
    })

    escaped_title = html.escape(title)
    table_name_esc = html.escape(mesh.table_name)
    turtle_esc = html.escape(mesh.turtle)
    jsonld_esc = html.escape(json.dumps(mesh.json_ld, indent=2))
    status_cls = "badge-conforming" if mesh.validation_status == "CONFORMING" else "badge-warning"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title} - {table_name_esc}</title>
<script>
  (function () {{
    try {{
      if (localStorage.getItem('gw2_ume_theme') === 'dark') {{
        document.documentElement.classList.add('dark');
      }}
    }} catch (e) {{}}
  }})();
</script>
<style>
:root, .light {{
  /* Priory Critical Edition (v5) — Daylight */
  --bg-canvas: #f5f2eb;
  --bg-surface-1: #fcfaf5;
  --bg-surface-2: #f3efe6;
  --bg-surface-3: #e9e4d8;
  --border-subtle: #ded8ca;
  --border-strong: #c7beae;

  --text-primary: #252830;
  --text-secondary: #484d59;
  --text-muted: #666259;

  --accent-primary: #3b6694;
  --accent-hover: #2f537a;
  --accent-fg: #fcfaf5;
  --accent-bg: rgba(59, 102, 148, 0.10);
  --accent-border: rgba(59, 102, 148, 0.26);

  --status-clear: #3d8b66;
  --status-clear-bg: #e7f3ed;
  --status-clear-text: #286146;
  --status-clear-border: #b5dac6;

  --status-warn: #b88438;
  --status-warn-bg: #f6eedb;
  --status-warn-text: #7d561c;
  --status-warn-border: #e0cba0;

  --status-avoid: #942c40;
  --status-avoid-bg: #f6dfe3;
  --status-avoid-text: #942c40;
  --status-avoid-border: #e5b2bc;

  --accent-wisteria: #7552a3;
  --accent-wisteria-bg: rgba(117, 82, 163, 0.10);
  --accent-wisteria-border: rgba(117, 82, 163, 0.25);

  --graph-dot: rgba(199, 190, 174, 0.55);
  --overlay-bg: rgba(252, 250, 245, 0.92);

  --font-sans: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Text', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace;
}}

.dark {{
  /* Priory Critical Edition (v5) — Nocturne */
  --bg-canvas: #171a23;
  --bg-surface-1: #1e222e;
  --bg-surface-2: #252a38;
  --bg-surface-3: #2f3648;
  --border-subtle: #353c50;
  --border-strong: #48516b;

  --text-primary: #ece8e0;
  --text-secondary: #b5bbc9;
  --text-muted: #8d94a6;

  --accent-primary: #7ea4d4;
  --accent-hover: #6891c6;
  --accent-fg: #141821;
  --accent-bg: rgba(126, 164, 212, 0.14);
  --accent-border: rgba(126, 164, 212, 0.34);

  --status-clear: #6ec297;
  --status-clear-bg: rgba(110, 194, 151, 0.14);
  --status-clear-text: #6ec297;
  --status-clear-border: rgba(110, 194, 151, 0.34);

  --status-warn: #d4a15a;
  --status-warn-bg: rgba(212, 161, 90, 0.15);
  --status-warn-text: #d4a15a;
  --status-warn-border: rgba(212, 161, 90, 0.34);

  --status-avoid: #ee9aa8;
  --status-avoid-bg: rgba(201, 86, 107, 0.15);
  --status-avoid-text: #ee9aa8;
  --status-avoid-border: rgba(238, 154, 168, 0.35);

  --accent-wisteria: #b298dc;
  --accent-wisteria-bg: rgba(178, 152, 220, 0.14);
  --accent-wisteria-border: rgba(178, 152, 220, 0.34);

  --graph-dot: rgba(72, 81, 107, 0.55);
  --overlay-bg: rgba(30, 34, 46, 0.92);
}}

* {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  font-family: var(--font-sans);
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
  background-color: var(--bg-canvas);
  background-image: none;
  color: var(--text-primary);
  font-size: 13.5px;
  line-height: 1.5;
  letter-spacing: -0.005em;
  padding: 24px;
  -webkit-font-smoothing: antialiased;
}}

.tabular-nums {{
  font-variant-numeric: tabular-nums;
}}

.dashboard-container {{
  max-width: 1380px;
  margin: 0 auto;
}}

header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-subtle);
}}

.logo-group h1 {{
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.015em;
}}

.logo-group p {{
  color: var(--text-muted);
  font-size: 12.5px;
  margin-top: 2px;
}}

.header-meta {{
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}}

.table-pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--bg-surface-1);
  border: 1px solid var(--border-subtle);
  font-size: 12px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}}

.table-pill strong {{
  font-weight: 500;
  color: var(--text-primary);
}}

.theme-btn {{
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px;
  border-radius: 6px;
  background: var(--bg-surface-1);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.14s ease, border-color 0.14s ease;
}}

.theme-btn:hover {{
  background: var(--bg-surface-2);
  border-color: var(--border-strong);
}}

/* Single-depth KPI Hairline Plate */
.kpi-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  background: var(--bg-surface-1);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  margin-bottom: 18px;
  overflow: hidden;
}}

.kpi-card {{
  padding: 14px 18px;
  border-right: 1px solid var(--border-subtle);
}}

.kpi-card:last-child {{
  border-right: none;
}}

.kpi-card .lbl {{
  font-size: 11.5px;
  font-weight: 400;
  color: var(--text-muted);
  margin-bottom: 4px;
}}

.kpi-card .val {{
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.25;
}}

.badge-conforming {{
  color: var(--status-clear) !important;
}}

.badge-warning {{
  color: var(--status-warn) !important;
}}

/* Navigation Tabs */
.nav-tabs {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}}

.tab-btn {{
  min-height: 32px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  padding: 6px 13px;
  border-radius: 6px;
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition: background-color 0.14s ease, color 0.14s ease, border-color 0.14s ease;
}}

.tab-btn:hover {{
  color: var(--text-primary);
  background: var(--bg-surface-2);
}}

.tab-btn.active {{
  background: var(--bg-surface-1);
  color: var(--text-primary);
  font-weight: 500;
  border-color: var(--border-strong);
  box-shadow: 0 1px 2px rgba(37, 40, 48, 0.05);
}}

/* Single-depth Content Plate */
.tab-content {{
  display: none;
  background: var(--bg-surface-1);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 20px;
}}

.tab-content.active {{
  display: block;
}}

.section-heading {{
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 12px;
}}

/* Hairline Table Styling */
.table-responsive {{
  overflow-x: auto;
}}

table.gw2-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}}

table.gw2-table th, table.gw2-table td {{
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: top;
}}

table.gw2-table th {{
  background: var(--bg-surface-2);
  color: var(--text-secondary);
  font-weight: 500;
  position: sticky;
  top: 0;
}}

table.gw2-table tbody tr:hover {{
  background: var(--bg-surface-2);
}}

.type-tag {{
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 9999px;
  margin-top: 4px;
  background: var(--accent-bg);
  color: var(--accent-primary);
  border: 1px solid var(--accent-border);
}}

.cell-ann {{
  border-bottom: 1px dotted var(--border-strong);
  cursor: help;
}}

/* Interactive 2D Graph Viewport (dot-grid strictly restricted here) */
#graph-container {{
  position: relative;
  width: 100%;
  height: 580px;
  background-color: var(--bg-surface-2);
  background-image: radial-gradient(circle, var(--graph-dot) 0.9px, transparent 0.9px);
  background-size: 22px 22px;
  border-radius: 8px;
  overflow: hidden;
}}

#meshCanvas {{
  width: 100%;
  height: 100%;
  display: block;
  cursor: grab;
}}

#meshCanvas:active {{
  cursor: grabbing;
}}

.graph-controls {{
  position: absolute;
  top: 12px;
  right: 12px;
  background: var(--overlay-bg);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  font-size: 11.5px;
  color: var(--text-secondary);
}}

.graph-legend {{
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 65%;
  background: var(--overlay-bg);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  font-size: 11.5px;
  color: var(--text-secondary);
}}

.legend-chip {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
}}

.legend-dot {{
  width: 7px;
  height: 7px;
  border-radius: 9999px;
  display: inline-block;
}}

.inspector-panel {{
  position: absolute;
  bottom: 12px;
  left: 12px;
  max-width: 340px;
  background: var(--overlay-bg);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  display: none;
}}

/* Ping-Pong Dialogue Trace (unboxed left-ruled wells) */
.timeline {{
  display: flex;
  flex-direction: column;
  gap: 10px;
}}

.turn-card {{
  border-left: 2px solid var(--accent-primary);
  background: var(--bg-surface-2);
  border-radius: 0 8px 8px 0;
  padding: 12px 16px;
}}

.turn-card.evaluator {{
  border-left-color: var(--status-warn);
}}

.turn-card.verifier {{
  border-left-color: var(--status-clear);
}}

.turn-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}}

.speaker-title {{
  font-weight: 500;
  font-size: 12.5px;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}}

.action-badge {{
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 9999px;
  font-weight: 500;
  border: 1px solid transparent;
}}

.action-PROPOSE {{ background: var(--accent-bg); color: var(--accent-primary); border-color: var(--accent-border); }}
.action-EVALUATE {{ background: var(--status-warn-bg); color: var(--status-warn-text); border-color: var(--status-warn-border); }}
.action-REPAIR {{ background: var(--accent-wisteria-bg); color: var(--accent-wisteria); border-color: var(--accent-wisteria-border); }}
.action-VERIFY {{ background: var(--status-clear-bg); color: var(--status-clear-text); border-color: var(--status-clear-border); }}

/* Quarantined Monospace Code Drawers */
.code-header-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}}

pre.code-block {{
  background: var(--bg-surface-2);
  border-radius: 8px;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--text-primary);
  overflow-x: auto;
  max-height: 480px;
  clear: both;
}}

.copy-btn {{
  min-height: 28px;
  background: var(--bg-surface-1);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  transition: background-color 0.14s ease, border-color 0.14s ease;
}}

.copy-btn:hover {{
  background: var(--bg-surface-2);
  border-color: var(--border-strong);
}}

@media (max-width: 760px) {{
  .kpi-card {{
    border-right: none;
    border-bottom: 1px solid var(--border-subtle);
  }}
  .kpi-card:last-child {{
    border-bottom: none;
  }}
}}
</style>
</head>
<body>

<div class="dashboard-container">
  <header>
    <div class="logo-group">
      <h1>GW2-UME Semantic Mesh Visualizer</h1>
      <p>{escaped_title} &middot; Universal Matrix Extraction &amp; Neuro-Symbolic Graph Layer</p>
    </div>
    <div class="header-meta">
      <span class="table-pill">Table: <strong>{table_name_esc}</strong></span>
      <button type="button" class="theme-btn" onclick="toggleTheme()" title="Toggle Daylight / Nocturne theme">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/></svg>
        <span id="themeToggleLabel">Nocturne</span>
      </button>
    </div>
  </header>

  <!-- Executive KPIs -->
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="lbl">Mesh Nodes</div>
      <div class="val">{len(mesh.nodes)}</div>
    </div>
    <div class="kpi-card">
      <div class="lbl">Relational Edges</div>
      <div class="val">{len(mesh.edges)}</div>
    </div>
    <div class="kpi-card">
      <div class="lbl">Cell Annotations (CEA)</div>
      <div class="val">{len(mesh.cea)}</div>
    </div>
    <div class="kpi-card">
      <div class="lbl">Column Types (CTA)</div>
      <div class="val">{len(mesh.cta)}</div>
    </div>
    <div class="kpi-card">
      <div class="lbl">SHACL Status</div>
      <div class="val {status_cls}">{html.escape(mesh.validation_status)}</div>
    </div>
  </div>

  <!-- Navigation Tabs -->
  <div class="nav-tabs">
    <button type="button" class="tab-btn active" onclick="switchTab('tab-table', this)">Table &amp; Annotations ({len(mesh.cea)})</button>
    <button type="button" class="tab-btn" onclick="switchTab('tab-graph', this)">Relational Mesh ({len(mesh.nodes)})</button>
    <button type="button" class="tab-btn" onclick="switchTab('tab-pingpong', this)">Dialogue Trace ({len(pingpong_data.get("turns", []))})</button>
    <button type="button" class="tab-btn" onclick="switchTab('tab-rdf', this)">RDF Export (Turtle / JSON-LD)</button>
  </div>

  <!-- Tab 1: Table & Annotations -->
  <div id="tab-table" class="tab-content active">
    <h3 class="section-heading">Annotated Matrix</h3>
    <div class="table-responsive">
      <table class="gw2-table">
        <thead>
          <tr>
            {"".join(f"<th>{html.escape(c.col_name)}<br><span class='type-tag'>{html.escape(c.type_label)}</span></th>" for c in mesh.cta)}
          </tr>
        </thead>
        <tbody>
          {"".join(
            "<tr>" + "".join(
              f"<td><span class='cell-ann' title='Row {r_idx}, Col {c_idx}'>{html.escape(cell)}</span></td>"
              for c_idx, cell in enumerate(row)
            ) + "</tr>"
            for r_idx, row in enumerate(mesh.rows)
          )}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Tab 2: Interactive Relational Mesh Graph -->
  <div id="tab-graph" class="tab-content">
    <h3 class="section-heading">Interactive Semantic Mesh Graph</h3>
    <div id="graph-container">
      <canvas id="meshCanvas"></canvas>
      <div id="graphLegend" class="graph-legend"></div>
      <div class="graph-controls">
        <span>Click node to inspect &middot; Drag to reposition</span>
      </div>
      <div id="inspector" class="inspector-panel"></div>
    </div>
  </div>

  <!-- Tab 3: Neuro-Symbolic Ping-Pong Trace -->
  <div id="tab-pingpong" class="tab-content">
    <h3 class="section-heading">Neuro-Symbolic Dialogue &amp; Repair Trace</h3>
    <div class="timeline">
      {"".join(
        f"""<div class='turn-card {"evaluator" if t["speaker"] == "Symbolic Validator" and t["action"] == "EVALUATE" else "verifier" if t["action"] == "VERIFY" else ""}'>
          <div class='turn-header'>
            <span class='speaker-title'>Round {t["round"]} &middot; {html.escape(t["speaker"])}</span>
            <span class='action-badge action-{t["action"]}'>{html.escape(t["action"])}</span>
          </div>
          <p style='color: var(--text-primary); font-size: 13.5px; margin-bottom: 4px;'>{html.escape(t["message"])}</p>
          <span class='tabular-nums' style='font-size: 11.5px; color: var(--text-muted);'>Confidence: {int(t["confidence"] * 100)}%</span>
        </div>"""
        for t in pingpong_data.get("turns", [])
      )}
    </div>
  </div>

  <!-- Tab 4: RDF Export -->
  <div id="tab-rdf" class="tab-content">
    <div class="code-header-row">
      <h3 class="section-heading" style="margin-bottom: 0;">RDF Turtle</h3>
      <button type="button" class="copy-btn" onclick="copyCode('turtleCode', this)">Copy Turtle</button>
    </div>
    <pre id="turtleCode" class="code-block">{turtle_esc}</pre>

    <div class="code-header-row" style="margin-top: 18px;">
      <h4 class="section-heading" style="margin-bottom: 0;">JSON-LD Serialization</h4>
      <button type="button" class="copy-btn" onclick="copyCode('jsonldCode', this)">Copy JSON-LD</button>
    </div>
    <pre id="jsonldCode" class="code-block">{jsonld_esc}</pre>
  </div>
</div>

<script>
const DATA = {payload_json};

const PALETTE_DAY = ['#3b6694', '#9e6b22', '#287078', '#7552a3', '#3d8b66', '#965562'];
const PALETTE_DARK = ['#7ea4d4', '#dfb068', '#6ec1cb', '#b298dc', '#6ec297', '#d9919f'];

function hashTypeIndex(typeName) {{
  const str = String(typeName || 'Entity');
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {{
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }}
  return Math.abs(h) % PALETTE_DAY.length;
}}

function colorForType(typeName, isDark) {{
  const idx = hashTypeIndex(typeName);
  return (isDark ? PALETTE_DARK : PALETTE_DAY)[idx];
}}

function syncThemeLabel() {{
  const isDark = document.documentElement.classList.contains('dark');
  const lbl = document.getElementById('themeToggleLabel');
  if (lbl) lbl.textContent = isDark ? 'Daylight' : 'Nocturne';
  renderGraphLegend();
}}

function toggleTheme() {{
  const root = document.documentElement;
  const nextDark = !root.classList.contains('dark');
  root.classList.toggle('dark', nextDark);
  try {{
    localStorage.setItem('gw2_ume_theme', nextDark ? 'dark' : 'light');
  }} catch (e) {{}}
  syncThemeLabel();
}}

function switchTab(tabId, btnEl) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const targetBtn = btnEl || (typeof event !== 'undefined' ? event.currentTarget : null);
  if (targetBtn) targetBtn.classList.add('active');
  document.getElementById(tabId).classList.add('active');
  if (tabId === 'tab-graph') {{
    initGraph();
  }}
}}

function copyCode(id, btnEl) {{
  const txt = document.getElementById(id).innerText;
  navigator.clipboard.writeText(txt).then(() => {{
    if (btnEl) {{
      const prev = btnEl.textContent;
      btnEl.textContent = 'Copied';
      setTimeout(() => {{ btnEl.textContent = prev; }}, 1400);
    }}
  }});
}}

function escapeHtmlClient(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

function renderGraphLegend() {{
  const legendEl = document.getElementById('graphLegend');
  if (!legendEl) return;
  const isDark = document.documentElement.classList.contains('dark');
  const seen = [];
  (DATA.nodes || []).forEach(n => {{
    const t = n.type || 'Entity';
    if (!seen.includes(t)) seen.push(t);
  }});
  legendEl.innerHTML = seen.map(t =>
    `<span class="legend-chip"><span class="legend-dot" style="background:${{colorForType(t, isDark)}}"></span>${{escapeHtmlClient(t)}}</span>`
  ).join('');
}}

// Domain-agnostic Force Graph simulation in HTML5 Canvas
let canvas, ctx, nodes = [], edges = [], animId = null, selectedNode = null, dragNode = null;

function initGraph() {{
  canvas = document.getElementById('meshCanvas');
  if (!canvas) return;
  ctx = canvas.getContext('2d');

  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;

  const degreeMap = new Map();
  (DATA.edges || []).forEach(e => {{
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
  }});

  const w = canvas.width, h = canvas.height;
  const radius = Math.min(w, h) * 0.34;
  const total = DATA.nodes.length;

  nodes = DATA.nodes.map((n, idx) => {{
    const angle = (idx / (total || 1)) * 2 * Math.PI;
    const deg = degreeMap.get(n.id) || 0;
    return {{
      ...n,
      x: w / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 32,
      y: h / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 32,
      vx: 0,
      vy: 0,
      radius: Math.min(13, 7 + Math.round(Math.sqrt(deg) * 1.5))
    }};
  }});

  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  edges = DATA.edges.map(e => ({{
    ...e,
    sourceNode: nodeMap.get(e.source),
    targetNode: nodeMap.get(e.target)
  }})).filter(e => e.sourceNode && e.targetNode);

  renderGraphLegend();
  if (animId) cancelAnimationFrame(animId);
  animate();
}}

function animate() {{
  const isDark = document.documentElement.classList.contains('dark');
  const edgeStroke = isDark ? 'rgba(141, 148, 166, 0.42)' : 'rgba(102, 98, 89, 0.38)';
  const edgeLabelFill = isDark ? '#8d94a6' : '#666259';
  const nodeRingStroke = isDark ? '#1e222e' : '#fcfaf5';
  const labelFill = isDark ? '#ece8e0' : '#252830';

  for (let i = 0; i < nodes.length; i++) {{
    for (let j = i + 1; j < nodes.length; j++) {{
      let dx = nodes[j].x - nodes[i].x;
      let dy = nodes[j].y - nodes[i].y;
      let dist = Math.hypot(dx, dy) || 1;
      if (dist < 120) {{
        let force = (120 - dist) / 120 * 0.48;
        if (nodes[i] !== dragNode) {{
          nodes[i].x -= (dx / dist) * force;
          nodes[i].y -= (dy / dist) * force;
        }}
        if (nodes[j] !== dragNode) {{
          nodes[j].x += (dx / dist) * force;
          nodes[j].y += (dy / dist) * force;
        }}
      }}
    }}
  }}

  edges.forEach(e => {{
    let dx = e.targetNode.x - e.sourceNode.x;
    let dy = e.targetNode.y - e.sourceNode.y;
    let dist = Math.hypot(dx, dy) || 1;
    let spring = (dist - 96) * 0.02;
    if (e.sourceNode !== dragNode) {{
      e.sourceNode.x += (dx / dist) * spring;
      e.sourceNode.y += (dy / dist) * spring;
    }}
    if (e.targetNode !== dragNode) {{
      e.targetNode.x -= (dx / dist) * spring;
      e.targetNode.y -= (dy / dist) * spring;
    }}
  }});

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.lineWidth = 1.25;
  edges.forEach(e => {{
    ctx.strokeStyle = edgeStroke;
    ctx.beginPath();
    ctx.moveTo(e.sourceNode.x, e.sourceNode.y);
    ctx.lineTo(e.targetNode.x, e.targetNode.y);
    ctx.stroke();

    ctx.fillStyle = edgeLabelFill;
    ctx.font = '10.5px -apple-system, BlinkMacSystemFont, Inter, sans-serif';
    let midX = (e.sourceNode.x + e.targetNode.x) / 2;
    let midY = (e.sourceNode.y + e.targetNode.y) / 2;
    ctx.fillText(e.label, midX, midY);
  }});

  nodes.forEach(n => {{
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
    ctx.fillStyle = colorForType(n.type, isDark);
    ctx.fill();
    ctx.lineWidth = selectedNode === n ? 2.2 : 1.5;
    ctx.strokeStyle = selectedNode === n ? labelFill : nodeRingStroke;
    ctx.stroke();

    ctx.fillStyle = labelFill;
    ctx.font = '11.5px -apple-system, BlinkMacSystemFont, Inter, sans-serif';
    ctx.fillText(n.label, n.x + n.radius + 5, n.y + 3.5);
  }});

  animId = requestAnimationFrame(animate);
}}

window.addEventListener('DOMContentLoaded', () => {{
  syncThemeLabel();
  const c = document.getElementById('meshCanvas');
  if (!c) return;

  c.addEventListener('mousedown', (e) => {{
    const rect = c.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const hit = nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 5);
    const inspector = document.getElementById('inspector');
    if (hit) {{
      dragNode = hit;
      selectedNode = hit;
      inspector.style.display = 'block';
      inspector.innerHTML = `<strong style="font-weight:600;">${{escapeHtmlClient(hit.label)}}</strong><br>
        <span style="color:var(--accent-primary);">Type:</span> ${{escapeHtmlClient(hit.type)}}<br>
        <span style="color:var(--text-muted);">URI:</span> ${{escapeHtmlClient(hit.uri)}}<br>
        <span style="color:var(--text-muted);">Position:</span> Row ${{hit.row}}, Col ${{hit.col}}`;
    }} else {{
      selectedNode = null;
      inspector.style.display = 'none';
    }}
  }});

  window.addEventListener('mousemove', (e) => {{
    if (!dragNode) return;
    const rect = c.getBoundingClientRect();
    dragNode.x = Math.max(16, Math.min(c.width - 16, e.clientX - rect.left));
    dragNode.y = Math.max(16, Math.min(c.height - 16, e.clientY - rect.top));
  }});

  window.addEventListener('mouseup', () => {{
    dragNode = null;
  }});
}});
</script>
</body>
</html>
"""

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    return html_content


__all__ = ["generate_dashboard_html"]
