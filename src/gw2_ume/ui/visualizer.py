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

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title} - {table_name_esc}</title>
<style>
:root {{
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-card: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --accent: #38bdf8;
  --accent-hover: #0ea5e9;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --border: #475569;
  --gold: #fbbf24;
  --purple: #c084fc;
}}

* {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.5;
  padding: 24px;
}}

.dashboard-container {{
  max-width: 1440px;
  margin: 0 auto;
}}

header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}}

.logo-group h1 {{
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 8px;
}}

.logo-group p {{
  color: var(--text-secondary);
  font-size: 14px;
}}

.kpi-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}

.kpi-card {{
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}}

.kpi-card .val {{
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}}

.kpi-card .lbl {{
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
}}

.badge-conforming {{
  color: var(--success) !important;
}}

.badge-warning {{
  color: var(--warning) !important;
}}

.nav-tabs {{
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}}

.tab-btn {{
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  padding: 10px 18px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}}

.tab-btn:hover {{
  color: var(--text-primary);
  background: var(--bg-secondary);
}}

.tab-btn.active {{
  background: var(--bg-secondary);
  color: var(--accent);
  border-color: var(--border);
}}

.tab-content {{
  display: none;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 24px;
}}

.tab-content.active {{
  display: block;
}}

/* Table Styling */
.table-responsive {{
  overflow-x: auto;
}}

table.gw2-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}

table.gw2-table th, table.gw2-table td {{
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}}

table.gw2-table th {{
  background: #1e293b;
  color: var(--accent);
  position: sticky;
  top: 0;
}}

table.gw2-table tr:hover {{
  background: rgba(255, 255, 255, 0.03);
}}

.type-tag {{
  display: inline-block;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  margin-top: 4px;
  background: #334155;
  color: var(--gold);
}}

.cell-ann {{
  border-bottom: 1px dotted var(--accent);
  cursor: help;
}}

/* Interactive Canvas / Graph */
#graph-container {{
  position: relative;
  width: 100%;
  height: 600px;
  background: #090d16;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
}}

#meshCanvas {{
  width: 100%;
  height: 100%;
}}

.graph-controls {{
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(30, 41, 59, 0.85);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-secondary);
}}

.inspector-panel {{
  position: absolute;
  bottom: 12px;
  left: 12px;
  max-width: 320px;
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid var(--accent);
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  display: none;
}}

/* Ping Pong Trace */
.timeline {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}

.turn-card {{
  border-left: 4px solid var(--accent);
  background: #1e293b;
  border-radius: 0 8px 8px 0;
  padding: 16px;
}}

.turn-card.evaluator {{
  border-left-color: var(--warning);
}}

.turn-card.verifier {{
  border-left-color: var(--success);
}}

.turn-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}}

.speaker-title {{
  font-weight: 700;
  font-size: 14px;
}}

.action-badge {{
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}}

.action-PROPOSE {{ background: rgba(56, 189, 248, 0.2); color: var(--accent); }}
.action-EVALUATE {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}
.action-REPAIR {{ background: rgba(192, 132, 252, 0.2); color: var(--purple); }}
.action-VERIFY {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}

/* Code Viewer */
pre.code-block {{
  background: #090d16;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: #e2e8f0;
  overflow-x: auto;
  max-height: 500px;
}}

.copy-btn {{
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  float: right;
  font-size: 11px;
  margin-bottom: 8px;
}}

.copy-btn:hover {{
  background: var(--border);
}}
</style>
</head>
<body>

