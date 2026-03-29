"""
server.py
==========
CodeForge main Flask server.
Routes:
  GET  /                 → IDE frontend
  POST /api/compile      → compile + error parse
  POST /api/explain      → AI / NLP error explanation
  POST /api/analyse      → lexer + parser + semantic analysis
  GET  /api/error-ref    → static error reference database
  GET  /api/hf-status    → Hugging Face token + model status
  POST /api/hf-settings  → save HF token / model to .env at runtime
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, send_from_directory
from backend.compiler     import compile_cpp, compile_java, parse_errors
from backend.lexer        import tokenise, tokens_to_dicts, gcc_syntax_check
from backend.parser       import parse as parse_ast, ast_to_mermaid
from backend.semantic     import analyse
from backend.nlp_explainer import explain_ai, explain_rules, ollama_status, hf_status, HF_RECOMMENDED_MODELS
from backend.config import cfg

app = Flask(__name__, static_folder="static")

# ── Serve frontend ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── Ollama Status ─────────────────────────────────────────────────────────────

@app.route("/api/ollama-status")
def ollama_status_route():
    return jsonify(ollama_status())


# ── Hugging Face Status & Settings ───────────────────────────────────────────

@app.route("/api/hf-status")
def hf_status_route():
    """Returns HF token readiness + current model."""
    status = hf_status()
    status["recommended_models"] = HF_RECOMMENDED_MODELS
    return jsonify(status)

@app.route("/api/hf-settings", methods=["POST"])
def hf_settings_route():
    """Save HF token and/or model to .env — takes effect immediately."""
    data  = request.get_json(force=True)
    token = data.get("token", "").strip()
    model = data.get("model", "").strip()
    results = {}

    if token:
        ok, msg = cfg.save_hf_token(token)
        results["token"] = {"ok": ok, "message": msg}

    if model:
        ok, msg = cfg.save_hf_model(model)
        results["model"] = {"ok": ok, "message": msg}

    if not token and not model:
        return jsonify({"ok": False, "message": "Nothing to save."}), 400

    overall_ok = all(v["ok"] for v in results.values())
    return jsonify({"ok": overall_ok, "results": results}), (200 if overall_ok else 400)

# ── Compile ───────────────────────────────────────────────────────────────────

@app.route("/api/compile", methods=["POST"])
def compile_route():
    data   = request.get_json(force=True)
    lang   = data.get("lang", "cpp")
    source = data.get("code", "")

    # timeout: None from client = no limit (0). Otherwise clamp 5–120 s.
    raw_timeout = data.get("timeout")
    if raw_timeout is None:
        safe_timeout = 0  # 0 = no limit in compiler.py
    else:
        safe_timeout = max(5, min(int(raw_timeout), 120))

    stdin = data.get("stdin", "") or ""

    result = compile_cpp(source, timeout=safe_timeout, stdin=stdin) if lang == "cpp" else compile_java(source, timeout=safe_timeout, stdin=stdin)

    errors = []
    if not result["success"] and result.get("stderr"):
        errors = parse_errors(result["stderr"], lang, result.get("source", source))

    return jsonify({
        "success": result["success"],
        "output":  result.get("output", []),
        "stderr":  result.get("stderr", ""),
        "tool":    result.get("tool", ""),
        "errors":  errors,
        "source":  result.get("source", source),
    })

# ── AI Explain ────────────────────────────────────────────────────────────────

@app.route("/api/explain", methods=["POST"])
def explain_route():
    data   = request.get_json(force=True)
    errors = data.get("errors", [])
    source = data.get("source", "")
    level  = data.get("level", "beginner")
    lang   = data.get("lang", "cpp")

    prefer_ollama = data.get("prefer_ollama", True)
    ollama_model  = data.get("ollama_model", None)
    hf_model      = data.get("hf_model", None)

    if not errors:
        return jsonify({"explanations": [], "ai": False})

    # Always guarantee NLP explanations — even if the AI call raises unexpectedly.
    try:
        explanations, used_ai = explain_ai(errors, source, lang, level,
                                           prefer_ollama=prefer_ollama,
                                           ollama_model=ollama_model,
                                           hf_model=hf_model)
    except Exception:
        explanations, used_ai = explain_rules(errors, lang, level), False

    # Safety net: if any explanation slot is missing or empty, fill it with
    # the rule-based result so no error card is ever left without human text.
    rule_fallbacks = explain_rules(errors, lang, level)
    final = []
    for i, exp in enumerate(explanations):
        fb = rule_fallbacks[i] if i < len(rule_fallbacks) else {}
        if not exp or not (exp.get("explanation") or exp.get("fix")):
            final.append(fb)
        else:
            final.append(exp)
    # Fill any missing slots if explanations list was shorter than errors list
    for i in range(len(final), len(errors)):
        final.append(rule_fallbacks[i] if i < len(rule_fallbacks) else {
            "title": "Compiler Error",
            "explanation": errors[i].get("raw", "Unknown error"),
            "fix": "Check the flagged line for typos or missing syntax.",
            "fixed_line": errors[i].get("source_line", ""),
        })

    return jsonify({"explanations": final, "ai": used_ai})

# ── Analyse (lexer + AST + symbols) ──────────────────────────────────────────

@app.route("/api/analyse", methods=["POST"])
def analyse_route():
    data   = request.get_json(force=True)
    source = data.get("code", "")
    lang   = data.get("lang", "cpp")
    level  = data.get("level", "beginner")

    # ── Real compiler syntax-only pass (subprocess → g++ / javac) ────────────
    syntax = gcc_syntax_check(source, lang)

    # Convert GCC diagnostics into the same error format used by /api/compile
    src_lines = source.splitlines()
    gcc_errors = []
    for d in syntax.get("diagnostics", []):
        lineno = d.get("line", 0)
        src_line = src_lines[lineno - 1].strip() if 0 < lineno <= len(src_lines) else ""
        gcc_errors.append({
            "line":        lineno,
            "column":      d.get("col", 0),
            "severity":    d.get("severity", "error"),
            "raw":         d.get("message", ""),
            "source_line": src_line,
        })

    # ── NLP explanations for any syntax errors found by GCC ──────────────────
    syntax_explanations = []
    used_ai = False
    if gcc_errors:
        try:
            syntax_explanations, used_ai = explain_ai(gcc_errors, source, lang, level, prefer_ollama=True)
        except Exception:
            syntax_explanations, used_ai = explain_rules(gcc_errors, lang, level), False

        # Safety net: fill any empty/missing slots with rule-based NLP
        rule_fb = explain_rules(gcc_errors, lang, level)
        filled = []
        for i, exp in enumerate(syntax_explanations):
            fb = rule_fb[i] if i < len(rule_fb) else {}
            if not exp or not (exp.get("explanation") or exp.get("fix")):
                filled.append(fb)
            else:
                filled.append(exp)
        for i in range(len(filled), len(gcc_errors)):
            filled.append(rule_fb[i] if i < len(rule_fb) else {
                "title": "Compiler Error",
                "explanation": gcc_errors[i].get("raw", "Unknown error"),
                "fix": "Check the flagged line.",
                "fixed_line": gcc_errors[i].get("source_line", ""),
            })
        syntax_explanations = filled

    # ── Token display (structural, for UI panel) ──────────────────────────────
    tokens   = tokens_to_dicts(tokenise(source, lang))

    # ── AST + semantic analysis ───────────────────────────────────────────────
    ast      = parse_ast(source, lang)
    mermaid  = ast_to_mermaid(ast)
    semantic = analyse(source, lang)

    return jsonify({
        "tokens":              tokens,
        "ast":                 ast,
        "mermaid":             mermaid,
        "symbols":             semantic["symbols"],
        "warnings":            semantic["warnings"],
        "imports":             semantic["imports"],
        # New: GCC syntax-only results + NLP explanations
        "syntax_ok":           syntax.get("ok"),
        "syntax_errors":       gcc_errors,
        "syntax_explanations": syntax_explanations,
        "syntax_ai":           used_ai,
        "gcc_available":       syntax.get("ok") is not None,
    })

# ── Error Reference ───────────────────────────────────────────────────────────

@app.route("/api/error-ref")
def error_ref_route():
    return jsonify(ERROR_REFERENCE)

ERROR_REFERENCE = [
    {
        "id": "E001", "tag": "Missing Semicolon",
        "pattern": "expected ';' before",
        "languages": ["C++", "Java"],
        "description": "Every statement must end with a semicolon `;`.",
        "example_bad":  "int x = 5\ncout << x;",
        "example_good": "int x = 5;\ncout << x;",
        "tip": "The error is reported one line AFTER the missing semicolon.",
    },
    {
        "id": "E002", "tag": "Undeclared Identifier",
        "pattern": "was not declared in this scope",
        "languages": ["C++"],
        "description": "You used a name that hasn't been declared.",
        "example_bad":  "cout << myVariable;",
        "example_good": "int myVariable = 42;\ncout << myVariable;",
        "tip": "Declare variables before you use them. Check for typos — C++ is case-sensitive.",
    },
    {
        "id": "E003", "tag": "Type Mismatch",
        "pattern": "invalid conversion from / incompatible types",
        "languages": ["C++", "Java"],
        "description": "You assigned the wrong type of value to a variable.",
        "example_bad":  'int x = "hello";',
        "example_good": 'string x = "hello";',
        "tip": "Use int/double for numbers, string/String for text, bool/boolean for true/false.",
    },
    {
        "id": "E004", "tag": "Missing Closing Brace",
        "pattern": "expected '}' at end / reached end of file",
        "languages": ["C++", "Java"],
        "description": "An opened `{` block was never closed with `}`.",
        "example_bad":  "int main() {\n    cout << 1;\n// missing }",
        "example_good": "int main() {\n    cout << 1;\n}",
        "tip": "Count your { and } — they must be equal.",
    },
    {
        "id": "E005", "tag": "Wrong Argument Count",
        "pattern": "too few / too many arguments",
        "languages": ["C++", "Java"],
        "description": "You called a function with the wrong number of arguments.",
        "example_bad":  "int add(int a, int b) {...}\nadd(1);",
        "example_good": "add(1, 2);",
        "tip": "Count the parameters in the function definition and match them in the call.",
    },
    {
        "id": "E006", "tag": "Undefined Reference",
        "pattern": "undefined reference to",
        "languages": ["C++"],
        "description": "A function is declared but its body is never defined.",
        "example_bad":  "void foo();\nint main() { foo(); }",
        "example_good": "void foo() { cout << 42; }\nint main() { foo(); }",
        "tip": "Make sure every declared function also has a body, or link the correct library.",
    },
    {
        "id": "E007", "tag": "Missing Return Value",
        "pattern": "control reaches end of non-void function",
        "languages": ["C++"],
        "description": "A function declared to return a value doesn't always do so.",
        "example_bad":  "int getX() {\n    int x = 5;\n    // forgot return\n}",
        "example_good": "int getX() {\n    int x = 5;\n    return x;\n}",
        "tip": "Every code path through a non-void function must have a return statement.",
    },
    {
        "id": "E008", "tag": "Cannot Find Symbol (Java)",
        "pattern": "cannot find symbol",
        "languages": ["Java"],
        "description": "Java can't find a variable, method, or class you referenced.",
        "example_bad":  'System.out.println(messge);',
        "example_good": 'System.out.println(message);',
        "tip": "Check for typos. Java is case-sensitive. Make sure imports are correct.",
    },
    {
        "id": "E009", "tag": "Array Out of Bounds",
        "pattern": "array subscript / index out of range",
        "languages": ["C++", "Java"],
        "description": "You're accessing an array index that doesn't exist.",
        "example_bad":  "int arr[3] = {1,2,3};\ncout << arr[5];",
        "example_good": "cout << arr[2]; // last valid index is size-1",
        "tip": "Valid indices are 0 to (array_size - 1). Never access beyond that.",
    },
    {
        "id": "E010", "tag": "Division by Zero",
        "pattern": "division by zero",
        "languages": ["C++", "Java"],
        "description": "Dividing by zero is undefined and will crash your program.",
        "example_bad":  "int result = 10 / 0;",
        "example_good": "if (divisor != 0) result = 10 / divisor;",
        "tip": "Always guard divisions with a zero-check.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n⚡ CodeForge running → http://localhost:{port}\n")
    app.run(debug=True, port=port, use_reloader=False)
