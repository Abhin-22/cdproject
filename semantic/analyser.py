"""
CEEA-Lang Semantic Analyser
============================
Walks the AST and performs:
  1. Symbol-table / scope resolution  (undeclared variables, redeclaration)
  2. Type checking                    (type mismatch in assignments / expressions)
  3. Return-path validation           (function returns correct type)
  4. Control-flow validation          (break/continue outside loop)

Errors produced here are classified as SEMANTIC errors and fed into the
NLP explanation engine.

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from parser.ast_nodes import (
    ASTNode, ASTVisitor, Assignment, BinaryOp, BoolLiteral, BreakStatement,
    ContinueStatement, FloatLiteral, ForStatement, FunctionCall,
    FunctionDeclaration, Identifier, IfStatement, IntLiteral, PrintStatement,
    Program, ReturnStatement, StringLiteral, UnaryOp, VarDeclaration,
    WhileStatement,
)


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Error
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SemanticError:
    message:    str
    line:       int
    column:     int
    error_code: str = "SEM_ERR"
    suggestion: str = ""

    def __str__(self) -> str:
        return (
            f"[Semantic Error {self.error_code}] line {self.line}, "
            f"col {self.column}: {self.message}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Symbol & Scope
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Symbol:
    name:      str
    type_name: str
    line:      int
    column:    int
    is_func:   bool = False
    param_types: List[str] = field(default_factory=list)
    return_type: str = "void"


class Scope:
    """A single lexical scope (function body, block, global)."""

    def __init__(self, parent: Optional[Scope] = None) -> None:
        self.symbols: Dict[str, Symbol] = {}
        self.parent = parent

    def declare(self, sym: Symbol) -> bool:
        """Declare a symbol in this scope. Returns False if already declared."""
        if sym.name in self.symbols:
            return False
        self.symbols[sym.name] = sym
        return True

    def lookup(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in this scope or any parent."""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Type inference helpers
# ─────────────────────────────────────────────────────────────────────────────

NUMERIC_TYPES = {"int", "float"}
ANY_TYPE = "any"   # used when type cannot be determined (after an error)


def _is_compatible(expected: str, got: str) -> bool:
    """Check if `got` is assignable to `expected`."""
    if expected == ANY_TYPE or got == ANY_TYPE:
        return True
    if expected == got:
        return True
    # int → float promotion
    if expected == "float" and got == "int":
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Analyser
# ─────────────────────────────────────────────────────────────────────────────

