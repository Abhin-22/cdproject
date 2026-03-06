"""
CEEA Compiler – Python Web Frontend
=====================================
A full-featured browser-based IDE for CEEA-Lang, served entirely
from Python using Flask. No Node.js or external build tools needed.

Features:
  • Syntax-highlighted code editor (CodeMirror via CDN)
  • Live compile button with animated feedback
  • Three-tab error panel: Beginner / Intermediate / Expert
  • Bytecode listing panel
  • Program output console
  • Example programs selector
  • Explanation level toggle
  • Dark IDE aesthetic

Run:
    python frontend/app.py
    # Then open http://localhost:5000

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

import json
import os
import sys
import traceback

# Make sure the parent package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template_string, request

from compiler import CEEACompiler

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Example programs
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLES = {
    "Hello World": """\
# CEEA-Lang – Hello World
print "Hello, World!"

int x = 10
int y = 20
int sum = x + y
print sum
""",
    "Functions & Loops": """\
# CEEA-Lang – Functions and Loops
func factorial(int n) {
    int result = 1
    int i = 1
    while i <= n {
        result = result * i
        i = i + 1
    }
    return result
}

for k in range(1, 6) {
    int f = factorial(k)
    print f
}
""",
    "Fibonacci": """\
# CEEA-Lang – Fibonacci (recursive)
func fib(int n) {
    if n <= 1 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}

for i in range(0, 8) {
    print fib(i)
}
""",
    "String Operations": """\
# CEEA-Lang – String operations
str first = "Hello"
str second = "CEEA-Lang"
str combined = first + " " + second
print combined

int len_demo = 42
str msg = "Answer: "
print msg
print len_demo
""",
    "Error: Type Mismatch": """\
# CEEA-Lang – Intentional errors (shows NLP explanations)

func add(int a, int b) {
    return a + b
}

# Error 1: undeclared variable
int result = z + 5

# Error 2: type mismatch
int number = "hello"

# Error 3: wrong argument count
int total = add(1, 2, 3)
""",
    "Error: Undeclared Variable": """\
# CEEA-Lang – Undeclared variable demo
int x = 10
int y = x + missing_var
print y
""",
    "Break & Continue": """\
