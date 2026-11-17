"""Interactive HTML Visualizer and Semantic Workbench for GW2-UME."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from gw2_ume.mesh.models import RelationalMesh
from gw2_ume.neurosymbolic.pingpong import PingPongResult

# Canonical 12x12 inline epistemic gutter SVGs (Priory UI & Workbench Specification)
_SVG_ENTAILED = (
    '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">'
    '<path d="M3 2.3V9.7M3 6H9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>'
)
_SVG_SYNTHESIZED = (
    '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">'
    '<path d="M2 4.4C3.6 3.1 5.1 5.7 6.7 4.4C8.3 3.1 9.4 4.4 10 4.4'
    'M2 7.6C3.6 6.3 5.1 8.9 6.7 7.6C8.3 6.3 9.4 7.6 10 7.6" '
    'stroke="currentColor" stroke-width="1.35" stroke-linecap="round"/></svg>'
)


def _is_numeric_cell(value: Any) -> bool:
    """Return True if a cell string parses as a plain number or percentage for tabular-nums right alignment."""
    s = str(value).strip().replace(",", "")
    if s.endswith("%"):
        s = s[:-1].strip()
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def _build_table_html(mesh: RelationalMesh) -> tuple[str, str]:
    """Render annotated matrix table headers and rows with numeric right alignment."""
    col_numeric: List[bool] = []
    for c_idx in range(len(mesh.cta)):
        vals = [row[c_idx] for row in mesh.rows if c_idx < len(row) and str(row[c_idx]).strip() != ""]
        is_num_col = bool(vals) and all(_is_numeric_cell(v) for v in vals)
        col_numeric.append(is_num_col)

    head_cells: List[str] = ['<th class="num" style="width:42px;">#</th>']
    for c_idx, c in enumerate(mesh.cta):
        align_cls = ' class="num"' if col_numeric[c_idx] else ""
        col_name = html.escape(c.col_name)
        type_label = html.escape(c.type_label)
        head_cells.append(
            f'<th{align_cls} title="{col_name} ({type_label})">'
            f'<div class="th-name">{col_name}</div>'
            f'<div class="th-type">{type_label}</div>'
            f"</th>"
        )

    body_rows: List[str] = []
    for r_idx, row in enumerate(mesh.rows):
        cells = [f'<td class="num" style="color:var(--text-muted);">{r_idx + 1}</td>']
        for c_idx, cell in enumerate(row):
            cell_esc = html.escape(str(cell))
            is_num = (c_idx < len(col_numeric) and col_numeric[c_idx]) or _is_numeric_cell(cell)
            cls = ' class="num"' if is_num else ""
            cells.append(
                f'<td{cls}><span class="cell-ann" title="Row {r_idx}, Col {c_idx}: {cell_esc}">{cell_esc}</span></td>'
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return "".join(head_cells), "".join(body_rows)


def _build_turns_html(turns: List[Dict[str, Any]]) -> str:
    """Render neuro-symbolic dialogue turns with 16px epistemic gutter symbols."""
    if not turns:
        return '<div class="wb-empty-row">No neuro-symbolic dialogue turns recorded.</div>'

    chunks: List[str] = []
    for t in turns:
        action = str(t.get("action", "PROPOSE"))
        is_entailed = action == "VERIFY"
        gutter_svg = _SVG_ENTAILED if is_entailed else _SVG_SYNTHESIZED
        gutter_title = "Entailed / Verified (⊢)" if is_entailed else "Synthesized / Proposed / Repaired (≈)"
        gutter_cls = "epistemic-entailed" if is_entailed else "epistemic-synth"
        speaker = html.escape(str(t.get("speaker", "")))
        msg = html.escape(str(t.get("message", "")))
        conf_pct = int(float(t.get("confidence", 0.0)) * 100)
        rnd = html.escape(str(t.get("round", "")))
        action_esc = html.escape(action)
        chunks.append(
            f'<div class="wb-epistemic-row">'
            f'<span class="epistemic-gutter {gutter_cls}" title="{gutter_title}">{gutter_svg}</span>'
            f'<div class="epistemic-content">'
            f'<div class="turn-header">'
            f'<span class="speaker-title">Round {rnd} &middot; {speaker}</span>'
            f'<span class="turn-meta">'
            f'<span class="action-tag action-{action_esc}">{action_esc}</span>'
            f'<span class="tabular-nums" style="color:var(--text-muted); font-size:11px;">{conf_pct}%</span>'
            f"</span>"
            f"</div>"
            f'<div class="turn-msg">{msg}</div>'
            f"</div>"
            f"</div>"
        )
    return "".join(chunks)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__ESCAPED_TITLE__ - __TABLE_NAME_ESC__</title>
<script>
  (function () {
    try {
      if (localStorage.getItem('gw2_ume_theme') === 'dark') {
        document.documentElement.classList.add('dark');
      }
    } catch (e) {}
  })();
</script>
<style>
:root, .light, .theme-day {
  /* Canonical Priory UI & Workbench Specification — Daylight */
  --bg-canvas: #f5f2eb;
  --bg-canvas-rgb: 245 242 235;
  --bg-surface-1: #fcfaf5;
  --bg-surface-1-rgb: 252 250 245;
  --bg-surface-2: #f3efe6;
  --bg-surface-2-rgb: 243 239 230;
  --bg-surface-3: #e9e4d8;
  --bg-surface-3-rgb: 233 228 216;

  --border-subtle: #ded8ca;
  --border-subtle-rgb: 222 216 202;
  --border-strong: #c7beae;
  --border-strong-rgb: 199 190 174;

  --text-primary: #252830;
  --text-primary-rgb: 37 40 48;
  --text-secondary: #484d59;
  --text-secondary-rgb: 72 77 89;
  --text-muted: #666259;
  --text-muted-rgb: 102 98 89;

  --accent-primary: #3b6694;
  --accent-primary-rgb: 59 102 148;
  --accent-hover: #2f537a;
  --accent-fg: #fcfaf5;
  --accent-bg: rgba(59, 102, 148, 0.09);
  --accent-border: rgba(59, 102, 148, 0.24);

  --accent-ochre: #b88438;
  --accent-entail: #4a78a8;
  --status-clear: #3d8b66;
  --status-clear-bg: #e7f3ed;
  --status-clear-text: #3d8b66;
  --status-clear-border: #b5dac6;

  --status-warn: #b88438;
  --status-warn-bg: #f6eedb;
  --status-warn-text: #b88438;
  --status-warn-border: #e0cba0;

  --status-avoid: #942c40;
  --status-avoid-bg: #f6dfe3;
  --status-avoid-text: #942c40;
  --status-avoid-border: #e5b2bc;

  /* Tier 2 BFO Semiotic Tokens */
  --sigil-cont-fg: #9e6b22; --sigil-cont-bg: rgba(158, 107, 34, 0.09); --sigil-cont-bd: rgba(158, 107, 34, 0.23);
  --sigil-proc-fg: #336699; --sigil-proc-bg: rgba(51, 102, 153, 0.09); --sigil-proc-bd: rgba(51, 102, 153, 0.23);
  --sigil-role-fg: #7552a3; --sigil-role-bg: rgba(117, 82, 163, 0.09); --sigil-role-bd: rgba(117, 82, 163, 0.23);
  --sigil-gdc-fg:  #287078; --sigil-gdc-bg:  rgba(40, 112, 120, 0.09); --sigil-gdc-bd:  rgba(40, 112, 120, 0.23);
  --sigil-qual-fg: #965562; --sigil-qual-bg: rgba(150, 85, 98, 0.09);  --sigil-qual-bd: rgba(150, 85, 98, 0.23);
  --sigil-ind-fg:  #347555; --sigil-ind-bg:  rgba(52, 117, 85, 0.09);  --sigil-ind-bd:  rgba(52, 117, 85, 0.23);

  --graph-dot-color: rgba(102, 98, 89, 0.25);

  --radius-pane: 0px;
  --radius-control: 2px;
  --radius-node: 2px;

  --font-sans: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Text', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace;
}

.dark, .theme-dark {
  /* Canonical Priory UI & Workbench Specification — Nocturne */
  --bg-canvas: #171a23;
  --bg-canvas-rgb: 23 26 35;
  --bg-surface-1: #1e222e;
  --bg-surface-1-rgb: 30 34 46;
  --bg-surface-2: #252a38;
  --bg-surface-2-rgb: 37 42 56;
  --bg-surface-3: #2f3648;
  --bg-surface-3-rgb: 47 54 72;

  --border-subtle: #353c50;
  --border-subtle-rgb: 53 60 80;
  --border-strong: #48516b;
  --border-strong-rgb: 72 81 107;

  --text-primary: #ece8e0;
  --text-primary-rgb: 236 232 224;
  --text-secondary: #b5bbc9;
  --text-secondary-rgb: 181 187 201;
  --text-muted: #8d94a6;
  --text-muted-rgb: 141 148 166;

  --accent-primary: #7ea4d4;
  --accent-primary-rgb: 126 164 212;
  --accent-hover: #6891c6;
  --accent-fg: #141821;
  --accent-bg: rgba(126, 164, 212, 0.14);
  --accent-border: rgba(126, 164, 212, 0.30);

  --accent-ochre: #d4a15a;
  --accent-entail: #7ea4d4;
  --status-clear: #6ec297;
  --status-clear-bg: rgba(110, 194, 151, 0.14);
  --status-clear-text: #6ec297;
  --status-clear-border: rgba(110, 194, 151, 0.30);

  --status-warn: #d4a15a;
  --status-warn-bg: rgba(212, 161, 90, 0.14);
  --status-warn-text: #d4a15a;
  --status-warn-border: rgba(212, 161, 90, 0.30);

  --status-avoid: #ee9aa8;
  --status-avoid-bg: rgba(201, 86, 107, 0.15);
  --status-avoid-text: #ee9aa8;
  --status-avoid-border: rgba(201, 86, 107, 0.32);

  --sigil-cont-fg: #dfb068; --sigil-cont-bg: rgba(223, 176, 104, 0.13); --sigil-cont-bd: rgba(223, 176, 104, 0.28);
  --sigil-proc-fg: #7ea8d8; --sigil-proc-bg: rgba(126, 168, 216, 0.13); --sigil-proc-bd: rgba(126, 168, 216, 0.28);
  --sigil-role-fg: #b298dc; --sigil-role-bg: rgba(178, 152, 220, 0.13); --sigil-role-bd: rgba(178, 152, 220, 0.28);
  --sigil-gdc-fg:  #6ec1cb; --sigil-gdc-bg:  rgba(110, 193, 203, 0.13); --sigil-gdc-bd:  rgba(110, 193, 203, 0.28);
  --sigil-qual-fg: #d9919f; --sigil-qual-bg: rgba(217, 145, 159, 0.13); --sigil-qual-bd: rgba(217, 145, 159, 0.28);
  --sigil-ind-fg:  #78ba9a; --sigil-ind-bg:  rgba(120, 186, 154, 0.13); --sigil-ind-bd:  rgba(120, 186, 154, 0.28);

  --graph-dot-color: rgba(141, 148, 166, 0.22);
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  font-family: var(--font-sans);
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
  background-color: var(--bg-canvas);
  background-image: none;
  color: var(--text-primary);
  font-size: 12.5px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.tabular-nums { font-variant-numeric: tabular-nums; }

pre, code {
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.5;
}

/* Rigid 100vw x 100vh Desktop Workbench Shell */
.wb-shell {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  display: grid;
  grid-template-rows: 34px minmax(0, 1fr) 23px;
  grid-template-columns: 240px minmax(0, 1fr) 320px;
  background: var(--bg-canvas);
  color: var(--text-primary);
}

/* Top Toolbar (34px) */
.wb-toolbar {
  grid-column: 1 / -1;
  grid-row: 1;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 10px;
  background: var(--bg-surface-2);
  border-bottom: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
  min-width: 0;
}

.toolbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
}

.toolbar-brand h1 {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  white-space: nowrap;
}

.toolbar-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-sep {
  width: 1px;
  height: 14px;
  background: var(--border-subtle);
  flex-shrink: 0;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Flat 0px Mode Tabs inside Top Toolbar */
.nav-tabs {
  display: flex;
  align-items: stretch;
  height: 34px;
  gap: 0;
}

.tab-btn {
  height: 34px;
  background: transparent;
  border: none;
  border-left: 1px solid var(--border-subtle);
  border-bottom: 2px solid transparent;
  border-radius: var(--radius-pane);
  color: var(--text-secondary);
  padding: 0 10px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  white-space: nowrap;
}
.tab-btn:last-child { border-right: 1px solid var(--border-subtle); }
.tab-btn:hover { color: var(--text-primary); background: var(--bg-surface-3); }
.tab-btn.active {
  background: var(--bg-surface-1);
  color: var(--text-primary);
  font-weight: 500;
  border-bottom-color: var(--accent-primary);
}

.wb-btn, .theme-btn, .copy-btn {
  height: 25px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 0 8px;
  border-radius: var(--radius-control);
  background: var(--bg-surface-1);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  line-height: 23px;
  cursor: pointer;
  white-space: nowrap;
}
.wb-btn:hover, .theme-btn:hover, .copy-btn:hover {
  background: var(--bg-surface-3);
  border-color: var(--border-strong);
}

.wb-btn-sm {
  height: 22px;
  padding: 0 6px;
  font-size: 11.5px;
  line-height: 20px;
}

/* Left Navigation Pane (240px) */
.wb-left {
  grid-column: 1;
  grid-row: 2;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface-1);
  border-right: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
  overflow-y: auto;
  overflow-x: hidden;
}

/* Central Workspace (1fr) */
.wb-center {
  grid-column: 2;
  grid-row: 2;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-canvas);
  border-radius: var(--radius-pane);
  overflow: hidden;
}

/* Right Inspector Pane (320px) */
.wb-right {
  grid-column: 3;
  grid-row: 2;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface-1);
  border-left: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
  overflow-y: auto;
  overflow-x: hidden;
}

/* Bottom Status Bar (23px) */
.wb-statusbar {
  grid-column: 1 / -1;
  grid-row: 3;
  height: 23px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 10px;
  background: var(--bg-surface-2);
  border-top: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
  color: var(--text-muted);
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
}

.status-cluster {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.badge-conforming { color: var(--status-clear); font-weight: 500; }
.badge-warning { color: var(--status-warn); font-weight: 500; }

/* Section Headers, Navigation Tree Rows, 2-Column Property Rows */
.wb-sec-hdr {
  height: 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
  background: var(--bg-surface-2);
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-secondary);
}
.wb-sec-hdr:first-child { border-top: none; }

.wb-sec-count {
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  font-weight: 400;
}

.wb-tree-row {
  width: 100%;
  height: 23px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border: none;
  border-left: 2px solid transparent;
  border-bottom: 1px solid transparent;
  border-radius: var(--radius-pane);
  background: transparent;
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  user-select: none;
}
.wb-tree-row:hover { background: var(--bg-surface-2); }
.wb-tree-row.is-active {
  background: var(--bg-surface-3);
  border-left-color: var(--accent-primary);
  font-weight: 500;
}
.wb-tree-row.is-indent { padding-left: 20px; }

.wb-tree-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.wb-tree-count {
  margin-left: auto;
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  flex-shrink: 0;
}

.wb-prop-row {
  display: grid;
  grid-template-columns: minmax(92px, 38%) minmax(0, 1fr);
  align-items: baseline;
  gap: 8px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
  font-size: 12px;
}

.wb-prop-key {
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-prop-val {
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-prop-link {
  color: var(--accent-primary);
  background: transparent;
  border: none;
  padding: 0;
  font-family: var(--font-sans);
  font-size: 12px;
  cursor: pointer;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.wb-prop-link:hover { text-decoration: underline; }

/* Docked Sub-Toolbar & Tab Panes */
.wb-subtoolbar {
  height: 28px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 8px;
  background: var(--bg-surface-2);
  border-bottom: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
}

.subtoolbar-group {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.tab-content {
  display: none;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  background: var(--bg-surface-1);
  overflow: hidden;
}
.tab-content.active { display: flex; }

/* Interactive 2D Graph Viewport */
#graph-container {
  flex: 1;
  min-height: 0;
  width: 100%;
  position: relative;
  background-color: var(--bg-canvas);
  background-image: radial-gradient(circle, var(--graph-dot-color) 0.9px, transparent 0.9px);
  background-size: 22px 22px;
  border-radius: var(--radius-pane);
  overflow: hidden;
}

#meshCanvas {
  width: 100%;
  height: 100%;
  display: block;
  cursor: grab;
}
#meshCanvas:active { cursor: grabbing; }

.graph-legend {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow-x: auto;
  font-size: 11.5px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

/* Docked Right Inspector Header (BFO tint reserved for active inspector header) */
.inspector-docked {
  display: flex;
  flex-direction: column;
}

.inspector-active-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 8px;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Hairline Ledger Table (23px rows, right-aligned tabular-nums) */
.table-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

table.gw2-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

table.gw2-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 4px 8px;
  text-align: left;
  background: var(--bg-surface-2);
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-subtle);
  font-weight: 500;
  vertical-align: top;
  white-space: nowrap;
}

table.gw2-table th.num, table.gw2-table td.num { text-align: right; }

.th-name { font-size: 11.5px; font-weight: 500; color: var(--text-primary); }
.th-type { font-size: 10.5px; font-weight: 400; color: var(--text-muted); }

table.gw2-table td {
  height: 23px;
  padding: 0 8px;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary);
  white-space: nowrap;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}

table.gw2-table tbody tr:hover { background: var(--bg-surface-2); }

.cell-ann { cursor: help; }

/* Epistemic 16px Gutter Rows in Dialogue Tab */
.timeline-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.wb-epistemic-row {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  column-gap: 8px;
  align-items: start;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-subtle);
  border-radius: var(--radius-pane);
}

.epistemic-gutter {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 18px;
  flex-shrink: 0;
}
.epistemic-entailed { color: var(--status-clear); }
.epistemic-synth { color: var(--accent-ochre); }

.epistemic-content { min-width: 0; }

.turn-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.speaker-title {
  font-weight: 500;
  font-size: 12px;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.turn-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.action-tag {
  display: inline-block;
  font-size: 10.5px;
  padding: 1px 5px;
  border-radius: var(--radius-control);
  font-weight: 500;
  border: 1px solid var(--border-subtle);
}
.action-PROPOSE  { background: var(--accent-bg); color: var(--accent-primary); border-color: var(--accent-border); }
.action-EVALUATE { background: var(--status-warn-bg); color: var(--status-warn-text); border-color: var(--status-warn-border); }
.action-REPAIR   { background: var(--sigil-role-bg); color: var(--sigil-role-fg); border-color: var(--sigil-role-bd); }
.action-VERIFY   { background: var(--status-clear-bg); color: var(--status-clear-text); border-color: var(--status-clear-border); }

.turn-msg {
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.45;
}

.wb-empty-row {
  padding: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

/* Quarantined Monospace RDF Drawers */
.rdf-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.code-header-row {
  height: 26px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
  background: var(--bg-surface-2);
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-secondary);
}
.code-header-row:first-child { border-top: none; }

pre.code-block {
  background: var(--bg-canvas);
  border-radius: var(--radius-pane);
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-primary);
  overflow-x: auto;
  margin: 0;
}

@media (max-width: 1060px) {
  .wb-shell { grid-template-columns: 210px minmax(0, 1fr) 270px; }
}
</style>
</head>
<body>

<div class="wb-shell">
  <!-- Top Toolbar (34px) -->
  <header class="wb-toolbar">
    <div class="toolbar-brand">
      <h1>GW2-UME Semantic Mesh Visualizer</h1>
      <span class="toolbar-sep" aria-hidden="true"></span>
      <span class="toolbar-sub" title="__ESCAPED_TITLE__ · __TABLE_NAME_ESC__">__ESCAPED_TITLE__ &middot; __TABLE_NAME_ESC__</span>
    </div>

    <div class="toolbar-right">
      <div class="nav-tabs" role="tablist">
        <button type="button" class="tab-btn active" role="tab" onclick="switchTab('tab-graph', this)">Mesh Graph (__NODE_COUNT__)</button>
        <button type="button" class="tab-btn" role="tab" onclick="switchTab('tab-table', this)">Entity Ledger (__CEA_COUNT__)</button>
        <button type="button" class="tab-btn" role="tab" onclick="switchTab('tab-pingpong', this)">Neuro-Symbolic Dialogue (__TURN_COUNT__)</button>
        <button type="button" class="tab-btn" role="tab" onclick="switchTab('tab-rdf', this)">RDF / JSON-LD</button>
      </div>

      <button type="button" class="theme-btn" onclick="toggleTheme()" title="Toggle Daylight / Nocturne theme">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/></svg>
        <span id="themeToggleLabel">Nocturne</span>
      </button>
    </div>
  </header>

  <!-- Left Navigation Pane (240px) -->
  <aside id="leftSchemaPane" class="wb-left" aria-label="RDF Schema and Entity Explorer"></aside>

  <!-- Central Workspace (1fr) -->
  <main class="wb-center">
    <!-- Tab 1: Interactive Relational Mesh Graph -->
    <div id="tab-graph" class="tab-content active">
      <div class="wb-subtoolbar">
        <div class="subtoolbar-group">
          <button type="button" class="wb-btn wb-btn-sm" onclick="zoomIn()" title="Zoom in">+</button>
          <button type="button" class="wb-btn wb-btn-sm" onclick="zoomOut()" title="Zoom out">&minus;</button>
          <button type="button" class="wb-btn wb-btn-sm" onclick="fitGraph()" title="Fit all nodes into view">Fit</button>
          <button type="button" class="wb-btn wb-btn-sm" onclick="resetGraph()" title="Reset layout and zoom">Reset</button>
          <span class="toolbar-sep" aria-hidden="true"></span>
          <span id="zoomLabel" class="tabular-nums" style="font-size:11.5px; color:var(--text-muted);">100%</span>
        </div>
        <div id="graphLegend" class="graph-legend"></div>
      </div>
      <div id="graph-container">
        <canvas id="meshCanvas"></canvas>
      </div>
    </div>

    <!-- Tab 2: Table & Annotations -->
    <div id="tab-table" class="tab-content">
      <div class="wb-subtoolbar">
        <span style="font-size:12px; font-weight:500;">Entity Ledger Matrix</span>
        <span class="tabular-nums" style="font-size:11.5px; color:var(--text-muted);">__ROW_COUNT__ rows &times; __COL_COUNT__ cols</span>
      </div>
      <div class="table-scroll">
        <table class="gw2-table">
          <thead>
            <tr>__TABLE_HEAD_HTML__</tr>
          </thead>
          <tbody>
            __TABLE_BODY_HTML__
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 3: Neuro-Symbolic Ping-Pong Trace -->
    <div id="tab-pingpong" class="tab-content">
      <div class="wb-subtoolbar">
        <span style="font-size:12px; font-weight:500;">Neuro-Symbolic Dialogue &amp; Repair Trace</span>
        <span class="tabular-nums" style="font-size:11.5px; color:var(--text-muted);">__TURN_COUNT__ turns</span>
      </div>
      <div class="timeline-scroll">
        __TURNS_HTML__
      </div>
    </div>

    <!-- Tab 4: RDF Export -->
    <div id="tab-rdf" class="tab-content">
      <div class="rdf-scroll">
        <div class="code-header-row">
          <span>RDF Turtle Serialization</span>
          <button type="button" class="copy-btn wb-btn-sm" onclick="copyCode('turtleCode', this)">Copy Turtle</button>
        </div>
        <pre id="turtleCode" class="code-block"><code>__TURTLE_ESC__</code></pre>

        <div class="code-header-row">
          <span>JSON-LD Serialization</span>
          <button type="button" class="copy-btn wb-btn-sm" onclick="copyCode('jsonldCode', this)">Copy JSON-LD</button>
        </div>
        <pre id="jsonldCode" class="code-block"><code>__JSONLD_ESC__</code></pre>
      </div>
    </div>
  </main>

  <!-- Right Inspector Pane (320px, Permanently Docked) -->
  <aside class="wb-right" aria-label="Node and Mesh Inspector">
    <div class="wb-sec-hdr">
      <span>Inspector</span>
      <span id="inspectorKindLabel" class="wb-sec-count">Mesh</span>
    </div>
    <div id="inspector" class="inspector-docked"></div>
  </aside>

  <!-- Bottom Status Bar (23px) -->
  <footer class="wb-statusbar">
    <div class="status-cluster">
      <span>Nodes: __NODE_COUNT__</span>
      <span class="toolbar-sep" aria-hidden="true"></span>
      <span>Edges: __EDGE_COUNT__</span>
      <span class="toolbar-sep" aria-hidden="true"></span>
      <span>CEA: __CEA_COUNT__</span>
      <span class="toolbar-sep" aria-hidden="true"></span>
      <span>CTA: __CTA_COUNT__</span>
      <span class="toolbar-sep" aria-hidden="true"></span>
      <span>Turns: __TURN_COUNT__</span>
    </div>
    <div class="status-cluster">
      <span>SHACL: <span class="__STATUS_CLS__">__VALIDATION_STATUS__</span></span>
      <span class="toolbar-sep" aria-hidden="true"></span>
      <span>Converged: __CONVERGED_TEXT__</span>
    </div>
  </footer>
</div>

<script>
const DATA = __PAYLOAD_JSON__;

const PRIORY_SIGILS_SVG = {
  cont: '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><circle cx="6" cy="6" r="3.5" fill="currentColor"/></svg>',
  proc: '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2.6 2.75L6.1 6L2.6 9.25M6.4 2.75L9.9 6L6.4 9.25" stroke="currentColor" stroke-width="1.45" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  role: '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1.5L10.5 6L6 10.5L1.5 6Z" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
  gdc: '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1.4L10.6 6L6 10.6L1.4 6Z" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"/><circle cx="6" cy="6" r="1.4" fill="currentColor"/></svg>',
  qual: '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><circle cx="6" cy="6" r="4.1" stroke="currentColor" stroke-width="1.4"/><path d="M6 1.9A4.1 4.1 0 0 0 6 10.1Z" fill="currentColor"/></svg>',
  ind: '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 2.1L9.9 6L6 9.9L2.1 6Z" fill="currentColor"/></svg>'
};

const SIGIL_KINDS = ['cont', 'proc', 'role', 'gdc', 'qual', 'ind'];

function hashTypeIndex(typeName) {
  const str = String(typeName || 'Entity');
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function resolveBfoSigilKind(iriOrCategory = '') {
  const s = String(iriOrCategory).toLowerCase();
  if (s.includes('0000031') || s.includes('iao') || s.includes('generically') || s.includes('information') || s === 'ice' || s === 'gdc') return 'gdc';
  if (s.includes('0000015') || s.includes('0000003') || s.includes('occurrent') || s.includes('process') || s.includes('temporal')) return 'proc';
  if (s.includes('0000017') || s.includes('0000023') || s.includes('0000016') || s.includes('0000034') || s.includes('role') || s.includes('realizable') || s.includes('disposition') || s.includes('function')) return 'role';
  if (s.includes('0000019') || s.includes('quality') || s.includes('dataproperty') || s.includes('datatype')) return 'qual';
  if (s.includes('namedindividual') || s.includes('individual') || s.includes('speaker') || s.includes('instance')) return 'ind';
  if (s.includes('0000004') || s.includes('continuant') || s.includes('material')) return 'cont';
  return SIGIL_KINDS[hashTypeIndex(s) % SIGIL_KINDS.length];
}

function renderBfoSigilHtml(iriOrCategory = '') {
  const kind = resolveBfoSigilKind(iriOrCategory);
  const svg = PRIORY_SIGILS_SVG[kind] || PRIORY_SIGILS_SVG.cont;
  return `<span style="color:var(--sigil-${kind}-fg);display:inline-flex;align-items:center;justify-content:center;width:12px;height:12px;flex-shrink:0;">${svg}</span>`;
}

function readPrioryThemeTokens() {
  const cs = getComputedStyle(document.documentElement);
  const g = (v, fb = '') => (cs.getPropertyValue(v) || fb).trim();
  const mutedRgb = g('--text-muted-rgb', '102 98 89').replace(/\\s+/g, ', ');
  return {
    bgCanvas: g('--bg-canvas'),
    bgSurface1: g('--bg-surface-1'),
    borderSubtle: g('--border-subtle'),
    borderStrong: g('--border-strong'),
    textPrimary: g('--text-primary'),
    textSecondary: g('--text-secondary'),
    textMuted: g('--text-muted'),
    edgeStroke: `rgba(${mutedRgb}, 0.42)`,
    accentPrimary: g('--accent-primary'),
    sigils: {
      cont: { fg: g('--sigil-cont-fg'), bg: g('--sigil-cont-bg'), bd: g('--sigil-cont-bd') },
      proc: { fg: g('--sigil-proc-fg'), bg: g('--sigil-proc-bg'), bd: g('--sigil-proc-bd') },
      role: { fg: g('--sigil-role-fg'), bg: g('--sigil-role-bg'), bd: g('--sigil-role-bd') },
      gdc:  { fg: g('--sigil-gdc-fg'),  bg: g('--sigil-gdc-bg'),  bd: g('--sigil-gdc-bd')  },
      qual: { fg: g('--sigil-qual-fg'), bg: g('--sigil-qual-bg'), bd: g('--sigil-qual-bd') },
      ind:  { fg: g('--sigil-ind-fg'),  bg: g('--sigil-ind-bg'),  bd: g('--sigil-ind-bd')  }
    }
  };
}

function colorForType(typeName, tokens) {
  const kind = resolveBfoSigilKind(typeName);
  return (tokens.sigils[kind] && tokens.sigils[kind].fg) || tokens.accentPrimary;
}

function escapeHtmlClient(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function syncThemeLabel() {
  const isDark = document.documentElement.classList.contains('dark');
  const lbl = document.getElementById('themeToggleLabel');
  if (lbl) lbl.textContent = isDark ? 'Daylight' : 'Nocturne';
  renderGraphLegend();
}

function toggleTheme() {
  const root = document.documentElement;
  const nextDark = !root.classList.contains('dark');
  root.classList.toggle('dark', nextDark);
  try {
    localStorage.setItem('gw2_ume_theme', nextDark ? 'dark' : 'light');
  } catch (e) {}
  syncThemeLabel();
}

function switchTab(tabId, btnEl) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const targetBtn = btnEl || (typeof event !== 'undefined' ? event.currentTarget : null);
  if (targetBtn) targetBtn.classList.add('active');
  const targetPane = document.getElementById(tabId);
  if (targetPane) targetPane.classList.add('active');
  if (tabId === 'tab-graph') {
    resizeCanvas();
    if (!nodes.length) initGraph();
  }
}

function copyCode(id, btnEl) {
  const txt = document.getElementById(id).innerText;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(() => {
      if (btnEl) {
        const prev = btnEl.textContent;
        btnEl.textContent = 'Copied';
        setTimeout(() => { btnEl.textContent = prev; }, 1400);
      }
    });
  }
}

let activeTypeFilter = null;
let canvas, ctx, nodes = [], edges = [], animId = null, selectedNode = null, dragNode = null;
let cssWidth = 800, cssHeight = 560;
let viewScale = 1, viewPanX = 0, viewPanY = 0;
let isPanning = false, panStartX = 0, panStartY = 0;

function renderGraphLegend() {
  const legendEl = document.getElementById('graphLegend');
  if (!legendEl) return;
  const seen = [];
  (DATA.nodes || []).forEach(n => {
    const t = n.type || 'Entity';
    if (!seen.includes(t)) seen.push(t);
  });
  legendEl.innerHTML = seen.map(t =>
    `<span class="legend-chip" onclick="filterByType('${escapeHtmlClient(t).replace(/'/g, "\\'")}')" title="Filter type: ${escapeHtmlClient(t)}">${renderBfoSigilHtml(t)}<span>${escapeHtmlClient(t)}</span></span>`
  ).join('');
}

function renderSchemaTree() {
  const left = document.getElementById('leftSchemaPane');
  if (!left) return;

  const typeCounts = new Map();
  const degreeMap = new Map();
  (DATA.nodes || []).forEach(n => {
    const t = n.type || 'Entity';
    typeCounts.set(t, (typeCounts.get(t) || 0) + 1);
  });
  (DATA.edges || []).forEach(e => {
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
  });

  let html = `
    <div class="wb-sec-hdr">
      <span>Entity Types</span>
      <span class="wb-sec-count">${typeCounts.size}</span>
    </div>
    <button type="button" class="wb-tree-row ${activeTypeFilter === null ? 'is-active' : ''}" onclick="filterByType(null)">
      ${renderBfoSigilHtml('continuant')}
      <span class="wb-tree-label">All Types</span>
      <span class="wb-tree-count">${(DATA.nodes || []).length}</span>
    </button>
  `;

  typeCounts.forEach((cnt, t) => {
    const isAct = activeTypeFilter === t;
    const safeArg = escapeHtmlClient(t).replace(/'/g, "\\'");
    html += `
      <button type="button" class="wb-tree-row is-indent ${isAct ? 'is-active' : ''}" onclick="filterByType('${safeArg}')" title="${escapeHtmlClient(t)}">
        ${renderBfoSigilHtml(t)}
        <span class="wb-tree-label">${escapeHtmlClient(t)}</span>
        <span class="wb-tree-count">${cnt}</span>
      </button>
    `;
  });

  const ctas = DATA.cta || [];
  html += `
    <div class="wb-sec-hdr">
      <span>Column Types (CTA)</span>
      <span class="wb-sec-count">${ctas.length}</span>
    </div>
  `;
  ctas.forEach(c => {
    html += `
      <div class="wb-tree-row" style="cursor:default;" title="${escapeHtmlClient(c.col_name)} -> ${escapeHtmlClient(c.type_label)}">
        ${renderBfoSigilHtml(c.type_label || c.type_uri)}
        <span class="wb-tree-label">${escapeHtmlClient(c.col_name)}</span>
        <span class="wb-tree-count">${escapeHtmlClient(c.type_label)}</span>
      </div>
    `;
  });

  const filteredNodes = activeTypeFilter
    ? (DATA.nodes || []).filter(n => (n.type || 'Entity') === activeTypeFilter)
    : (DATA.nodes || []);
  html += `
    <div class="wb-sec-hdr">
      <span>Graph Entities</span>
      <span class="wb-sec-count">${filteredNodes.length}</span>
    </div>
  `;
  filteredNodes.forEach(n => {
    const isSel = selectedNode && selectedNode.id === n.id;
    const safeId = escapeHtmlClient(n.id).replace(/'/g, "\\'");
    const deg = degreeMap.get(n.id) || 0;
    html += `
      <button type="button" class="wb-tree-row ${isSel ? 'is-active' : ''}" onclick="selectNodeById('${safeId}')" title="${escapeHtmlClient(n.label)} (${escapeHtmlClient(n.type || 'Entity')})">
        ${renderBfoSigilHtml(n.type || 'Entity')}
        <span class="wb-tree-label">${escapeHtmlClient(n.label)}</span>
        <span class="wb-tree-count">${deg}</span>
      </button>
    `;
  });

  left.innerHTML = html;
}

function filterByType(typeName) {
  activeTypeFilter = (activeTypeFilter === typeName) ? null : typeName;
  renderSchemaTree();
}

function selectNodeById(nodeId) {
  const hit = nodes.find(n => n.id === nodeId) || (DATA.nodes || []).find(n => n.id === nodeId) || null;
  selectedNode = hit;
  renderSchemaTree();
  renderInspector(hit);
}

function renderInspector(node) {
  const inspector = document.getElementById('inspector');
  const kindLbl = document.getElementById('inspectorKindLabel');
  if (!inspector) return;

  if (!node) {
    if (kindLbl) kindLbl.textContent = 'Mesh';
    const turns = (DATA.pingpong && DATA.pingpong.turns) || [];
    const violCount = (DATA.violations || []).length;
    inspector.innerHTML = `
      <div class="wb-prop-row"><span class="wb-prop-key">Table</span><span class="wb-prop-val" title="${escapeHtmlClient(DATA.tableName)}">${escapeHtmlClient(DATA.tableName)}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">Nodes</span><span class="wb-prop-val">${(DATA.nodes || []).length}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">Edges</span><span class="wb-prop-val">${(DATA.edges || []).length}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">CEA Links</span><span class="wb-prop-val">${(DATA.cea || []).length}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">CTA Columns</span><span class="wb-prop-val">${(DATA.cta || []).length}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">CPA Relations</span><span class="wb-prop-val">${(DATA.cpa || []).length}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">Dialogue Turns</span><span class="wb-prop-val">${turns.length}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">SHACL Status</span><span class="wb-prop-val">${escapeHtmlClient(DATA.validationStatus || 'UNKNOWN')}</span></div>
      <div class="wb-prop-row"><span class="wb-prop-key">Violations</span><span class="wb-prop-val">${violCount}</span></div>
    `;
    return;
  }

  const kind = resolveBfoSigilKind(node.type || 'Entity');
  if (kindLbl) kindLbl.textContent = node.type || 'Entity';

  const propEntries = Object.entries(node.properties || {});
  const nodeById = new Map((DATA.nodes || []).map(n => [n.id, n]));
  const inEdges = (DATA.edges || []).filter(e => e.target === node.id);
  const outEdges = (DATA.edges || []).filter(e => e.source === node.id);

  let html = `
    <div class="inspector-active-hdr" style="background:var(--sigil-${kind}-bg);">
      ${renderBfoSigilHtml(node.type || 'Entity')}
      <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtmlClient(node.label)}">${escapeHtmlClient(node.label)}</span>
    </div>
    <div class="wb-prop-row">
      <span class="wb-prop-key">Type</span>
      <span class="wb-prop-val" title="${escapeHtmlClient(node.type || 'Entity')}">${escapeHtmlClient(node.type || 'Entity')}</span>
    </div>
    <div class="wb-prop-row">
      <span class="wb-prop-key">URI</span>
      <span class="wb-prop-val" title="${escapeHtmlClient(node.uri)}"><code>${escapeHtmlClient(node.uri)}</code></span>
    </div>
    <div class="wb-prop-row">
      <span class="wb-prop-key">Matrix Cell</span>
      <span class="wb-prop-val">Row ${node.row}, Col ${node.col}</span>
    </div>
  `;

  propEntries.forEach(([k, v]) => {
    const valStr = typeof v === 'object' ? JSON.stringify(v) : String(v);
    html += `
      <div class="wb-prop-row">
        <span class="wb-prop-key" title="${escapeHtmlClient(k)}">${escapeHtmlClient(k)}</span>
        <span class="wb-prop-val" title="${escapeHtmlClient(valStr)}">${escapeHtmlClient(valStr)}</span>
      </div>
    `;
  });

  html += `
    <div class="wb-sec-hdr">
      <span>Outgoing Links</span>
      <span class="wb-sec-count">${outEdges.length}</span>
    </div>
  `;
  if (!outEdges.length) {
    html += `<div class="wb-prop-row"><span class="wb-prop-key">None</span><span class="wb-prop-val">&mdash;</span></div>`;
  } else {
    outEdges.forEach(e => {
      const target = nodeById.get(e.target);
      const tLabel = target ? target.label : e.target;
      const safeId = escapeHtmlClient(e.target).replace(/'/g, "\\'");
      html += `
        <div class="wb-prop-row">
          <span class="wb-prop-key" title="${escapeHtmlClient(e.label)}">${escapeHtmlClient(e.label)}</span>
          <span class="wb-prop-val"><button type="button" class="wb-prop-link" onclick="selectNodeById('${safeId}')" title="${escapeHtmlClient(tLabel)}">${escapeHtmlClient(tLabel)}</button></span>
        </div>
      `;
    });
  }

  html += `
    <div class="wb-sec-hdr">
      <span>Incoming Links</span>
      <span class="wb-sec-count">${inEdges.length}</span>
    </div>
  `;
  if (!inEdges.length) {
    html += `<div class="wb-prop-row"><span class="wb-prop-key">None</span><span class="wb-prop-val">&mdash;</span></div>`;
  } else {
    inEdges.forEach(e => {
      const src = nodeById.get(e.source);
      const sLabel = src ? src.label : e.source;
      const safeId = escapeHtmlClient(e.source).replace(/'/g, "\\'");
      html += `
        <div class="wb-prop-row">
          <span class="wb-prop-key" title="${escapeHtmlClient(e.label)}">${escapeHtmlClient(e.label)}</span>
          <span class="wb-prop-val"><button type="button" class="wb-prop-link" onclick="selectNodeById('${safeId}')" title="${escapeHtmlClient(sLabel)}">${escapeHtmlClient(sLabel)}</button></span>
        </div>
      `;
    });
  }

  inspector.innerHTML = html;
}

function updateZoomLabel() {
  const lbl = document.getElementById('zoomLabel');
  if (lbl) lbl.textContent = Math.round(viewScale * 100) + '%';
}

function zoomAt(cx, cy, factor) {
  const nextScale = Math.max(0.25, Math.min(3.5, viewScale * factor));
  const actualFactor = nextScale / viewScale;
  viewPanX = cx - (cx - viewPanX) * actualFactor;
  viewPanY = cy - (cy - viewPanY) * actualFactor;
  viewScale = nextScale;
  updateZoomLabel();
}

function zoomIn() { zoomAt(cssWidth / 2, cssHeight / 2, 1.2); }
function zoomOut() { zoomAt(cssWidth / 2, cssHeight / 2, 1 / 1.2); }

function fitGraph() {
  if (!nodes.length) return;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  nodes.forEach(n => {
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
  });
  const spanX = Math.max(80, maxX - minX + 90);
  const spanY = Math.max(80, maxY - minY + 90);
  viewScale = Math.max(0.35, Math.min(1.6, Math.min((cssWidth - 40) / spanX, (cssHeight - 40) / spanY)));
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  viewPanX = cssWidth / 2 - cx * viewScale;
  viewPanY = cssHeight / 2 - cy * viewScale;
  updateZoomLabel();
}

function resetGraph() {
  viewScale = 1;
  viewPanX = 0;
  viewPanY = 0;
  updateZoomLabel();
  initGraph();
}

function resizeCanvas() {
  const container = document.getElementById('graph-container');
  if (!container || !canvas || !ctx) return;
  const rect = container.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  cssWidth = rect.width;
  cssHeight = rect.height;
  canvas.width = Math.max(1, Math.floor(cssWidth * dpr));
  canvas.height = Math.max(1, Math.floor(cssHeight * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function initGraph() {
  canvas = document.getElementById('meshCanvas');
  if (!canvas) return;
  ctx = canvas.getContext('2d');
  resizeCanvas();

  const degreeMap = new Map();
  (DATA.edges || []).forEach(e => {
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
  });

  const w = cssWidth || 800;
  const h = cssHeight || 560;
  const radius = Math.min(w, h) * 0.34;
  const total = DATA.nodes.length;

  nodes = DATA.nodes.map((n, idx) => {
    const angle = (idx / (total || 1)) * 2 * Math.PI;
    const deg = degreeMap.get(n.id) || 0;
    return {
      ...n,
      x: w / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 28,
      y: h / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 28,
      vx: 0,
      vy: 0,
      radius: Math.min(12, 6.5 + Math.round(Math.sqrt(deg) * 1.4))
    };
  });

  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  edges = DATA.edges.map(e => ({
    ...e,
    sourceNode: nodeMap.get(e.source),
    targetNode: nodeMap.get(e.target)
  })).filter(e => e.sourceNode && e.targetNode);

  renderGraphLegend();
  renderSchemaTree();
  renderInspector(selectedNode);
  if (animId) cancelAnimationFrame(animId);
  animate();
}

function screenToWorld(sx, sy) {
  return {
    x: (sx - viewPanX) / viewScale,
    y: (sy - viewPanY) / viewScale
  };
}

function animate() {
  if (!ctx || !canvas) return;
  const tokens = readPrioryThemeTokens();

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      let dx = nodes[j].x - nodes[i].x;
      let dy = nodes[j].y - nodes[i].y;
      let dist = Math.hypot(dx, dy) || 1;
      if (dist < 120) {
        let force = (120 - dist) / 120 * 0.48;
        if (nodes[i] !== dragNode) {
          nodes[i].x -= (dx / dist) * force;
          nodes[i].y -= (dy / dist) * force;
        }
        if (nodes[j] !== dragNode) {
          nodes[j].x += (dx / dist) * force;
          nodes[j].y += (dy / dist) * force;
        }
      }
    }
  }

  edges.forEach(e => {
    let dx = e.targetNode.x - e.sourceNode.x;
    let dy = e.targetNode.y - e.sourceNode.y;
    let dist = Math.hypot(dx, dy) || 1;
    let spring = (dist - 96) * 0.02;
    if (e.sourceNode !== dragNode) {
      e.sourceNode.x += (dx / dist) * spring;
      e.sourceNode.y += (dy / dist) * spring;
    }
    if (e.targetNode !== dragNode) {
      e.targetNode.x -= (dx / dist) * spring;
      e.targetNode.y -= (dy / dist) * spring;
    }
  });

  ctx.clearRect(0, 0, cssWidth, cssHeight);
  ctx.save();
  ctx.translate(viewPanX, viewPanY);
  ctx.scale(viewScale, viewScale);

  ctx.lineWidth = 1.2;
  ctx.font = '11.5px -apple-system, BlinkMacSystemFont, "Inter", "SF Pro Text", system-ui, sans-serif';

  edges.forEach(e => {
    const dim = activeTypeFilter &&
      (e.sourceNode.type || 'Entity') !== activeTypeFilter &&
      (e.targetNode.type || 'Entity') !== activeTypeFilter;
    ctx.globalAlpha = dim ? 0.16 : 1;
    ctx.strokeStyle = tokens.edgeStroke;
    ctx.beginPath();
    ctx.moveTo(e.sourceNode.x, e.sourceNode.y);
    ctx.lineTo(e.targetNode.x, e.targetNode.y);
    ctx.stroke();

    ctx.fillStyle = tokens.textMuted;
    let midX = (e.sourceNode.x + e.targetNode.x) / 2;
    let midY = (e.sourceNode.y + e.targetNode.y) / 2;
    ctx.fillText(e.label, midX, midY);
  });

  nodes.forEach(n => {
    const dim = activeTypeFilter && (n.type || 'Entity') !== activeTypeFilter;
    const isSel = selectedNode && selectedNode.id === n.id;
    ctx.globalAlpha = dim ? 0.22 : 1;
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
    ctx.fillStyle = colorForType(n.type, tokens);
    ctx.fill();
    ctx.lineWidth = isSel ? 2.2 : 1.5;
    ctx.strokeStyle = isSel ? tokens.textPrimary : tokens.bgSurface1;
    ctx.stroke();

    ctx.fillStyle = tokens.textPrimary;
    ctx.fillText(n.label, n.x + n.radius + 5, n.y + 3.5);
  });

  ctx.restore();
  animId = requestAnimationFrame(animate);
}

window.addEventListener('DOMContentLoaded', () => {
  syncThemeLabel();
  renderSchemaTree();
  renderInspector(null);

  const c = document.getElementById('meshCanvas');
  const container = document.getElementById('graph-container');
  if (c) {
    initGraph();

    if (typeof ResizeObserver !== 'undefined' && container) {
      const ro = new ResizeObserver(() => resizeCanvas());
      ro.observe(container);
    }

    c.addEventListener('mousedown', (e) => {
      const rect = c.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const pt = screenToWorld(sx, sy);
      const hit = nodes.find(n => Math.hypot(n.x - pt.x, n.y - pt.y) <= n.radius + 6);
      if (hit) {
        dragNode = hit;
        selectedNode = hit;
        renderSchemaTree();
        renderInspector(hit);
      } else {
        isPanning = true;
        panStartX = sx - viewPanX;
        panStartY = sy - viewPanY;
        selectedNode = null;
        renderSchemaTree();
        renderInspector(null);
      }
    });

    c.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = c.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      zoomAt(sx, sy, factor);
    }, { passive: false });

    window.addEventListener('mousemove', (e) => {
      const rect = c.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      if (dragNode) {
        const pt = screenToWorld(sx, sy);
        dragNode.x = pt.x;
        dragNode.y = pt.y;
      } else if (isPanning) {
        viewPanX = sx - panStartX;
        viewPanY = sy - panStartY;
      }
    });

    window.addEventListener('mouseup', () => {
      dragNode = null;
      isPanning = false;
    });
  }
});
</script>
</body>
</html>
"""


