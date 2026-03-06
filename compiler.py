"""
CEEA Compiler – Main Driver
============================
Orchestrates all compilation phases:

  Phase 1 – Lexical Analysis   →  Lexer  (tokens.py + lexer.py)
  Phase 2 – Syntax Analysis    →  Parser (ast_nodes.py + parser.py)
  Phase 3 – Semantic Analysis  →  SemanticAnalyser
  Phase 4 – Code Generation    →  Interpreter (tree-walking)
  Phase 5 – NLP Explanation    →  NLPExplainer (on any errors)

Usage
-----
  # From Python
  from compiler import CEEACompiler
  result = CEEACompiler().compile(source_code, user_level="beginner")

  # From CLI
  python compiler.py examples/hello.cea
  python compiler.py examples/hello.cea --level intermediate
  python compiler.py examples/hello.cea --bytecode

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from lexer.lexer import Lexer, LexerError
from parser.parser import ParseError, Parser
from parser.ast_nodes import Program
from semantic.analyser import SemanticAnalyser, SemanticError
from codegen.interpreter import Interpreter
from nlp.explainer import ErrorReport, NLPExplainer


# ─────────────────────────────────────────────────────────────────────────────
# Compilation result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompilationResult:
    """Holds everything produced by one compilation run."""
    success:       bool
    output:        List[str]            = field(default_factory=list)
    lex_errors:    List[LexerError]     = field(default_factory=list)
    parse_errors:  List[ParseError]     = field(default_factory=list)
    sem_errors:    List[SemanticError]  = field(default_factory=list)
    explanations:  List[ErrorReport]    = field(default_factory=list)
    ast:           Optional[Program]    = None
    bytecode:      str                  = ""
    compile_time:  float                = 0.0

    @property
    def all_errors(self) -> List:
        return self.lex_errors + self.parse_errors + self.sem_errors

    @property
    def error_count(self) -> int:
        return len(self.all_errors)

    def summary(self) -> str:
        lines = [
            "━" * 60,
            f"  CEEA Compiler  –  Compilation {'SUCCESSFUL ✓' if self.success else 'FAILED ✗'}",
            f"  Time: {self.compile_time*1000:.1f} ms  |  Errors: {self.error_count}",
            "━" * 60,
        ]
        if self.output:
            lines.append("  Program Output:")
            for line in self.output:
                lines.append(f"    {line}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main Compiler
# ─────────────────────────────────────────────────────────────────────────────

class CEEACompiler:
    """
    CEEA-Lang compiler.

    Parameters
    ----------
    user_level    : "beginner" | "intermediate" | "expert"
                    Controls the verbosity of NLP error explanations.
    use_nlp_model : bool
                    If True, use a Transformer model for explanations
                    (requires the NLP pipeline to be installed).
    emit_bytecode : bool
                    If True, produce a bytecode listing.
    """

    def __init__(
        self,
        user_level:    str  = "beginner",
        use_nlp_model: bool = False,
        emit_bytecode: bool = False,
    ) -> None:
        self.user_level    = user_level
        self.explainer     = NLPExplainer(use_model=use_nlp_model)
        self.emit_bytecode = emit_bytecode

    # ── Public API ────────────────────────────────────────────────────────────

    def compile(self, source: str) -> CompilationResult:
        """
        Compile and run a CEEA-Lang source string.

        Returns a CompilationResult with output, errors, and explanations.
        """
        start = time.perf_counter()
        result = CompilationResult(success=False)
        source_lines = source.splitlines()

        # ── Phase 1: Lexical Analysis ─────────────────────────────────────────
        lexer = Lexer(source)
        tokens, lex_errors = lexer.tokenise()
        result.lex_errors = lex_errors

        if lex_errors:
            result.explanations += self._explain_errors(
                [{"error_code": e.error_code,
                  "message": e.message,
                  "line": e.line,
                  "column": e.column} for e in lex_errors],
                source_lines,
            )
            # We can still try to parse after lexer errors (error recovery)

        # ── Phase 2: Syntax Analysis ──────────────────────────────────────────
        parser  = Parser(tokens)
        ast, parse_errors = parser.parse()
        result.ast         = ast
        result.parse_errors = parse_errors

        if parse_errors:
            result.explanations += self._explain_errors(
                [{"error_code": e.error_code,
                  "message": e.message,
                  "line": e.line,
                  "column": e.column} for e in parse_errors],
                source_lines,
            )

        # If there are lex or parse errors, stop here
        if lex_errors or parse_errors:
            result.compile_time = time.perf_counter() - start
            self._print_error_report(result)
            return result

        # ── Phase 3: Semantic Analysis ────────────────────────────────────────
        analyser   = SemanticAnalyser()
        sem_errors = analyser.analyse(ast)
        result.sem_errors = sem_errors

        if sem_errors:
            result.explanations += self._explain_errors(
                [{"error_code": e.error_code,
                  "message": e.message,
                  "line": e.line,
                  "column": e.column} for e in sem_errors],
                source_lines,
            )
            result.compile_time = time.perf_counter() - start
            self._print_error_report(result)
            return result

        # ── Phase 4: Code Generation / Execution ──────────────────────────────
        interpreter = Interpreter(emit_bytecode=self.emit_bytecode)
        try:
            output = interpreter.run(ast)
            result.output      = output
            result.bytecode    = interpreter.bytecode_listing()
            result.success     = True
        except Exception as exc:
            result.explanations.append(
                self.explainer.explain(
                    error_code="RUNTIME001",
                    original_message=str(exc),
                    line=0, column=0,
                )
            )

        result.compile_time = time.perf_counter() - start
        if not result.success:
            self._print_error_report(result)
        else:
            print(result.summary())
            if self.emit_bytecode:
                print("\n" + result.bytecode)
        return result

    def compile_file(self, path: str) -> CompilationResult:
        """Compile a .cea file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Source file not found: {path}")
        source = p.read_text(encoding="utf-8")
        print(f"[CEEA] Compiling: {p.name}")
        return self.compile(source)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _explain_errors(
        self,
        errors: List[dict],
        source_lines: List[str],
    ) -> List[ErrorReport]:
        return self.explainer.explain_many(errors, source_lines)

    def _print_error_report(self, result: CompilationResult) -> None:
        print(result.summary())
        print()
        for report in result.explanations:
            print(report.display(self.user_level))
            print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ceea",
        description="CEEA-Lang Compiler with NLP Error Explanation",
    )
    p.add_argument("source", nargs="?", help="Path to .cea source file")
    p.add_argument(
        "--level", "-l",
        choices=["beginner", "intermediate", "expert"],
        default="beginner",
        help="Explanation level for error messages (default: beginner)",
    )
    p.add_argument(
        "--bytecode", "-b",
        action="store_true",
        help="Print bytecode listing after successful compilation",
    )
    p.add_argument(
        "--model", "-m",
        action="store_true",
        help="Use Transformer NLP model for explanations (requires GPU setup)",
    )
    p.add_argument(
        "--eval", "-e",
        help="Evaluate inline code snippet instead of a file",
    )
    return p


def main() -> None:
    parser = _build_cli()
    args   = parser.parse_args()

    compiler = CEEACompiler(
        user_level=args.level,
        use_nlp_model=args.model,
        emit_bytecode=args.bytecode,
    )

    if args.eval:
        compiler.compile(args.eval)
    elif args.source:
        compiler.compile_file(args.source)
    else:
        # Interactive REPL
        print("CEEA-Lang Interactive Mode  (type 'exit' to quit)")
        print(f"Explanation level: {args.level}")
        print("─" * 50)
        lines: List[str] = []
        while True:
            try:
                prompt = "... " if lines else ">>> "
                line   = input(prompt)
                if line.strip() == "exit":
                    break
                if line.strip() == "":
                    if lines:
                        source = "\n".join(lines)
                        compiler.compile(source)
                        lines = []
                else:
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break


if __name__ == "__main__":
    main()