<div class="dashboard-container">
  <header>
    <div class="logo-group">
      <h1>GW2-UME Semantic Mesh Visualizer</h1>
      <p>Universal Matrix Extraction & Neuro-Symbolic Graph Layer</p>
    </div>
    <div>
      <span style="font-size: 13px; color: var(--text-secondary);">Table: <strong>{table_name_esc}</strong></span>
    </div>
  </header>

  <!-- Executive KPIs -->
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="val">{len(mesh.nodes)}</div>
      <div class="lbl">Mesh Nodes</div>
    </div>
    <div class="kpi-card">
      <div class="val">{len(mesh.edges)}</div>
      <div class="lbl">Relational Edges</div>
    </div>
    <div class="kpi-card">
      <div class="val">{len(mesh.cea)}</div>
      <div class="lbl">Cell Annotations (CEA)</div>
    </div>
    <div class="kpi-card">
      <div class="val">{len(mesh.cta)}</div>
      <div class="lbl">Column Types (CTA)</div>
    </div>
    <div class="kpi-card">
      <div class="val badge-conforming">{mesh.validation_status}</div>
      <div class="lbl">SHACL Status</div>
    </div>
  </div>

  <!-- Navigation Tabs -->
  <div class="nav-tabs">
    <button class="tab-btn active" onclick="switchTab('tab-table')">Table & Annotations (CEA/CTA)</button>
    <button class="tab-btn" onclick="switchTab('tab-graph')">Relational Mesh Graph</button>
    <button class="tab-btn" onclick="switchTab('tab-pingpong')">Neuro-Symbolic Ping-Pong Trace</button>
    <button class="tab-btn" onclick="switchTab('tab-rdf')">RDF Export (Turtle / JSON-LD)</button>
  </div>

  <!-- Tab 1: Table & Annotations -->
  <div id="tab-table" class="tab-content active">
    <h3 style="margin-bottom: 12px; color: var(--accent);">Annotated Matrix</h3>
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
    <h3 style="margin-bottom: 12px; color: var(--accent);">Interactive Semantic Mesh Graph</h3>
    <div id="graph-container">
      <canvas id="meshCanvas"></canvas>
      <div class="graph-controls">
        <span>Click node to inspect | Drag to move</span>
      </div>
      <div id="inspector" class="inspector-panel"></div>
    </div>
  </div>

  <!-- Tab 3: Neuro-Symbolic Ping-Pong Trace -->
  <div id="tab-pingpong" class="tab-content">
    <h3 style="margin-bottom: 16px; color: var(--accent);">Neuro-Symbolic Dialogue & Repair Trace</h3>
    <div class="timeline">
      {"".join(
        f"""<div class='turn-card {"evaluator" if t["speaker"] == "Symbolic Validator" and t["action"] == "EVALUATE" else "verifier" if t["action"] == "VERIFY" else ""}'>
          <div class='turn-header'>
            <span class='speaker-title'>Round {t["round"]} - {html.escape(t["speaker"])}</span>
            <span class='action-badge action-{t["action"]}'>{t["action"]}</span>
          </div>
          <p style='color: var(--text-primary); font-size: 13px; margin-bottom: 6px;'>{html.escape(t["message"])}</p>
          <span style='font-size: 11px; color: var(--text-secondary);'>Confidence: {int(t["confidence"] * 100)}%</span>
        </div>"""
        for t in pingpong_data.get("turns", [])
      )}
    </div>
  </div>

  <!-- Tab 4: RDF Export -->
  <div id="tab-rdf" class="tab-content">
    <h3 style="margin-bottom: 12px; color: var(--accent);">RDF Turtle & JSON-LD</h3>
    <button class="copy-btn" onclick="copyCode('turtleCode')">Copy Turtle</button>
    <pre id="turtleCode" class="code-block">{turtle_esc}</pre>
    
    <h4 style="margin: 20px 0 10px; color: var(--accent);">JSON-LD Format</h4>
    <button class="copy-btn" onclick="copyCode('jsonldCode')">Copy JSON-LD</button>
    <pre id="jsonldCode" class="code-block">{jsonld_esc}</pre>
  </div>
</div>

<script>
const DATA = {payload_json};

function switchTab(tabId) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(tabId).classList.add('active');
  if (tabId === 'tab-graph') {{
    initGraph();
  }}
}}

function copyCode(id) {{
  const txt = document.getElementById(id).innerText;
  navigator.clipboard.writeText(txt);
  alert("Copied to clipboard!");
}}

// Simple Force Graph simulation in HTML5 Canvas
let canvas, ctx, nodes = [], edges = [], animId = null, selectedNode = null;