def generate_dashboard_html(
    mesh: RelationalMesh,
    pingpong_result: Optional[PingPongResult] = None,
    title: str = "GW2-UME Semantic Dashboard",
    output_path: Optional[str] = None,
) -> str:
    """Generates a standalone, interactive HTML workbench visualizing the Relational Mesh and Ping-Pong trace."""
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

    pingpong_data = (
        pingpong_result.to_dict()
        if pingpong_result
        else {
            "table_name": mesh.table_name,
            "turns": [],
            "initial_proposals_count": len(mesh.cea),
            "violations_detected_count": len(mesh.validation_violations),
            "repairs_applied_count": 0,
            "final_verified_triples_count": len(mesh.edges),
            "conforms_shacl": mesh.validation_status == "CONFORMING",
        }
    )

    payload_json = json.dumps(
        {
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
        }
    )

    table_head_html, table_body_html = _build_table_html(mesh)
    turns = pingpong_data.get("turns", [])
    turns_html = _build_turns_html(turns)
    status_cls = "badge-conforming" if mesh.validation_status == "CONFORMING" else "badge-warning"
    conforms_text = "Yes" if pingpong_data.get("conforms_shacl") else "No"

    replacements = {
        "__ESCAPED_TITLE__": html.escape(title),
        "__TABLE_NAME_ESC__": html.escape(mesh.table_name),
        "__NODE_COUNT__": str(len(mesh.nodes)),
        "__EDGE_COUNT__": str(len(mesh.edges)),
        "__CEA_COUNT__": str(len(mesh.cea)),
        "__CTA_COUNT__": str(len(mesh.cta)),
        "__TURN_COUNT__": str(len(turns)),
        "__ROW_COUNT__": str(len(mesh.rows)),
        "__COL_COUNT__": str(len(mesh.headers)),
        "__STATUS_CLS__": status_cls,
        "__VALIDATION_STATUS__": html.escape(mesh.validation_status),
        "__CONVERGED_TEXT__": conforms_text,
        "__TABLE_HEAD_HTML__": table_head_html,
        "__TABLE_BODY_HTML__": table_body_html,
        "__TURNS_HTML__": turns_html,
        "__TURTLE_ESC__": html.escape(mesh.turtle),
        "__JSONLD_ESC__": html.escape(json.dumps(mesh.json_ld, indent=2)),
        "__PAYLOAD_JSON__": payload_json,
    }

    html_content = _HTML_TEMPLATE
    for token, value in replacements.items():
        html_content = html_content.replace(token, value)

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    return html_content


__all__ = ["generate_dashboard_html"]
