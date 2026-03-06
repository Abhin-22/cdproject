"""
CEEA-Lang AST Node Definitions
================================
All Abstract Syntax Tree node types for CEEA-Lang.

Every node inherits from ASTNode and carries line/column info
for error reporting.

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ASTNode:
    """Base class for all AST nodes."""
    line:   int = 0
    column: int = 0

    def accept(self, visitor: "ASTVisitor") -> Any:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# Literals
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IntLiteral(ASTNode):
    value: int = 0

    def accept(self, visitor): return visitor.visit_int_literal(self)


@dataclass
class FloatLiteral(ASTNode):
    value: float = 0.0

    def accept(self, visitor): return visitor.visit_float_literal(self)


@dataclass
class StringLiteral(ASTNode):
    value: str = ""

    def accept(self, visitor): return visitor.visit_string_literal(self)


@dataclass
class BoolLiteral(ASTNode):
    value: bool = False

    def accept(self, visitor): return visitor.visit_bool_literal(self)


# ─────────────────────────────────────────────────────────────────────────────
# Identifier / Variable reference
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Identifier(ASTNode):
    name: str = ""

    def accept(self, visitor): return visitor.visit_identifier(self)


# ─────────────────────────────────────────────────────────────────────────────
# Expressions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BinaryOp(ASTNode):
    """Binary operation: left op right."""
    op:    str     = ""
    left:  ASTNode = field(default_factory=ASTNode)
    right: ASTNode = field(default_factory=ASTNode)

    def accept(self, visitor): return visitor.visit_binary_op(self)


@dataclass
class UnaryOp(ASTNode):
    """Unary operation: op operand."""
    op:      str     = ""
    operand: ASTNode = field(default_factory=ASTNode)

    def accept(self, visitor): return visitor.visit_unary_op(self)


@dataclass
class FunctionCall(ASTNode):
    """Function call: name(args...)."""
    name: str = ""
    args: List[ASTNode] = field(default_factory=list)

    def accept(self, visitor): return visitor.visit_function_call(self)


# ─────────────────────────────────────────────────────────────────────────────
# Statements
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Program(ASTNode):
    """Root node — list of top-level statements."""
    body: List[ASTNode] = field(default_factory=list)

    def accept(self, visitor): return visitor.visit_program(self)


@dataclass
class VarDeclaration(ASTNode):
    """Type annotation + optional assignment: int x = 5"""
    var_type: str           = ""
    name:     str           = ""
    value:    Optional[ASTNode] = None

    def accept(self, visitor): return visitor.visit_var_declaration(self)


@dataclass
class Assignment(ASTNode):
    """Re-assignment: x = expr"""
    name:  str     = ""
    value: ASTNode = field(default_factory=ASTNode)

    def accept(self, visitor): return visitor.visit_assignment(self)


@dataclass
class PrintStatement(ASTNode):
    """print expr"""
    expr: ASTNode = field(default_factory=ASTNode)

    def accept(self, visitor): return visitor.visit_print(self)


@dataclass
class IfStatement(ASTNode):
    """if condition { then } else { else_ }"""
    condition: ASTNode          = field(default_factory=ASTNode)
    then_body: List[ASTNode]    = field(default_factory=list)
    else_body: List[ASTNode]    = field(default_factory=list)

    def accept(self, visitor): return visitor.visit_if(self)


@dataclass
class WhileStatement(ASTNode):
    """while condition { body }"""
    condition: ASTNode       = field(default_factory=ASTNode)
    body:      List[ASTNode] = field(default_factory=list)

    def accept(self, visitor): return visitor.visit_while(self)


@dataclass
class ForStatement(ASTNode):
    """for var in range(start, end) { body }"""
    var:   str           = ""
    start: ASTNode       = field(default_factory=ASTNode)
    end:   ASTNode       = field(default_factory=ASTNode)
    body:  List[ASTNode] = field(default_factory=list)

    def accept(self, visitor): return visitor.visit_for(self)


@dataclass
class ReturnStatement(ASTNode):
    """return expr?"""
    value: Optional[ASTNode] = None

    def accept(self, visitor): return visitor.visit_return(self)


@dataclass
class BreakStatement(ASTNode):
    def accept(self, visitor): return visitor.visit_break(self)


@dataclass
class ContinueStatement(ASTNode):
    def accept(self, visitor): return visitor.visit_continue(self)


@dataclass
class FunctionDeclaration(ASTNode):
    """func name(params) { body }"""
    name:        str              = ""
    params:      List[tuple]      = field(default_factory=list)  # [(type, name), …]
    return_type: str              = "void"
    body:        List[ASTNode]    = field(default_factory=list)

    def accept(self, visitor): return visitor.visit_function_decl(self)


# ─────────────────────────────────────────────────────────────────────────────
# Visitor interface  (for semantic analyser, code-gen, pretty-printer)
# ─────────────────────────────────────────────────────────────────────────────

class ASTVisitor:
    """Base visitor — subclasses override the methods they need."""

    def visit_program(self, node: Program): pass
    def visit_int_literal(self, node: IntLiteral): pass
    def visit_float_literal(self, node: FloatLiteral): pass
    def visit_string_literal(self, node: StringLiteral): pass
    def visit_bool_literal(self, node: BoolLiteral): pass
    def visit_identifier(self, node: Identifier): pass
    def visit_binary_op(self, node: BinaryOp): pass
    def visit_unary_op(self, node: UnaryOp): pass
    def visit_function_call(self, node: FunctionCall): pass
    def visit_var_declaration(self, node: VarDeclaration): pass
    def visit_assignment(self, node: Assignment): pass
    def visit_print(self, node: PrintStatement): pass
    def visit_if(self, node: IfStatement): pass
    def visit_while(self, node: WhileStatement): pass
    def visit_for(self, node: ForStatement): pass
    def visit_return(self, node: ReturnStatement): pass
    def visit_break(self, node: BreakStatement): pass
    def visit_continue(self, node: ContinueStatement): pass
    def visit_function_decl(self, node: FunctionDeclaration): pass