function initGraph() {{
  canvas = document.getElementById('meshCanvas');
  if (!canvas) return;
  ctx = canvas.getContext('2d');
  
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;

  // Initialize node positions in circular layout
  const w = canvas.width, h = canvas.height;
  const radius = Math.min(w, h) * 0.35;
  const total = DATA.nodes.length;

  nodes = DATA.nodes.map((n, idx) => {{
    const angle = (idx / (total || 1)) * 2 * Math.PI;
    return {{
      ...n,
      x: w / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 40,
      y: h / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 40,
      vx: 0,
      vy: 0,
      radius: n.type === 'PrecursorWeapon' ? 12 : (n.type === 'NPCVendor' ? 10 : 8)
    }};
  }});

  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  edges = DATA.edges.map(e => ({{
    ...e,
    sourceNode: nodeMap.get(e.source),
    targetNode: nodeMap.get(e.target)
  }})).filter(e => e.sourceNode && e.targetNode);

  if (animId) cancelAnimationFrame(animId);
  animate();
}}

function animate() {{
  // Simple force step
  for (let i = 0; i < nodes.length; i++) {{
    for (let j = i + 1; j < nodes.length; j++) {{
      let dx = nodes[j].x - nodes[i].x;
      let dy = nodes[j].y - nodes[i].y;
      let dist = Math.hypot(dx, dy) || 1;
      if (dist < 120) {{
        let force = (120 - dist) / 120 * 0.5;
        nodes[i].x -= (dx / dist) * force;
        nodes[i].y -= (dy / dist) * force;
        nodes[j].x += (dx / dist) * force;
        nodes[j].y += (dy / dist) * force;
      }}
    }}
  }}

  // Spring force on edges
  edges.forEach(e => {{
    let dx = e.targetNode.x - e.sourceNode.x;
    let dy = e.targetNode.y - e.sourceNode.y;
    let dist = Math.hypot(dx, dy) || 1;
    let spring = (dist - 90) * 0.02;
    e.sourceNode.x += (dx / dist) * spring;
    e.sourceNode.y += (dy / dist) * spring;
    e.targetNode.x -= (dx / dist) * spring;
    e.targetNode.y -= (dy / dist) * spring;
  }});

  // Render
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw edges
  ctx.lineWidth = 1.5;
  edges.forEach(e => {{
    ctx.strokeStyle = 'rgba(71, 85, 105, 0.7)';
    ctx.beginPath();
    ctx.moveTo(e.sourceNode.x, e.sourceNode.y);
    ctx.lineTo(e.targetNode.x, e.targetNode.y);
    ctx.stroke();

    // Edge label
    ctx.fillStyle = '#94a3b8';
    ctx.font = '9px sans-serif';
    let midX = (e.sourceNode.x + e.targetNode.x) / 2;
    let midY = (e.sourceNode.y + e.targetNode.y) / 2;
    ctx.fillText(e.label, midX, midY);
  }});

  // Draw nodes
  nodes.forEach(n => {{
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
    if (n.type === 'PrecursorWeapon') ctx.fillStyle = '#38bdf8';
    else if (n.type === 'NPCVendor') ctx.fillStyle = '#fbbf24';
    else if (n.type === 'Zone') ctx.fillStyle = '#10b981';
    else if (n.type === 'CraftingDiscipline') ctx.fillStyle = '#c084fc';
    else ctx.fillStyle = '#94a3b8';

    ctx.fill();
    ctx.strokeStyle = '#0f172a';
    ctx.stroke();

    // Label
    ctx.fillStyle = '#f8fafc';
    ctx.font = '10px sans-serif';
    ctx.fillText(n.label, n.x + n.radius + 4, n.y + 3);
  }});

  animId = requestAnimationFrame(animate);
}}

// Canvas click interaction
window.addEventListener('load', () => {{
  const c = document.getElementById('meshCanvas');
  if (c) {{
    c.addEventListener('click', (e) => {{
      const rect = c.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const clicked = nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 4);
      const inspector = document.getElementById('inspector');
      if (clicked) {{
        selectedNode = clicked;
        inspector.style.display = 'block';
        inspector.innerHTML = `<strong>${{clicked.label}}</strong><br>
          <span style="color:var(--accent)">Type:</span> ${{clicked.type}}<br>
          <span style="color:var(--text-secondary)">URI:</span> ${{clicked.uri}}<br>
          <span style="color:var(--text-secondary)">Position:</span> Row ${{clicked.row}}, Col ${{clicked.col}}`;
      }} else {{
        inspector.style.display = 'none';
      }}
    }});
  }}
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