class SemanticAnalyser(ASTVisitor):
    """
    Walks the AST and collects semantic errors.

    Usage
    -----
        sa = SemanticAnalyser()
        errors = sa.analyse(ast)
    """

    def __init__(self) -> None:
        self.errors: List[SemanticError] = []
        self.global_scope = Scope()
        self.current_scope = self.global_scope
        self._loop_depth  = 0      # track nesting for break/continue
        self._func_return_type: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def analyse(self, program: Program) -> List[SemanticError]:
        self.visit_program(program)
        return self.errors

    # ── Scope helpers ─────────────────────────────────────────────────────────

    def _enter_scope(self) -> None:
        self.current_scope = Scope(parent=self.current_scope)

    def _exit_scope(self) -> None:
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def _add_error(
        self, msg: str, line: int, col: int,
        code: str = "SEM001", suggestion: str = ""
    ) -> None:
        self.errors.append(
            SemanticError(
                message=msg, line=line, column=col,
                error_code=code, suggestion=suggestion,
            )
        )

    # ── Visitor implementations ───────────────────────────────────────────────

    def visit_program(self, node: Program) -> str:
        for stmt in node.body:
            stmt.accept(self)
        return "void"

    # ── Declarations ──────────────────────────────────────────────────────────

    def visit_function_decl(self, node: FunctionDeclaration) -> str:
        # Register function in current (global) scope
        sym = Symbol(
            name=node.name,
            type_name="func",
            line=node.line,
            column=node.column,
            is_func=True,
            param_types=[p[0] for p in node.params],
            return_type=ANY_TYPE,   # accept any return type (inferred)
        )
        if not self.current_scope.declare(sym):
            self._add_error(
                f"Function '{node.name}' is already declared",
                node.line, node.column,
                code="SEM010",
                suggestion=f"Rename the function or remove the duplicate declaration.",
            )

        # Analyse body in new scope (child of current, so globals are visible)
        self._enter_scope()
        prev_ret_type = self._func_return_type
        self._func_return_type = ANY_TYPE  # infer from body

        # Register params
        for param_type, param_name in node.params:
            p_sym = Symbol(
                name=param_name, type_name=param_type,
                line=node.line, column=node.column,
            )
            if not self.current_scope.declare(p_sym):
                self._add_error(
                    f"Duplicate parameter name '{param_name}'",
                    node.line, node.column,
                    code="SEM011",
                    suggestion="Each parameter must have a unique name.",
                )

        for stmt in node.body:
            stmt.accept(self)

        self._func_return_type = prev_ret_type
        self._exit_scope()
        return "void"

    def visit_var_declaration(self, node: VarDeclaration) -> str:
        sym = Symbol(
            name=node.name, type_name=node.var_type,
            line=node.line, column=node.column,
        )
        if not self.current_scope.declare(sym):
            self._add_error(
                f"Variable '{node.name}' is already declared in this scope",
                node.line, node.column,
                code="SEM020",
                suggestion=f"Use a different name, or remove the duplicate declaration of '{node.name}'.",
            )

        if node.value is not None:
            value_type = node.value.accept(self)
            if not _is_compatible(node.var_type, value_type):
                self._add_error(
                    f"Type mismatch: cannot assign '{value_type}' to variable "
                    f"'{node.name}' of type '{node.var_type}'",
                    node.line, node.column,
                    code="SEM021",
                    suggestion=(
                        f"Either change the variable type to '{value_type}', "
                        f"or convert the value to '{node.var_type}'."
                    ),
                )
        return node.var_type

    def visit_assignment(self, node: Assignment) -> str:
        sym = self.current_scope.lookup(node.name)
        if sym is None:
            self._add_error(
                f"Variable '{node.name}' is used before declaration",
                node.line, node.column,
                code="SEM030",
                suggestion=(
                    f"Declare '{node.name}' before assigning to it, "
                    f"e.g.:  int {node.name} = ..."
                ),
            )
            node.value.accept(self)
            return ANY_TYPE

        value_type = node.value.accept(self)
        if not _is_compatible(sym.type_name, value_type):
            self._add_error(
                f"Type mismatch: cannot assign '{value_type}' to "
                f"'{node.name}' (declared as '{sym.type_name}')",
                node.line, node.column,
                code="SEM031",
                suggestion=(
                    f"Convert the right-hand side to '{sym.type_name}', "
                    f"or change the declaration type."
                ),
            )
        return sym.type_name

    # ── Expressions ───────────────────────────────────────────────────────────

    def visit_int_literal(self, node: IntLiteral) -> str:
        return "int"

    def visit_float_literal(self, node: FloatLiteral) -> str:
        return "float"

    def visit_string_literal(self, node: StringLiteral) -> str:
        return "str"

    def visit_bool_literal(self, node: BoolLiteral) -> str:
        return "bool"

    def visit_identifier(self, node: Identifier) -> str:
        sym = self.current_scope.lookup(node.name)
        if sym is None:
            self._add_error(
                f"Undeclared variable '{node.name}'",
                node.line, node.column,
                code="SEM040",
                suggestion=(
                    f"Declare '{node.name}' before using it: "
                    f"int {node.name} = <value>"
                ),
            )
            return ANY_TYPE
        return sym.type_name

    def visit_binary_op(self, node: BinaryOp) -> str:
        left_type  = node.left.accept(self)
        right_type = node.right.accept(self)

        arith_ops   = {"+", "-", "*", "/", "%"}
        compare_ops = {"==", "!=", "<", "<=", ">", ">="}
        logic_ops   = {"and", "or"}

        if node.op in arith_ops:
            # String concatenation with +
            if node.op == "+" and left_type == "str" and right_type == "str":
                return "str"
            if left_type not in NUMERIC_TYPES | {ANY_TYPE}:
                self._add_error(
                    f"Operator '{node.op}' cannot be applied to type '{left_type}'",
                    node.line, node.column,
                    code="SEM050",
                    suggestion=f"Arithmetic operators require int or float values.",
                )
            if right_type not in NUMERIC_TYPES | {ANY_TYPE}:
                self._add_error(
                    f"Operator '{node.op}' cannot be applied to type '{right_type}'",
                    node.line, node.column,
                    code="SEM051",
                    suggestion=f"Arithmetic operators require int or float values.",
                )
            # float promotion
            if "float" in (left_type, right_type):
                return "float"
            return "int"

        if node.op in compare_ops:
            return "bool"

        if node.op in logic_ops:
            if left_type not in ("bool", ANY_TYPE):
                self._add_error(
                    f"Logical operator '{node.op}' expects bool, got '{left_type}'",
                    node.line, node.column,
                    code="SEM055",
                    suggestion="Use boolean expressions with 'and'/'or'.",
                )
            if right_type not in ("bool", ANY_TYPE):
                self._add_error(
                    f"Logical operator '{node.op}' expects bool, got '{right_type}'",
                    node.line, node.column,
                    code="SEM056",
                    suggestion="Use boolean expressions with 'and'/'or'.",
                )
            return "bool"

        return ANY_TYPE

    def visit_unary_op(self, node: UnaryOp) -> str:
        operand_type = node.operand.accept(self)
        if node.op == "-":
            if operand_type not in NUMERIC_TYPES | {ANY_TYPE}:
                self._add_error(
                    f"Unary '-' cannot be applied to type '{operand_type}'",
                    node.line, node.column,
                    code="SEM060",
                    suggestion="Unary '-' requires an integer or float value.",
                )
            return operand_type
        if node.op == "not":
            if operand_type not in ("bool", ANY_TYPE):
                self._add_error(
                    f"'not' operator expects bool, got '{operand_type}'",
                    node.line, node.column,
                    code="SEM061",
                    suggestion="Use 'not' with a boolean expression.",
                )
            return "bool"
        return ANY_TYPE

    def visit_function_call(self, node: FunctionCall) -> str:
        sym = self.current_scope.lookup(node.name)
        if sym is None:
            self._add_error(
                f"Call to undeclared function '{node.name}'",
                node.line, node.column,
                code="SEM070",
                suggestion=f"Declare 'func {node.name}(...)' before calling it.",
            )
            for arg in node.args:
                arg.accept(self)
            return ANY_TYPE

        if not sym.is_func:
            self._add_error(
                f"'{node.name}' is a variable, not a function",
                node.line, node.column,
                code="SEM071",
                suggestion=f"You cannot call '{node.name}' as a function.",
            )

        # Arity check
        if len(node.args) != len(sym.param_types):
            self._add_error(
                f"Function '{node.name}' expects {len(sym.param_types)} argument(s), "
                f"got {len(node.args)}",
                node.line, node.column,
                code="SEM072",
                suggestion=(
                    f"Pass exactly {len(sym.param_types)} argument(s) "
                    f"to '{node.name}'."
                ),
            )

        # Argument type check
        for i, (arg, expected) in enumerate(
            zip(node.args, sym.param_types), start=1
        ):
            got = arg.accept(self)
            if not _is_compatible(expected, got):
                self._add_error(
                    f"Argument {i} of '{node.name}': expected '{expected}', got '{got}'",
                    node.line, node.column,
                    code="SEM073",
                    suggestion=f"Convert argument {i} to '{expected}'.",
                )

        return sym.return_type

    # ── Statements ────────────────────────────────────────────────────────────

    def visit_print(self, node: PrintStatement) -> str:
        node.expr.accept(self)
        return "void"

    def visit_if(self, node: IfStatement) -> str:
        cond_type = node.condition.accept(self)
        if cond_type not in ("bool", ANY_TYPE):
            self._add_error(
                f"If-condition must be boolean, got '{cond_type}'",
                node.line, node.column,
                code="SEM080",
                suggestion="Use a comparison or boolean expression as the if-condition.",
            )
        self._enter_scope()
        for stmt in node.then_body:
            stmt.accept(self)
        self._exit_scope()
        if node.else_body:
            self._enter_scope()
            for stmt in node.else_body:
                stmt.accept(self)
            self._exit_scope()
        return "void"

    def visit_while(self, node: WhileStatement) -> str:
        cond_type = node.condition.accept(self)
        if cond_type not in ("bool", ANY_TYPE):
            self._add_error(
                f"While-condition must be boolean, got '{cond_type}'",
                node.line, node.column,
                code="SEM090",
                suggestion="Use a comparison or boolean expression as the while-condition.",
            )
        self._loop_depth += 1
        self._enter_scope()
        for stmt in node.body:
            stmt.accept(self)
        self._exit_scope()
        self._loop_depth -= 1
        return "void"

    def visit_for(self, node: ForStatement) -> str:
        node.start.accept(self)
        node.end.accept(self)
        self._loop_depth += 1
        self._enter_scope()
        # Declare loop variable as int
        self.current_scope.declare(
            Symbol(name=node.var, type_name="int",
                   line=node.line, column=node.column)
        )
        for stmt in node.body:
            stmt.accept(self)
        self._exit_scope()
        self._loop_depth -= 1
        return "void"

    def visit_return(self, node: ReturnStatement) -> str:
        ret_type = "void"
        if node.value is not None:
            ret_type = node.value.accept(self)

        if self._func_return_type is not None and self._func_return_type != ANY_TYPE:
            if not _is_compatible(self._func_return_type, ret_type):
                self._add_error(
                    f"Return type mismatch: function expects "
                    f"'{self._func_return_type}', got '{ret_type}'",
                    node.line, node.column,
                    code="SEM100",
                    suggestion=(
                        f"Return a value of type '{self._func_return_type}', "
                        f"or change the function's return type."
                    ),
                )
        return ret_type

    def visit_break(self, node: BreakStatement) -> str:
        if self._loop_depth == 0:
            self._add_error(
                "'break' used outside of a loop",
                node.line, node.column,
                code="SEM110",
                suggestion="'break' can only appear inside a 'while' or 'for' loop.",
            )
        return "void"

    def visit_continue(self, node: ContinueStatement) -> str:
        if self._loop_depth == 0:
            self._add_error(
                "'continue' used outside of a loop",
                node.line, node.column,
                code="SEM111",
                suggestion="'continue' can only appear inside a 'while' or 'for' loop.",
            )
        return "void"
