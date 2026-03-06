"""
CEEA-Lang Code Generator (Tree-Walking Interpreter)
=====================================================
Walks a type-checked AST and executes the program directly.
This is the "back-end" of the CEEA compiler for the prototype phase.

It can also emit a simple bytecode listing for teaching purposes
(set emit_bytecode=True when instantiating).

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from parser.ast_nodes import (
    ASTVisitor, Assignment, BinaryOp, BoolLiteral, BreakStatement,
    ContinueStatement, FloatLiteral, ForStatement, FunctionCall,
    FunctionDeclaration, Identifier, IfStatement, IntLiteral, PrintStatement,
    Program, ReturnStatement, StringLiteral, UnaryOp, VarDeclaration,
    WhileStatement,
)


# ─────────────────────────────────────────────────────────────────────────────
# Control flow signals  (used as exceptions internally)
# ─────────────────────────────────────────────────────────────────────────────

class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value

class _BreakSignal(Exception):  pass
class _ContinueSignal(Exception): pass


# ─────────────────────────────────────────────────────────────────────────────
# Runtime Environment (scope)
# ─────────────────────────────────────────────────────────────────────────────

class Environment:
    def __init__(self, parent: Optional["Environment"] = None) -> None:
        self.vars: Dict[str, Any] = {}
        self.parent = parent

    def define(self, name: str, value: Any) -> None:
        self.vars[name] = value

    def get(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable '{name}'")

    def set(self, name: str, value: Any) -> None:
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent:
            self.parent.set(name, value)
            return
        raise NameError(f"Cannot assign to undeclared variable '{name}'")


# ─────────────────────────────────────────────────────────────────────────────
# Bytecode instruction (for the optional bytecode emitter)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Instruction:
    op:      str
    operand: Any = None

    def __str__(self) -> str:
        if self.operand is None:
            return self.op
        return f"{self.op:<16} {self.operand!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Interpreter / Code Generator
# ─────────────────────────────────────────────────────────────────────────────

class Interpreter(ASTVisitor):
    """
    Tree-walking interpreter for CEEA-Lang.

    Parameters
    ----------
    emit_bytecode : bool
        If True, also produce a linear bytecode listing.
    """

    def __init__(self, emit_bytecode: bool = False) -> None:
        self.global_env   = Environment()
        self.current_env  = self.global_env
        self.output:       List[str]        = []     # captured print output
        self.bytecode:     List[Instruction]= []     # optional IR listing
        self.emit_bytecode = emit_bytecode

        # Register built-in functions
        self._builtins: Dict[str, Any] = {
            "int":   int,
            "float": float,
            "str":   str,
            "bool":  bool,
            "len":   len,
        }

    # ── Emit helpers ──────────────────────────────────────────────────────────

    def _emit(self, op: str, operand: Any = None) -> None:
        if self.emit_bytecode:
            self.bytecode.append(Instruction(op, operand))

    def bytecode_listing(self) -> str:
        if not self.bytecode:
            return "(no bytecode – enable emit_bytecode=True)"
        lines = ["CEEA-Lang Bytecode Listing", "=" * 40]
        for i, instr in enumerate(self.bytecode):
            lines.append(f"  {i:04d}  {instr}")
        return "\n".join(lines)

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, program: Program) -> List[str]:
        """Execute a program and return its printed output lines."""
        self.visit_program(program)
        return self.output

    # ── Environment helpers ───────────────────────────────────────────────────

    def _enter_env(self) -> None:
        self.current_env = Environment(parent=self.current_env)

    def _exit_env(self) -> None:
        if self.current_env.parent:
            self.current_env = self.current_env.parent

    # ── Visitor: Program ──────────────────────────────────────────────────────

    def visit_program(self, node: Program) -> Any:
        self._emit("PROGRAM_START")
        for stmt in node.body:
            stmt.accept(self)
        self._emit("PROGRAM_END")

    # ── Visitor: Declarations ─────────────────────────────────────────────────

    def visit_function_decl(self, node: FunctionDeclaration) -> Any:
        self._emit("DEF_FUNC", node.name)
        # Store function object in environment
        self.current_env.define(node.name, node)

    def visit_var_declaration(self, node: VarDeclaration) -> Any:
        value = node.value.accept(self) if node.value else None
        # Type coercion
        if value is not None:
            value = self._coerce(node.var_type, value)
        self.current_env.define(node.name, value)
        self._emit("STORE", node.name)

    def visit_assignment(self, node: Assignment) -> Any:
        value = node.value.accept(self)
        self.current_env.set(node.name, value)
        self._emit("STORE", node.name)

    # ── Visitor: Expressions ──────────────────────────────────────────────────

    def visit_int_literal(self, node: IntLiteral) -> int:
        self._emit("PUSH_INT", node.value)
        return node.value

    def visit_float_literal(self, node: FloatLiteral) -> float:
        self._emit("PUSH_FLOAT", node.value)
        return node.value

    def visit_string_literal(self, node: StringLiteral) -> str:
        self._emit("PUSH_STR", node.value)
        return node.value

    def visit_bool_literal(self, node: BoolLiteral) -> bool:
        self._emit("PUSH_BOOL", node.value)
        return node.value

    def visit_identifier(self, node: Identifier) -> Any:
        value = self.current_env.get(node.name)
        self._emit("LOAD", node.name)
        return value

    def visit_binary_op(self, node: BinaryOp) -> Any:
        left  = node.left.accept(self)
        right = node.right.accept(self)
        self._emit("BINARY_OP", node.op)

        ops = {
            "+":  lambda a, b: a + b,
            "-":  lambda a, b: a - b,
            "*":  lambda a, b: a * b,
            "/":  lambda a, b: a / b if b != 0 else (_ for _ in ()).throw(
                ZeroDivisionError("Division by zero")
            ),
            "%":  lambda a, b: a % b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<":  lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">":  lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "and": lambda a, b: a and b,
            "or":  lambda a, b: a or b,
        }
        fn = ops.get(node.op)
        if fn is None:
            raise RuntimeError(f"Unknown operator: {node.op}")
        return fn(left, right)

    def visit_unary_op(self, node: UnaryOp) -> Any:
        operand = node.operand.accept(self)
        self._emit("UNARY_OP", node.op)
        if node.op == "-":
            return -operand
        if node.op == "not":
            return not operand
        raise RuntimeError(f"Unknown unary op: {node.op}")

    def visit_function_call(self, node: FunctionCall) -> Any:
        self._emit("CALL", node.name)

        # Check built-ins first
        if node.name in self._builtins:
            args = [arg.accept(self) for arg in node.args]
            return self._builtins[node.name](*args)

        func_node = self.current_env.get(node.name)
        if not isinstance(func_node, FunctionDeclaration):
            raise RuntimeError(f"'{node.name}' is not a function")

        args = [arg.accept(self) for arg in node.args]

        # Create function scope
        func_env = Environment(parent=self.global_env)
        for (param_type, param_name), arg_val in zip(func_node.params, args):
            func_env.define(param_name, self._coerce(param_type, arg_val))

        prev_env = self.current_env
        self.current_env = func_env

        return_value = None
        try:
            for stmt in func_node.body:
                stmt.accept(self)
        except _ReturnSignal as ret:
            return_value = ret.value
        finally:
            self.current_env = prev_env

        self._emit("RETURN")
        return return_value

    # ── Visitor: Statements ───────────────────────────────────────────────────

    def visit_print(self, node: PrintStatement) -> Any:
        value = node.expr.accept(self)
        line  = str(value) if not isinstance(value, bool) else ("true" if value else "false")
        self.output.append(line)
        print(line)           # also echo to real stdout
        self._emit("PRINT")

    def visit_if(self, node: IfStatement) -> Any:
        self._emit("IF_START")
        condition = node.condition.accept(self)
        if condition:
            self._emit("BRANCH_TRUE")
            self._enter_env()
            for stmt in node.then_body:
                stmt.accept(self)
            self._exit_env()
        else:
            self._emit("BRANCH_FALSE")
            if node.else_body:
                self._enter_env()
                for stmt in node.else_body:
                    stmt.accept(self)
                self._exit_env()
        self._emit("IF_END")

    def visit_while(self, node: WhileStatement) -> Any:
        self._emit("WHILE_START")
        while node.condition.accept(self):
            self._enter_env()
            try:
                for stmt in node.body:
                    stmt.accept(self)
            except _BreakSignal:
                self._exit_env()
                break
            except _ContinueSignal:
                pass
            self._exit_env()
        self._emit("WHILE_END")

    def visit_for(self, node: ForStatement) -> Any:
        start = int(node.start.accept(self))
        end   = int(node.end.accept(self))
        self._emit("FOR_START")
        for i in range(start, end):
            self._enter_env()
            self.current_env.define(node.var, i)
            try:
                for stmt in node.body:
                    stmt.accept(self)
            except _BreakSignal:
                self._exit_env()
                break
            except _ContinueSignal:
                pass
            self._exit_env()
        self._emit("FOR_END")

    def visit_return(self, node: ReturnStatement) -> Any:
        value = node.value.accept(self) if node.value else None
        self._emit("RETURN")
        raise _ReturnSignal(value)

    def visit_break(self, node: BreakStatement) -> Any:
        self._emit("BREAK")
        raise _BreakSignal()

    def visit_continue(self, node: ContinueStatement) -> Any:
        self._emit("CONTINUE")
        raise _ContinueSignal()

    # ── Type coercion helper ──────────────────────────────────────────────────

    @staticmethod
    def _coerce(type_name: str, value: Any) -> Any:
        """Best-effort coercion from Python value to CEEA type."""
        try:
            if type_name == "int":   return int(value)
            if type_name == "float": return float(value)
            if type_name == "str":   return str(value)
            if type_name == "bool":  return bool(value)
        except (ValueError, TypeError):
            pass
        return value
