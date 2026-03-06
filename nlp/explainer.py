"""
CEEA-Lang NLP Error Explanation Engine
========================================
Translates raw compiler errors (from Lexer, Parser, Semantic Analyser)
into beginner / intermediate / expert-level natural-language explanations.

Architecture
------------
  1. ErrorClassifier  – maps error code → category & sub-type
  2. ExplanationTemplates – rule-based templates (fast, always available)
  3. NLPExplainer     – public API; assembles the final multi-level explanation
  4. ErrorReport      – dataclass holding one complete error explanation

For the prototype we use rule-based template matching.
When a GPU + HuggingFace environment is available the Transformer-based
generator (transformer_explainer.py) can be plugged in as a drop-in upgrade.

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Error Report
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ErrorReport:
    """Complete explanation for a single compiler error."""
    error_code:           str
    error_type:           str          # lexical | syntax | semantic
    original_message:     str
    line:                 int
    column:               int

    beginner_explanation: str = ""
    intermediate_explanation: str = ""
    expert_explanation:   str = ""
    suggestions:          List[str] = field(default_factory=list)
    resources:            List[str] = field(default_factory=list)
    severity:             str = "error"   # error | warning | info

    def display(self, level: str = "beginner") -> str:
        """Return the explanation for the requested level."""
        level = level.lower()
        mapping = {
            "beginner":     self.beginner_explanation,
            "intermediate": self.intermediate_explanation,
            "expert":       self.expert_explanation,
        }
        expl = mapping.get(level, self.beginner_explanation)
        out = [
            f"━━━ [{self.error_type.upper()} ERROR {self.error_code}] "
            f"Line {self.line}, Col {self.column} ━━━",
            f"  Original:    {self.original_message}",
            f"  Explanation: {expl}",
        ]
        if self.suggestions:
            out.append("  How to fix:")
            for s in self.suggestions:
                out.append(f"    • {s}")
        if self.resources:
            out.append("  Learn more:")
            for r in self.resources:
                out.append(f"    → {r}")
        return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Error Template database
# ─────────────────────────────────────────────────────────────────────────────

# Each entry: error_code → dict with keys:
#   type, beginner, intermediate, expert, suggestions, resources

_TEMPLATES: Dict[str, Dict[str, Any]] = {

    # ── LEXER ──────────────────────────────────────────────────────────────
    "LEX001": {
        "type": "lexical",
        "beginner": (
            "Your code has a character that CEEA-Lang doesn't understand. "
            "Think of it like a typo that the compiler cannot read."
        ),
        "intermediate": (
            "The lexer encountered a character outside the set of valid "
            "CEEA-Lang symbols. The tokeniser cannot produce a valid token "
            "from this input."
        ),
        "expert": (
            "Lexical error LEX001: the finite-state automaton (FSA) of the "
            "lexer reached a dead state on this character. No transition "
            "function δ(state, char) maps to an accepting state. "
            "The character is not part of the CEEA-Lang alphabet Σ."
        ),
        "suggestions": [
            "Remove or replace the unexpected character.",
            "Check the list of valid operators: + - * / % == != < <= > >= = and or not",
            "Use # for comments (not // or /* */)",
        ],
        "resources": [
            "CEEA-Lang spec § 2.1 – Lexical Grammar",
            "Aho, Lam, Sethi, Ullman – 'Compilers' Ch. 3 (Lexical Analysis)",
        ],
    },

    "LEX002": {
        "type": "lexical",
        "beginner": (
            "You wrote '!' alone. In CEEA-Lang, '!' must always be followed "
            "by '=' to mean 'not equal'. Remove the '!' or write '!='."
        ),
        "intermediate": (
            "Lexical error: '!' is not a valid standalone operator in "
            "CEEA-Lang. The only valid two-character operator starting with "
            "'!' is '!=' (not-equal). Use 'not' for boolean negation."
        ),
        "expert": (
            "LEX002: The lexer DFA has a partial transition from the '!' "
            "state that only accepts '=' as the next character. Any other "
            "character triggers a rejection. CEEA-Lang does not have a "
            "unary logical-NOT operator symbol; use the keyword 'not' "
            "instead, consistent with Python-style syntax."
        ),
        "suggestions": [
            "Use '!=' for 'not equal'  (e.g.  x != 5)",
            "Use 'not' for boolean negation  (e.g.  not flag)",
        ],
        "resources": [
            "CEEA-Lang spec § 2.3 – Operators",
        ],
    },

    "LEX003": {
        "type": "lexical",
        "beginner": (
            "You started a text (string) with a double-quote '\"' but never "
            "closed it. Every string must begin AND end with a double-quote."
        ),
        "intermediate": (
            "Unterminated string literal. The lexer reached end-of-line or "
            "end-of-file before finding the closing '\"'. "
            "String tokens in CEEA-Lang cannot span multiple lines."
        ),
        "expert": (
            "LEX003: The string scanning sub-automaton entered the "
            "string-body state after consuming the opening '\"' but did not "
            "find the closing '\"' before hitting the newline or EOF sentinel. "
            "CEEA-Lang strings are single-line; for multi-line text, "
            "use explicit concatenation with '+'."
        ),
        "suggestions": [
            'Close the string with a double-quote: "your text"',
            "If you need a newline inside a string use the escape \\n",
        ],
        "resources": [
            "CEEA-Lang spec § 2.2 – String Literals",
        ],
    },

    # ── PARSER ─────────────────────────────────────────────────────────────
    "PARSE001": {
        "type": "syntax",
        "beginner": (
            "The compiler expected a specific word or symbol but found "
            "something else. Check the line for a missing bracket, "
            "keyword, or symbol."
        ),
        "intermediate": (
            "Syntax error: the parser's expected terminal did not match the "
            "current lookahead token. This usually means a missing delimiter, "
            "keyword, or wrong token order."
        ),
        "expert": (
            "PARSE001: LL(1) parse table lookup failed — the current "
            "production rule requires a specific terminal in FIRST(α) but "
            "the lookahead token is not in that set. The parser attempts "
            "panic-mode error recovery by skipping tokens to a synchronisation "
            "point (FOLLOW set boundary)."
        ),
        "suggestions": [
            "Read the error message to see what token was expected.",
            "Check for missing semicolons, braces, or parentheses.",
        ],
        "resources": [
            "CEEA-Lang spec § 3 – Syntax Grammar",
            "Aho et al. – 'Compilers' Ch. 4.4 (Top-Down Parsing)",
        ],
    },

    "PARSE002": {
        "type": "syntax",
        "beginner": (
            "After writing 'func' you need to give your function a name. "
            "Example:  func myFunction() { ... }"
        ),
        "intermediate": (
            "Function declaration: identifier expected after 'func' keyword. "
            "The parser found a non-identifier token where the function "
            "name should appear."
        ),
        "expert": (
            "PARSE002: In the production "
            "func_decl → 'func' IDENTIFIER '(' params ')' '{' body '}', "
            "the parser consumed 'func' but the lookahead is not an "
            "IDENTIFIER token. This is a First/Follow set violation."
        ),
        "suggestions": [
            "Add a valid function name after 'func', e.g.:  func greet(...)",
            "Function names must start with a letter or underscore.",
        ],
        "resources": ["CEEA-Lang spec § 4.1 – Function Declarations"],
    },

    "PARSE003": {
        "type": "syntax",
        "beginner": (
            "After the function name you need opening parenthesis '('. "
            "Example:  func add(int a, int b) { ... }"
        ),
        "intermediate": (
            "Expected '(' to begin parameter list. The grammar requires "
            "'(' immediately after the function identifier."
        ),
        "expert": (
            "PARSE003: First(params) starts with '('. The LL(1) parser "
            "expects '(' as the next terminal after the function IDENTIFIER "
            "token. Check for missing or mis-placed parenthesis."
        ),
        "suggestions": [
            "Add '(' after the function name:  func myFunc(...) { }",
        ],
        "resources": ["CEEA-Lang spec § 4.1 – Function Declarations"],
    },

    "PARSE020": {
        "type": "syntax",
        "beginner": (
            "After an 'if' condition you need an opening brace '{' to start "
            "the block of code that runs when the condition is true."
        ),
        "intermediate": (
            "Syntax error in if-statement: '{' expected after the condition "
            "expression. CEEA-Lang does not support single-line if without braces."
        ),
        "expert": (
            "PARSE020: In the production "
            "if_stmt → 'if' expression '{' body '}', the parser "
            "consumed the condition expression but the lookahead is not '{'. "
            "CEEA-Lang requires mandatory braces for all control-flow blocks."
        ),
        "suggestions": [
            "Add '{' after the if condition:  if x > 0 { ... }",
        ],
        "resources": ["CEEA-Lang spec § 4.3 – If Statements"],
    },

    "PARSE030": {
        "type": "syntax",
        "beginner": (
            "After the 'while' condition you need '{' to open the loop body."
        ),
        "intermediate": (
            "'{' expected after while-condition. CEEA-Lang requires explicit "
            "braces around loop bodies."
        ),
        "expert": (
            "PARSE030: The while_stmt production requires '{' after the "
            "condition expression. Lookahead mismatch triggers error recovery."
        ),
        "suggestions": ["Add '{' after the while condition:  while x < 10 { ... }"],
        "resources": ["CEEA-Lang spec § 4.4 – While Loops"],
    },

    "PARSE060": {
        "type": "syntax",
        "beginner": (
            "The compiler found something it didn't expect in the middle of "
            "an expression. Check for typos or missing values."
        ),
        "intermediate": (
            "Unexpected token in expression. The parser expected a value "
            "(number, string, identifier) or '(' but found something else."
        ),
        "expert": (
            "PARSE060: In the primary production, the parser's FIRST set "
            "includes {INT, FLOAT, STRING, BOOL, IDENTIFIER, LPAREN}. "
            "The current lookahead is not in this set, causing a parse error. "
            "Panic-mode recovery advances to the next synchronisation point."
        ),
        "suggestions": [
            "Make sure every expression has a valid value on the right-hand side.",
            "Check for missing variable names or literal values.",
        ],
        "resources": [
            "CEEA-Lang spec § 3.2 – Expressions",
            "Aho et al. – 'Compilers' Ch. 4.6 (Error Recovery)",
        ],
    },

    # ── SEMANTIC ────────────────────────────────────────────────────────────
    "SEM010": {
        "type": "semantic",
        "beginner": (
            "You defined a function with the same name twice. "
            "Each function must have a unique name."
        ),
        "intermediate": (
            "Semantic error: function redeclaration. The symbol table "
            "already contains an entry for this function name in the "
            "current scope."
        ),
        "expert": (
            "SEM010: During scope analysis, the symbol-table insertion for "
            "this FunctionDeclaration node failed because the name already "
            "exists in Scope.symbols[name]. CEEA-Lang does not support "
            "function overloading; each identifier must be unique per scope."
        ),
        "suggestions": [
            "Rename one of the functions.",
            "Or remove the duplicate definition.",
        ],
        "resources": ["CEEA-Lang spec § 5 – Scope Rules"],
    },

    "SEM020": {
        "type": "semantic",
        "beginner": (
            "You declared the same variable twice in the same place. "
            "You only need to declare a variable once."
        ),
        "intermediate": (
            "Variable redeclaration in the same scope. The identifier is "
            "already present in the current symbol table."
        ),
        "expert": (
            "SEM020: Symbol-table insertion rejected because the variable "
            "name already exists in the current Scope.symbols dict. "
            "CEEA-Lang uses block scoping — each new '{...}' block creates "
            "a child scope, so the same name may be reused in nested blocks."
        ),
        "suggestions": [
            "Remove the duplicate declaration.",
            "Or use a different variable name.",
        ],
        "resources": ["CEEA-Lang spec § 5 – Scope Rules"],
    },

    "SEM021": {
        "type": "semantic",
        "beginner": (
            "You're trying to store the wrong kind of value in a variable. "
            "For example, storing text in an integer variable."
        ),
        "intermediate": (
            "Type mismatch on variable initialisation. The declared type "
            "and the type of the assigned expression are incompatible. "
            "CEEA-Lang allows implicit int→float promotion only."
        ),
        "expert": (
            "SEM021: Type compatibility check failed: "
            "_is_compatible(declared_type, expr_type) returned False. "
            "CEEA-Lang's type lattice is: "
            "int <: float (only numeric promotion). "
            "All other cross-type assignments require explicit conversion."
        ),
        "suggestions": [
            "Change the variable's declared type to match the value.",
            "Or convert the value to the correct type.",
        ],
        "resources": [
            "CEEA-Lang spec § 6 – Type System",
            "Dragon Book Ch. 6.5 – Type Checking",
        ],
    },

    "SEM030": {
        "type": "semantic",
        "beginner": (
            "You're trying to use a variable that hasn't been declared yet. "
            "You must declare a variable before you can use it."
        ),
        "intermediate": (
            "Undeclared variable: the identifier was not found in the "
            "current scope or any enclosing scope during symbol-table lookup."
        ),
        "expert": (
            "SEM030: Scope.lookup(name) traversed the scope chain "
            "(current → parent → … → global) and returned None. "
            "The variable is referenced before its declaration, violating "
            "CEEA-Lang's declare-before-use rule."
        ),
        "suggestions": [
            "Declare the variable before using it:  int x = 0",
            "Check for typos in the variable name.",
        ],
        "resources": [
            "CEEA-Lang spec § 5 – Scope Rules",
            "Dragon Book Ch. 2.7 – Symbol Tables",
        ],
    },

    "SEM040": {
        "type": "semantic",
        "beginner": (
            "You used a name that hasn't been defined anywhere in your code. "
            "Check your spelling or add a declaration."
        ),
        "intermediate": (
            "Undeclared identifier. The symbol-table lookup failed for "
            "this identifier across all enclosing scopes."
        ),
        "expert": (
            "SEM040: Like SEM030 but on a read reference (Identifier node). "
            "Scope.lookup traversal returned None — the identifier has no "
            "entry in any reachable scope frame."
        ),
        "suggestions": [
            "Declare the variable:  int name = value",
            "Check for misspelling.",
        ],
        "resources": ["CEEA-Lang spec § 5 – Scope Rules"],
    },

    "SEM050": {
        "type": "semantic",
        "beginner": (
            "You're trying to do arithmetic (like + or *) on something that "
            "isn't a number. Only integers and floats can be used with "
            "arithmetic operators."
        ),
        "intermediate": (
            "Type error: arithmetic operator applied to non-numeric type. "
            "CEEA-Lang arithmetic operators require int or float operands, "
            "except '+' which also accepts str+str (concatenation)."
        ),
        "expert": (
            "SEM050/051: The operand type is not in the numeric type set "
            "{int, float}. The type-checking rule for BinaryOp arithmetic "
            "rejects non-numeric types except the special-cased str+str. "
            "Implicit coercion is not supported."
        ),
        "suggestions": [
            "Make sure both sides of the operator are numbers.",
            "Convert strings to numbers if needed.",
        ],
        "resources": [
            "CEEA-Lang spec § 6.2 – Operator Type Rules",
            "Dragon Book Ch. 6.5.3 – Type Checking Expressions",
        ],
    },

    "SEM070": {
        "type": "semantic",
        "beginner": (
            "You called a function that doesn't exist. "
            "Check the spelling or define the function first."
        ),
        "intermediate": (
            "Call to undeclared function. The symbol-table lookup for the "
            "function name returned None or a non-function symbol."
        ),
        "expert": (
            "SEM070: FunctionCall node resolution: Scope.lookup returned "
            "None for the callee name, or the Symbol found has is_func=False. "
            "Ensure the function is declared (func keyword) before the call site."
        ),
        "suggestions": [
            "Define the function before calling it:  func myFunc(...) { ... }",
            "Check for typos in the function name.",
        ],
        "resources": ["CEEA-Lang spec § 4.1 – Functions"],
    },

    "SEM072": {
        "type": "semantic",
        "beginner": (
            "You called a function with the wrong number of inputs. "
            "Check how many values the function expects."
        ),
        "intermediate": (
            "Arity mismatch: the number of arguments in the function call "
            "does not match the number of parameters in the declaration."
        ),
        "expert": (
            "SEM072: len(call.args) ≠ len(sym.param_types). "
            "CEEA-Lang uses fixed-arity functions; variadic arguments "
            "are not supported in v1. Ensure call-site arity matches "
            "the declaration."
        ),
        "suggestions": [
            "Count the parameters in the function definition.",
            "Pass exactly that many arguments in the call.",
        ],
        "resources": ["CEEA-Lang spec § 4.1 – Functions"],
    },

    "SEM100": {
        "type": "semantic",
        "beginner": (
            "Your function is supposed to give back one type of value "
            "but it's returning a different type."
        ),
        "intermediate": (
            "Return type mismatch: the expression type in the return "
            "statement is not compatible with the declared return type "
            "of the enclosing function."
        ),
        "expert": (
            "SEM100: During return-path analysis, _is_compatible("
            "func.return_type, expr_type) failed. CEEA-Lang v1 infers "
            "return types from the func declaration; implicit coercion "
            "at return boundaries is not applied (except int→float)."
        ),
        "suggestions": [
            "Make sure the returned expression matches the function's return type.",
            "Change the function return type if needed.",
        ],
        "resources": ["CEEA-Lang spec § 4.1 – Functions"],
    },

    "SEM110": {
        "type": "semantic",
        "beginner": (
            "'break' only works inside a loop. Move it inside a 'while' or 'for'."
        ),
        "intermediate": (
            "Control-flow error: 'break' statement found outside any loop body. "
            "The loop-depth counter is zero at this point."
        ),
        "expert": (
            "SEM110: The semantic analyser maintains a loop_depth counter "
            "that is incremented on WhileStatement/ForStatement entry and "
            "decremented on exit. A BreakStatement node with loop_depth=0 "
            "is semantically invalid."
        ),
        "suggestions": [
            "Place 'break' inside a while or for loop.",
        ],
        "resources": ["CEEA-Lang spec § 4.4 – Control Flow"],
    },
}

# Fallback for unknown codes
_DEFAULT_TEMPLATE: Dict[str, Any] = {
    "type": "unknown",
    "beginner": "An error occurred. Check the highlighted line for mistakes.",
    "intermediate": "Compiler error. See the error code and message for details.",
    "expert": "No expert template available for this error code. Check the source.",
    "suggestions": ["Review the error message and the relevant line of code."],
    "resources": ["CEEA-Lang Reference Manual"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Classifier
# ─────────────────────────────────────────────────────────────────────────────

class ErrorClassifier:
    """Maps an error code to its category and severity."""

    @staticmethod
    def classify(error_code: str) -> tuple[str, str]:
        """Returns (error_type, severity)."""
        prefix = error_code[:3].upper()
        if prefix == "LEX":
            return "lexical", "error"
        if prefix == "PAR":
            return "syntax", "error"
        if prefix == "SEM":
            return "semantic", "error"
        return "unknown", "error"


# ─────────────────────────────────────────────────────────────────────────────
# NLP Explainer
# ─────────────────────────────────────────────────────────────────────────────

class NLPExplainer:
    """
    Generates multi-level natural language explanations for compiler errors.

    Currently uses rule-based templates. Replace _generate_with_model()
    with a Transformer call when the NLP pipeline is ready.
    """

    def __init__(self, use_model: bool = False) -> None:
        self.use_model = use_model

    def explain(
        self,
        error_code: str,
        original_message: str,
        line: int,
        column: int,
        context: str = "",
    ) -> ErrorReport:
        """
        Build a full ErrorReport for one compiler error.

        Parameters
        ----------
        error_code       : e.g. "SEM021"
        original_message : raw error text from the compiler phase
        line, column     : source location
        context          : surrounding source code (optional)
        """
        tmpl = _TEMPLATES.get(error_code, _DEFAULT_TEMPLATE)
        error_type, severity = ErrorClassifier.classify(error_code)

        # Optionally, call a Transformer model for richer explanations
        if self.use_model:
            beg, mid, exp = self._generate_with_model(
                error_code, original_message, context
            )
        else:
            beg = self._personalise(tmpl["beginner"], original_message, context)
            mid = self._personalise(tmpl["intermediate"], original_message, context)
            exp = self._personalise(tmpl["expert"], original_message, context)

        return ErrorReport(
            error_code=error_code,
            error_type=error_type,
            original_message=original_message,
            line=line,
            column=column,
            beginner_explanation=beg,
            intermediate_explanation=mid,
            expert_explanation=exp,
            suggestions=list(tmpl.get("suggestions", [])),
            resources=list(tmpl.get("resources", [])),
            severity=severity,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _personalise(template: str, message: str, context: str) -> str:
        """Insert dynamic values into the template."""
        # Extract quoted tokens from the original message
        quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", message)
        tokens = [q[0] or q[1] for q in quoted]

        result = template
        if tokens:
            result = result.replace("{token}", tokens[0])
        return result

    def _generate_with_model(
        self, error_code: str, message: str, context: str
    ) -> tuple[str, str, str]:
        """
        Placeholder for Transformer-based explanation generation.

        Replace this method with actual HuggingFace Transformers call:

            from transformers import pipeline
            generator = pipeline("text2text-generation",
                                 model="your-finetuned-T5-model")
            prompt = f"Explain compiler error {error_code}: {message}\\nContext: {context}"
            result = generator(prompt, max_length=200)
            ...
        """
        tmpl = _TEMPLATES.get(error_code, _DEFAULT_TEMPLATE)
        return (
            self._personalise(tmpl["beginner"], message, context),
            self._personalise(tmpl["intermediate"], message, context),
            self._personalise(tmpl["expert"], message, context),
        )

    def explain_many(
        self, errors: List[Dict], source_lines: List[str]
    ) -> List[ErrorReport]:
        """
        Explain a list of errors at once.

        Parameters
        ----------
        errors : list of dicts with keys:
                 error_code, message, line, column
        source_lines : the source split into lines (for context extraction)
        """
        reports: List[ErrorReport] = []
        for err in errors:
            line   = err.get("line", 0)
            col    = err.get("column", 0)
            code   = err.get("error_code", "UNKNOWN")
            msg    = err.get("message", "")

            # Grab ±2 lines of context
            start = max(0, line - 3)
            end   = min(len(source_lines), line + 2)
            context = "\n".join(
                f"  {i+1:>4} | {source_lines[i]}"
                for i in range(start, end)
            )

            reports.append(self.explain(code, msg, line, col, context))
        return reports