# CEEA-Lang – Break and continue
int i = 0
while i < 10 {
    i = i + 1
    if i == 3 {
        continue
    }
    if i == 7 {
        break
    }
    print i
}
print "Done"
""",
}

# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>CEEA Compiler IDE</title>

<!-- CodeMirror -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/dracula.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js"></script>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;800&display=swap" rel="stylesheet"/>

<style>
/* ── Reset & Variables ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg0:     #0d0f14;
  --bg1:     #13151c;
  --bg2:     #1a1d27;
  --bg3:     #22263a;
  --border:  #2a2f47;
  --accent:  #7c6af7;
  --accent2: #4dd8e0;
  --accent3: #f7c26a;
  --success: #52e3a0;
  --error:   #ff5e7e;
  --warning: #ffb347;
  --text1:   #e8eaf6;
  --text2:   #9ba3c7;
  --text3:   #5c6494;
  --radius:  8px;
  --mono:    'JetBrains Mono', monospace;
  --sans:    'Syne', sans-serif;
}

html, body { height: 100%; background: var(--bg0); color: var(--text1); font-family: var(--sans); overflow: hidden; }

/* ── Top Bar ──────────────────────────────────────────────────────── */
.topbar {
  height: 52px;
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 16px;
  position: relative;
  z-index: 100;
}
.logo {
  font-family: var(--sans);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 2px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  flex-shrink: 0;
}
.logo-sub {
  font-size: 11px;
  color: var(--text3);
  letter-spacing: 1px;
  font-family: var(--mono);
  flex-shrink: 0;
}
.topbar-spacer { flex: 1; }

/* Level Toggle */
.level-group {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 3px;
}
.level-btn {
  font-family: var(--mono);
  font-size: 11px;
  padding: 4px 12px;
  border: none;
  border-radius: 16px;
  cursor: pointer;
  background: transparent;
  color: var(--text3);
  transition: all 0.2s;
  letter-spacing: 0.5px;
}
.level-btn.active {
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}

/* Examples dropdown */
.examples-select {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--bg2);
  border: 1px solid var(--border);
  color: var(--text2);
  padding: 5px 10px;
  border-radius: var(--radius);
  cursor: pointer;
  outline: none;
}

/* Compile Button */
.compile-btn {
  font-family: var(--sans);
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 1px;
  padding: 8px 24px;
  background: linear-gradient(135deg, var(--accent), #5a4de0);
  border: none;
  border-radius: 20px;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}
.compile-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(124,106,247,0.4); }
.compile-btn:active { transform: translateY(0); }
.compile-btn.loading { opacity: 0.7; cursor: default; }
.compile-btn .btn-text { display: inline-block; transition: opacity 0.2s; }

/* ── Layout ────────────────────────────────────────────────────────── */
.layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  height: calc(100vh - 52px);
}

/* ── Left Panel: Editor ────────────────────────────────────────────── */
.editor-pane {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg1);
}
.pane-header {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  gap: 10px;
  height: 40px;
}
.pane-title {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.5px;
  color: var(--text3);
  text-transform: uppercase;
}
.pane-badge {
  font-family: var(--mono);
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg3);
  color: var(--text3);
}
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-red   { background: #ff5e7e; }
.dot-yellow{ background: #ffb347; }
.dot-green { background: #52e3a0; }
.dots { display: flex; gap: 5px; margin-left: auto; }

/* CodeMirror overrides */
.CodeMirror {
  flex: 1;
  height: 100%;
  font-family: var(--mono) !important;
  font-size: 14px !important;
  line-height: 1.7 !important;
  background: var(--bg1) !important;
}
.CodeMirror-scroll { padding-bottom: 20px; }
.editor-wrap {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── Right Panel: Results ──────────────────────────────────────────── */
.results-pane {
  display: flex;
  flex-direction: column;
  background: var(--bg0);
  overflow: hidden;
}

/* Output console */
.output-section {
  height: 180px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.output-console {
  flex: 1;
  font-family: var(--mono);
  font-size: 13px;
  padding: 12px 16px;
  overflow-y: auto;
  background: #090b10;
  color: var(--success);
  line-height: 1.8;
}
.output-console .prompt { color: var(--text3); user-select: none; }
.output-line { animation: fadeIn 0.3s ease; }
.output-error-line { color: var(--error); }
.output-info-line  { color: var(--text3); }

/* Status bar */
.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 16px;
  background: var(--bg1);
  border-top: 1px solid var(--border);
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text3);
  flex-shrink: 0;
}
.status-indicator {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--text3);
  transition: background 0.3s;
}
.status-indicator.success { background: var(--success); box-shadow: 0 0 8px var(--success); }
.status-indicator.error   { background: var(--error);   box-shadow: 0 0 8px var(--error); }
.status-indicator.running { background: var(--accent3); animation: pulse 1s infinite; }

/* ── Error / Explanation Panel ─────────────────────────────────────── */
.explain-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.tab-bar {
  display: flex;
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.tab {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.8px;
  padding: 10px 18px;
  cursor: pointer;
  color: var(--text3);
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  background: none;
  border-top: none;
  border-left: none;
  border-right: none;
}
.tab:hover { color: var(--text1); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-badge {
  display: inline-block;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 8px;
  background: var(--error);
  color: #fff;
  margin-left: 5px;
  vertical-align: middle;
}

.tab-content {
  display: none;
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.tab-content.active { display: block; }

/* Error cards */
.error-card {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 12px;
  overflow: hidden;
  animation: slideIn 0.3s ease;
}
.error-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg2);
  cursor: pointer;
  user-select: none;
}
.error-type-badge {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  letter-spacing: 0.5px;
}
.badge-lexical  { background: rgba(247,194,106,0.2); color: var(--accent3); }
.badge-syntax   { background: rgba(255,94,126,0.2);  color: var(--error); }
.badge-semantic { background: rgba(77,216,224,0.2);  color: var(--accent2); }
.badge-runtime  { background: rgba(255,179,71,0.2);  color: var(--warning); }

.error-code {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text1);
}
.error-location {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text3);
  margin-left: auto;
}
.error-card-body {
  padding: 12px 14px;
}
.error-original {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text3);
  background: var(--bg0);
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 10px;
  border-left: 3px solid var(--border);
}
.error-explanation {
  font-size: 13px;
  color: var(--text1);
  line-height: 1.7;
  margin-bottom: 10px;
}
.suggestions-title {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--text3);
  text-transform: uppercase;
  margin-bottom: 6px;
}
.suggestion-item {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text2);
  margin-bottom: 4px;
  line-height: 1.5;
}
.suggestion-item::before {
  content: '→';
  color: var(--accent2);
  flex-shrink: 0;
  font-family: var(--mono);
}
.resources-list {
  margin-top: 8px;
}
.resource-item {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent);
  margin-bottom: 3px;
}
.resource-item::before { content: '📖 '; }

/* Bytecode panel */
.bytecode-pre {
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.8;
  color: var(--text2);
  background: var(--bg0);
  padding: 16px;
  border-radius: var(--radius);
  white-space: pre;
  overflow-x: auto;
}
.bytecode-pre .bc-addr { color: var(--text3); user-select: none; }
.bytecode-pre .bc-op   { color: var(--accent2); font-weight: 600; }
.bytecode-pre .bc-val  { color: var(--accent3); }

/* Success / Empty states */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--text3);
}
.empty-icon { font-size: 36px; opacity: 0.4; }
.empty-text { font-size: 13px; }

.success-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 10px;
  color: var(--success);
}
.success-icon { font-size: 48px; animation: popIn 0.4s cubic-bezier(0.34,1.56,0.64,1); }
.success-text { font-family: var(--mono); font-size: 13px; opacity: 0.8; }

/* Loader spinner */
.spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  vertical-align: middle;
  margin-right: 6px;
}

/* ── Animations ─────────────────────────────────────────────────────── */
@keyframes fadeIn   { from { opacity: 0; }               to { opacity: 1; } }
@keyframes slideIn  { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@keyframes popIn    { from { transform: scale(0.5); opacity: 0; } to { transform: scale(1); opacity: 1; } }
@keyframes spin     { to { transform: rotate(360deg); } }
@keyframes pulse    { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
@keyframes glow     { 0%,100% { box-shadow: 0 0 5px var(--accent); } 50% { box-shadow: 0 0 20px var(--accent); } }

/* ── Scrollbars ─────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text3); }
</style>
</head>
<body>

<!-- ── Top Bar ────────────────────────────────────────────────────────── -->
<div class="topbar">
  <div class="logo">CEEA</div>
  <div class="logo-sub">COMPILER IDE</div>

  <div class="topbar-spacer"></div>

  <select class="examples-select" id="examplesSelect" title="Load example program">
    <option value="">⚡ Examples...</option>
    {% for name in examples %}
    <option value="{{ name }}">{{ name }}</option>
    {% endfor %}
  </select>

  <div class="level-group">
    <button class="level-btn active" data-level="beginner">Beginner</button>
    <button class="level-btn" data-level="intermediate">Intermediate</button>
    <button class="level-btn" data-level="expert">Expert</button>
  </div>

  <button class="compile-btn" id="compileBtn">
    <span class="btn-text">▶ RUN</span>
  </button>
</div>

<!-- ── Main Layout ───────────────────────────────────────────────────── -->
<div class="layout">

  <!-- Editor -->
  <div class="editor-pane">
    <div class="pane-header">
      <span class="pane-title">editor</span>
      <span class="pane-badge" id="langBadge">CEEA-Lang</span>
      <div class="dots">
        <span class="dot dot-red"></span>
        <span class="dot dot-yellow"></span>
        <span class="dot dot-green"></span>
      </div>
    </div>
    <div class="editor-wrap">
      <textarea id="codeInput">{{ default_code }}</textarea>
    </div>
  </div>

  <!-- Results -->
  <div class="results-pane">

    <!-- Output console -->
    <div class="output-section">
      <div class="pane-header">
        <span class="pane-title">output</span>
        <span class="pane-badge" id="timeDisplay">—</span>
        <div class="dots" style="margin-left:auto;">
          <div class="status-indicator" id="statusIndicator"></div>
          <span id="statusText" style="font-family:var(--mono);font-size:11px;color:var(--text3)">ready</span>
        </div>
      </div>
      <div class="output-console" id="outputConsole">
        <div class="output-info-line"><span class="prompt">$</span> CEEA Compiler v1.0 — Write code and press ▶ RUN</div>
      </div>
    </div>

    <!-- Explanation / Bytecode tabs -->
    <div class="explain-section">
      <div class="tab-bar">
        <button class="tab active" data-tab="explanations">
          EXPLANATIONS
          <span class="tab-badge" id="errorCountBadge" style="display:none">0</span>
        </button>
        <button class="tab" data-tab="bytecode">BYTECODE</button>
        <button class="tab" data-tab="ast">ERROR CODES</button>
      </div>

      <div class="tab-content active" id="tab-explanations">
        <div class="empty-state" id="emptyState">
          <div class="empty-icon">⚡</div>
          <div class="empty-text">Compile your code to see error explanations</div>
        </div>
        <div id="explanationsContainer" style="display:none"></div>
        <div class="success-state" id="successState" style="display:none">
          <div class="success-icon">✓</div>
          <div class="success-text">Compiled successfully — no errors found</div>
        </div>
      </div>

      <div class="tab-content" id="tab-bytecode">
        <div class="empty-state" id="bytecodeEmpty">
          <div class="empty-icon">⚙</div>
          <div class="empty-text">Bytecode listing will appear after a successful compile</div>
        </div>
        <pre class="bytecode-pre" id="bytecodeContent" style="display:none"></pre>
      </div>

      <div class="tab-content" id="tab-ast">
        <div style="font-family:var(--mono);font-size:12px;color:var(--text2);line-height:2;">
          <div style="color:var(--accent2);font-weight:600;margin-bottom:12px;font-size:13px;">CEEA-Lang Error Code Reference</div>
          <table style="width:100%;border-collapse:collapse;">
            {% for row in error_ref %}
            <tr style="border-bottom:1px solid var(--border);">
              <td style="padding:6px 10px;color:var(--accent3);font-weight:600;white-space:nowrap;">{{ row[0] }}</td>
              <td style="padding:6px 10px;color:var(--error);">{{ row[1] }}</td>
              <td style="padding:6px 10px;color:var(--text2);">{{ row[2] }}</td>
            </tr>
            {% endfor %}
          </table>
        </div>
      </div>

    </div><!-- explain-section -->

  </div><!-- results-pane -->
</div><!-- layout -->

<div class="status-bar">
  <span id="globalStatus">CEEA-Lang v1.0</span>
  <span>•</span>
  <span id="cursorPos">Ln 1, Col 1</span>
  <span>•</span>
  <span id="errorSummary">No errors</span>
</div>

<script>
// ── CodeMirror setup ────────────────────────────────────────────────────────
const editor = CodeMirror.fromTextArea(document.getElementById('codeInput'), {
  mode:            'python',
  theme:           'dracula',
  lineNumbers:     true,
  matchBrackets:   true,
  autoCloseBrackets: true,
  indentUnit:      4,
  tabSize:         4,
  indentWithTabs:  false,
  lineWrapping:    false,
  autofocus:       true,
  extraKeys: {
    "Ctrl-Enter": compile,
    "Cmd-Enter":  compile,
  },
});
editor.setSize("100%", "100%");
editor.on('cursorActivity', () => {
  const c = editor.getCursor();
  document.getElementById('cursorPos').textContent = `Ln ${c.line+1}, Col ${c.ch+1}`;
});

// ── State ────────────────────────────────────────────────────────────────────
let currentLevel = 'beginner';
let currentResult = null;

// ── Level buttons ─────────────────────────────────────────────────────────────
document.querySelectorAll('.level-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.level-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentLevel = btn.dataset.level;
    if (currentResult) renderExplanations(currentResult.explanations);
  });
});

// ── Examples selector ─────────────────────────────────────────────────────────
document.getElementById('examplesSelect').addEventListener('change', async function() {
  if (!this.value) return;
  const res  = await fetch('/api/example', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ name: this.value }),
  });
  const data = await res.json();
  editor.setValue(data.code);
  this.value = '';
  resetUI();
});

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
  });
});

// ── Compile ───────────────────────────────────────────────────────────────────
async function compile() {
  const btn  = document.getElementById('compileBtn');
  const code = editor.getValue();
  if (!code.trim()) return;

  // Loading state
  btn.classList.add('loading');
  btn.querySelector('.btn-text').innerHTML = '<span class="spinner"></span>RUNNING';
  setStatus('running', 'compiling…');

  const outputEl = document.getElementById('outputConsole');
  outputEl.innerHTML = '<div class="output-info-line"><span class="prompt">$</span> Compiling…</div>';

  try {
    const res  = await fetch('/api/compile', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ code, level: currentLevel }),
    });
    const data = await res.json();
    currentResult = data;
    renderResult(data);
  } catch (e) {
    outputEl.innerHTML += `<div class="output-error-line">Network error: ${e.message}</div>`;
    setStatus('error', 'network error');
  } finally {
    btn.classList.remove('loading');
    btn.querySelector('.btn-text').textContent = '▶ RUN';
  }
}
document.getElementById('compileBtn').addEventListener('click', compile);

// ── Render ────────────────────────────────────────────────────────────────────
function renderResult(data) {
  // Time
  document.getElementById('timeDisplay').textContent =
    data.compile_time !== undefined ? `${(data.compile_time * 1000).toFixed(1)} ms` : '—';

  // Output console
  const outEl = document.getElementById('outputConsole');
  if (data.output && data.output.length) {
    outEl.innerHTML = data.output.map(
      line => `<div class="output-line"><span class="prompt">›</span> ${escHtml(line)}</div>`
    ).join('');
  } else if (data.success) {
    outEl.innerHTML = '<div class="output-info-line"><span class="prompt">$</span> (no output)</div>';
  } else {
    outEl.innerHTML = `<div class="output-error-line"><span class="prompt">✗</span> Compilation failed — see explanations →</div>`;
  }

  // Status
  if (data.success) {
    setStatus('success', `success — ${data.output ? data.output.length : 0} line(s) output`);
  } else {
    const n = data.error_count || 0;
    setStatus('error', `${n} error${n !== 1 ? 's' : ''} found`);
    document.getElementById('errorSummary').textContent =
      `${n} error${n !== 1 ? 's' : ''}`;
  }

  // Error badge on tab
  const badge = document.getElementById('errorCountBadge');
  if (data.error_count > 0) {
    badge.textContent = data.error_count;
    badge.style.display = 'inline-block';
  } else {
    badge.style.display = 'none';
  }

  // Explanations tab
  renderExplanations(data.explanations || []);

  // Bytecode
  if (data.bytecode && data.bytecode.trim() && !data.bytecode.includes('(no bytecode')) {
    document.getElementById('bytecodeEmpty').style.display = 'none';
    const pre = document.getElementById('bytecodeContent');
    pre.style.display = 'block';
    pre.innerHTML = colorizeBytecode(data.bytecode);
  } else {
    document.getElementById('bytecodeEmpty').style.display = 'flex';
    document.getElementById('bytecodeContent').style.display = 'none';
  }
}

function renderExplanations(explanations) {
  const container = document.getElementById('explanationsContainer');
  const empty     = document.getElementById('emptyState');
  const success   = document.getElementById('successState');

  if (!explanations || explanations.length === 0) {
    container.style.display = 'none';
    empty.style.display = 'none';
    success.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  success.style.display = 'none';
  container.style.display = 'block';

  container.innerHTML = explanations.map(e => buildCard(e)).join('');
}

function buildCard(e) {
  const typeClass = `badge-${e.error_type || 'syntax'}`;
  const expl = currentLevel === 'beginner'     ? e.beginner_explanation
             : currentLevel === 'intermediate' ? e.intermediate_explanation
             :                                   e.expert_explanation;

  const suggestions = (e.suggestions || []).map(
    s => `<div class="suggestion-item">${escHtml(s)}</div>`
  ).join('');
  const resources = (e.resources || []).map(
    r => `<div class="resource-item">${escHtml(r)}</div>`
  ).join('');

  return `
  <div class="error-card">
    <div class="error-card-header">
      <span class="error-type-badge ${typeClass}">${(e.error_type || '').toUpperCase()}</span>
      <span class="error-code">${escHtml(e.error_code || '')}</span>
      <span class="error-location">Ln ${e.line || 0} · Col ${e.column || 0}</span>
    </div>
    <div class="error-card-body">
      <div class="error-original">${escHtml(e.original_message || '')}</div>
      <div class="error-explanation">${escHtml(expl || '')}</div>
      ${suggestions ? `<div class="suggestions-title">How to fix</div>${suggestions}` : ''}
      ${resources ? `<div class="resources-list">${resources}</div>` : ''}
    </div>
  </div>`;
}

function colorizeBytecode(raw) {
  return raw.split('\n').map(line => {
    // Match:  0000  OPNAME  operand
    const m = line.match(/^(\s*\d{4})(\s+)(\S+)(.*)$/);
    if (m) {
      return `<span class="bc-addr">${escHtml(m[1])}</span>${m[2]}<span class="bc-op">${escHtml(m[3])}</span><span class="bc-val">${escHtml(m[4])}</span>`;
    }
    return escHtml(line);
  }).join('\n');
}

function setStatus(state, text) {
  const ind  = document.getElementById('statusIndicator');
  const txt  = document.getElementById('statusText');
  const gbl  = document.getElementById('globalStatus');
  ind.className = 'status-indicator ' + state;
  txt.textContent = text;
  gbl.textContent = 'CEEA-Lang v1.0 · ' + text;
}

function resetUI() {
  currentResult = null;
  document.getElementById('outputConsole').innerHTML =
    '<div class="output-info-line"><span class="prompt">$</span> Ready</div>';
  document.getElementById('emptyState').style.display = 'flex';
  document.getElementById('explanationsContainer').style.display = 'none';
  document.getElementById('successState').style.display = 'none';
  document.getElementById('errorCountBadge').style.display = 'none';
  document.getElementById('bytecodeEmpty').style.display = 'flex';
  document.getElementById('bytecodeContent').style.display = 'none';
  document.getElementById('timeDisplay').textContent = '—';
  document.getElementById('errorSummary').textContent = 'No errors';
  setStatus('', 'ready');
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Ctrl+Enter shortcut hint
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') compile();
});
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Error reference table
# ─────────────────────────────────────────────────────────────────────────────

ERROR_REF = [
    ("LEX001", "Lexical", "Unexpected / unrecognised character"),
    ("LEX002", "Lexical", "Lone '!' — did you mean '!='?"),
    ("LEX003", "Lexical", "Unterminated string literal"),
    ("PARSE001", "Syntax", "Unexpected token — expected something else"),
    ("PARSE002", "Syntax", "Expected function name after 'func'"),
    ("PARSE003", "Syntax", "Expected '(' after function name"),
    ("PARSE006", "Syntax", "Expected '}' to close function body"),
    ("PARSE020", "Syntax", "Expected '{' after if-condition"),
    ("PARSE030", "Syntax", "Expected '{' after while-condition"),
    ("PARSE060", "Syntax", "Unexpected token in expression"),
    ("SEM010", "Semantic", "Function declared twice"),
    ("SEM020", "Semantic", "Variable declared twice in same scope"),
    ("SEM021", "Semantic", "Type mismatch on variable initialisation"),
    ("SEM030", "Semantic", "Assignment to undeclared variable"),
    ("SEM040", "Semantic", "Use of undeclared variable"),
    ("SEM050", "Semantic", "Arithmetic on non-numeric type"),
    ("SEM070", "Semantic", "Call to undeclared function"),
    ("SEM072", "Semantic", "Wrong number of function arguments"),
    ("SEM073", "Semantic", "Function argument type mismatch"),
    ("SEM100", "Semantic", "Return type mismatch"),
    ("SEM110", "Semantic", "'break' used outside a loop"),
    ("SEM111", "Semantic", "'continue' used outside a loop"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Flask routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(
        HTML,
        examples=list(EXAMPLES.keys()),
        default_code=EXAMPLES["Hello World"],
        error_ref=ERROR_REF,
    )


@app.route("/api/compile", methods=["POST"])
def api_compile():
    data  = request.get_json(force=True)
    code  = data.get("code", "")
    level = data.get("level", "beginner")

    try:
        compiler = CEEACompiler(
            user_level=level,
            use_nlp_model=False,
            emit_bytecode=True,
        )
        result = compiler.compile(code)

        # Serialise explanations
        explanations = []
        for rep in result.explanations:
            explanations.append({
                "error_code":               rep.error_code,
                "error_type":               rep.error_type,
                "original_message":         rep.original_message,
                "line":                     rep.line,
                "column":                   rep.column,
                "beginner_explanation":     rep.beginner_explanation,
                "intermediate_explanation": rep.intermediate_explanation,
                "expert_explanation":       rep.expert_explanation,
                "suggestions":              rep.suggestions,
                "resources":                rep.resources,
                "severity":                 rep.severity,
            })

        return jsonify({
            "success":      result.success,
            "output":       result.output,
            "error_count":  result.error_count,
            "compile_time": result.compile_time,
            "explanations": explanations,
            "bytecode":     result.bytecode,
        })

    except Exception as exc:
        return jsonify({
            "success":     False,
            "output":      [],
            "error_count": 1,
            "compile_time": 0,
            "explanations": [{
                "error_code":           "INTERNAL_ERR",
                "error_type":           "runtime",
                "original_message":     str(exc),
                "line": 0, "column": 0,
                "beginner_explanation":
                    "An internal error occurred in the compiler. "
                    + traceback.format_exc(limit=3),
                "intermediate_explanation": traceback.format_exc(limit=5),
                "expert_explanation":       traceback.format_exc(),
                "suggestions": ["Check the server console for details."],
                "resources":   [],
                "severity":    "error",
            }],
            "bytecode": "",
        }), 500


@app.route("/api/example", methods=["POST"])
def api_example():
    name = request.get_json(force=True).get("name", "")
    code = EXAMPLES.get(name, "")
    return jsonify({"code": code})


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser, threading

    port = 5000
    print("=" * 55)
    print("  CEEA Compiler IDE")
    print(f"  Open your browser at:  http://localhost:{port}")
    print("  Press Ctrl+C to stop the server")
    print("=" * 55)

    # Auto-open browser after a short delay
    def _open():
        import time; time.sleep(1.0)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=False)
