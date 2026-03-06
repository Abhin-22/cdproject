"""
CEEA-Lang Parser
=================
Recursive-descent parser.  Consumes a token stream (from the Lexer) and
builds an Abstract Syntax Tree (AST).

Grammar (simplified BNF)
------------------------
program        → declaration* EOF
declaration    → func_decl | statement
func_decl      → "func" IDENT "(" params? ")" "{" statement* "}"
params         → param ("," param)*
param          → TYPE IDENT
statement      → var_decl | assign | print_stmt | if_stmt
               | while_stmt | for_stmt | return_stmt
               | break_stmt | continue_stmt | expr_stmt
var_decl       → TYPE IDENT ("=" expression)? ";"?
assign         → IDENT "=" expression ";"?
print_stmt     → "print" expression ";"?
if_stmt        → "if" expression "{" statement* "}" ("else" "{" statement* "}")?
while_stmt     → "while" expression "{" statement* "}"
for_stmt       → "for" IDENT "in" "range" "(" expression "," expression ")" "{" statement* "}"
return_stmt    → "return" expression? ";"?
expression     → or_expr
or_expr        → and_expr ("or" and_expr)*
and_expr       → not_expr ("and" not_expr)*
not_expr       → "not" not_expr | comparison
comparison     → addition (("==" | "!=" | "<" | "<=" | ">" | ">=") addition)*
addition       → multiplication (("+" | "-") multiplication)*
multiplication → unary (("*" | "/" | "%") unary)*
unary          → "-" unary | primary
primary        → INT | FLOAT | STRING | BOOL | IDENT | call | "(" expression ")"
call           → IDENT "(" args? ")"
args           → expression ("," expression)*

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from lexer.tokens import Token, TokenType
from parser.ast_nodes import (
    ASTNode, Assignment, BinaryOp, BoolLiteral, BreakStatement,
    ContinueStatement, FloatLiteral, ForStatement, FunctionCall,
    FunctionDeclaration, Identifier, IfStatement, IntLiteral,
    PrintStatement, Program, ReturnStatement, StringLiteral, UnaryOp,
    VarDeclaration, WhileStatement,
)


# ─────────────────────────────────────────────────────────────────────────────
# Parse error
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ParseError:
    message:    str
    line:       int
    column:     int
    token:      str
    error_code: str = "PARSE_ERR"
    suggestion: str = ""

    def __str__(self) -> str:
        return (
            f"[Parser Error {self.error_code}] line {self.line}, "
            f"col {self.column}: {self.message} (at {self.token!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Type keywords set
# ─────────────────────────────────────────────────────────────────────────────

TYPE_TOKENS = {TokenType.INT, TokenType.FLOAT, TokenType.STR, TokenType.BOOL}


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

class Parser:
    """
    Recursive-descent parser for CEEA-Lang.

    Parameters
    ----------
    tokens : List[Token]
        Output from Lexer.tokenise() (must include EOF token).
    """

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens: List[Token] = tokens
        self.pos:    int         = 0
        self.errors: List[ParseError] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(self) -> Tuple[Program, List[ParseError]]:
        body: List[ASTNode] = []
        while not self._at_end():
            node = self._declaration()
            if node is not None:
                body.append(node)
        program = Program(body=body)
        return program, self.errors

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _peek(self, offset: int = 0) -> Token:
        idx = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _match(self, *types: TokenType) -> bool:
        if self._check(*types):
            self._advance()
            return True
        return False

    def _expect(
        self,
        type_: TokenType,
        error_msg: str,
        error_code: str = "PARSE001",
        suggestion: str = "",
    ) -> Optional[Token]:
        if self._check(type_):
            return self._advance()
        tok = self._peek()
        self.errors.append(
            ParseError(
                message=error_msg,
                line=tok.line,
                column=tok.column,
                token=tok.value,
                error_code=error_code,
                suggestion=suggestion,
            )
        )
        return None

    def _synchronise(self) -> None:
        """Skip tokens until a safe restart point."""
        self._advance()
        sync_types = {
            TokenType.FUNC, TokenType.INT, TokenType.FLOAT,
            TokenType.STR, TokenType.BOOL, TokenType.IF,
            TokenType.WHILE, TokenType.FOR, TokenType.RETURN,
            TokenType.PRINT, TokenType.EOF,
        }
        while not self._at_end():
            if self._peek().type in sync_types:
                return
            self._advance()

    # ── Grammar rules ─────────────────────────────────────────────────────────

    def _declaration(self) -> Optional[ASTNode]:
        try:
            if self._check(TokenType.FUNC):
                return self._func_decl()
            return self._statement()
        except Exception as exc:
            tok = self._peek()
            self.errors.append(
                ParseError(
                    message=f"Unexpected parse error: {exc}",
                    line=tok.line,
                    column=tok.column,
                    token=tok.value,
                    error_code="PARSE999",
                )
            )
            self._synchronise()
            return None

    # ── Function declaration ───────────────────────────────────────────────────

    def _func_decl(self) -> FunctionDeclaration:
        tok = self._advance()          # consume 'func'
        name_tok = self._expect(
            TokenType.IDENTIFIER,
            "Expected function name after 'func'",
            "PARSE002",
            "Provide a name for your function, e.g.:  func myFunction(...) { ... }",
        )
        name = name_tok.value if name_tok else "<unknown>"

        self._expect(
            TokenType.LPAREN,
            "Expected '(' after function name",
            "PARSE003",
            f"Add parentheses after the name: func {name}(...)",
        )

        params = self._params()

        self._expect(
            TokenType.RPAREN,
            "Expected ')' to close parameter list",
            "PARSE004",
            "Close the parameter list with ')'",
        )

        self._expect(
            TokenType.LBRACE,
            "Expected '{' to start function body",
            "PARSE005",
            "Add '{' before the function body",
        )

        body = self._block()

        self._expect(
            TokenType.RBRACE,
            "Expected '}' to close function body",
            "PARSE006",
            "Add '}' after the function body",
        )

        return FunctionDeclaration(
            name=name, params=params, body=body,
            line=tok.line, column=tok.column,
        )

    def _params(self) -> List[Tuple[str, str]]:
        params: List[Tuple[str, str]] = []
        if not self._check(TokenType.RPAREN) and self._peek().type in TYPE_TOKENS:
            params.append(self._param())
            while self._match(TokenType.COMMA):
                params.append(self._param())
        return params

    def _param(self) -> Tuple[str, str]:
        type_tok = self._advance()
        name_tok = self._expect(
            TokenType.IDENTIFIER,
            f"Expected parameter name after type '{type_tok.value}'",
            "PARSE007",
            f"Write the parameter name after its type, e.g.:  {type_tok.value} paramName",
        )
        return (type_tok.value, name_tok.value if name_tok else "<param>")

    # ── Block ─────────────────────────────────────────────────────────────────

    def _block(self) -> List[ASTNode]:
        stmts: List[ASTNode] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            stmt = self._statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    # ── Statements ────────────────────────────────────────────────────────────

    def _statement(self) -> Optional[ASTNode]:
        # Skip stray semicolons / newlines
        while self._match(TokenType.SEMICOLON):
            pass
        if self._at_end() or self._check(TokenType.RBRACE):
            return None

        tok = self._peek()

        if tok.type in TYPE_TOKENS:
            return self._var_decl()
        if tok.type == TokenType.IF:
            return self._if_stmt()
        if tok.type == TokenType.WHILE:
            return self._while_stmt()
        if tok.type == TokenType.FOR:
            return self._for_stmt()
        if tok.type == TokenType.RETURN:
            return self._return_stmt()
        if tok.type == TokenType.PRINT:
            return self._print_stmt()
        if tok.type == TokenType.BREAK:
            self._advance()
            self._match(TokenType.SEMICOLON)
            return BreakStatement(line=tok.line, column=tok.column)
        if tok.type == TokenType.CONTINUE:
            self._advance()
            self._match(TokenType.SEMICOLON)
            return ContinueStatement(line=tok.line, column=tok.column)

        # IDENT = expr  (assignment)
        if tok.type == TokenType.IDENTIFIER and self._peek(1).type == TokenType.ASSIGN:
            return self._assign_stmt()

        # expression statement
        expr = self._expression()
        self._match(TokenType.SEMICOLON)
        return expr

    def _var_decl(self) -> VarDeclaration:
        type_tok = self._advance()
        name_tok = self._expect(
            TokenType.IDENTIFIER,
            f"Expected variable name after type '{type_tok.value}'",
            "PARSE010",
            f"Provide a name: {type_tok.value} myVariable",
        )
        name = name_tok.value if name_tok else "<var>"
        value = None
        if self._match(TokenType.ASSIGN):
            value = self._expression()
        self._match(TokenType.SEMICOLON)
        return VarDeclaration(
            var_type=type_tok.value, name=name, value=value,
            line=type_tok.line, column=type_tok.column,
        )

    def _assign_stmt(self) -> Assignment:
        name_tok = self._advance()       # IDENT
        self._advance()                  # =
        value = self._expression()
        self._match(TokenType.SEMICOLON)
        return Assignment(
            name=name_tok.value, value=value,
            line=name_tok.line, column=name_tok.column,
        )

    def _print_stmt(self) -> PrintStatement:
        tok = self._advance()            # 'print'
        expr = self._expression()
        self._match(TokenType.SEMICOLON)
        return PrintStatement(expr=expr, line=tok.line, column=tok.column)

    def _if_stmt(self) -> IfStatement:
        tok = self._advance()            # 'if'
        condition = self._expression()
        self._expect(TokenType.LBRACE, "Expected '{' after if-condition",
                     "PARSE020", "Add '{' before the if-body")
        then_body = self._block()
        self._expect(TokenType.RBRACE, "Expected '}' to close if-body",
                     "PARSE021", "Add '}' after the if-body")
        else_body: List[ASTNode] = []
        if self._match(TokenType.ELSE):
            self._expect(TokenType.LBRACE, "Expected '{' after 'else'",
                         "PARSE022", "Add '{' before the else-body")
            else_body = self._block()
            self._expect(TokenType.RBRACE, "Expected '}' to close else-body",
                         "PARSE023", "Add '}' after the else-body")
        return IfStatement(
            condition=condition, then_body=then_body, else_body=else_body,
            line=tok.line, column=tok.column,
        )

    def _while_stmt(self) -> WhileStatement:
        tok = self._advance()            # 'while'
        condition = self._expression()
        self._expect(TokenType.LBRACE, "Expected '{' after while-condition",
                     "PARSE030", "Add '{' before the while-body")
        body = self._block()
        self._expect(TokenType.RBRACE, "Expected '}' to close while-body",
                     "PARSE031", "Add '}' after the while-body")
        return WhileStatement(
            condition=condition, body=body, line=tok.line, column=tok.column
        )

    def _for_stmt(self) -> ForStatement:
        tok = self._advance()            # 'for'
        var_tok = self._expect(
            TokenType.IDENTIFIER,
            "Expected loop variable after 'for'",
            "PARSE040",
            "Write: for i in range(start, end) { ... }",
        )
        # expect 'in'
        in_tok = self._peek()
        if in_tok.value == "in":
            self._advance()
        else:
            self.errors.append(ParseError(
                message="Expected 'in' after loop variable",
                line=in_tok.line, column=in_tok.column,
                token=in_tok.value, error_code="PARSE041",
                suggestion="Write: for i in range(0, 10) { ... }",
            ))
        # expect 'range'
        range_tok = self._peek()
        if range_tok.value == "range":
            self._advance()
        else:
            self.errors.append(ParseError(
                message="Expected 'range' after 'in'",
                line=range_tok.line, column=range_tok.column,
                token=range_tok.value, error_code="PARSE042",
                suggestion="Use range(start, end) in for loops",
            ))
        self._expect(TokenType.LPAREN, "Expected '(' after 'range'", "PARSE043")
        start = self._expression()
        self._expect(TokenType.COMMA, "Expected ',' between range arguments", "PARSE044",
                     "Write: range(start, end)")
        end = self._expression()
        self._expect(TokenType.RPAREN, "Expected ')' to close range", "PARSE045")
        self._expect(TokenType.LBRACE, "Expected '{' before for-body", "PARSE046")
        body = self._block()
        self._expect(TokenType.RBRACE, "Expected '}' after for-body", "PARSE047")
        return ForStatement(
            var=var_tok.value if var_tok else "i",
            start=start, end=end, body=body,
            line=tok.line, column=tok.column,
        )

    def _return_stmt(self) -> ReturnStatement:
        tok = self._advance()            # 'return'
        value = None
        if not self._check(TokenType.SEMICOLON) and not self._check(TokenType.RBRACE):
            value = self._expression()
        self._match(TokenType.SEMICOLON)
        return ReturnStatement(value=value, line=tok.line, column=tok.column)

    # ── Expressions (Pratt-style precedence) ──────────────────────────────────

    def _expression(self) -> ASTNode:
        return self._or_expr()

    def _or_expr(self) -> ASTNode:
        left = self._and_expr()
        while self._check(TokenType.OR):
            op = self._advance().value
            right = self._and_expr()
            left = BinaryOp(op=op, left=left, right=right,
                            line=left.line, column=left.column)
        return left

    def _and_expr(self) -> ASTNode:
        left = self._not_expr()
        while self._check(TokenType.AND):
            op = self._advance().value
            right = self._not_expr()
            left = BinaryOp(op=op, left=left, right=right,
                            line=left.line, column=left.column)
        return left

    def _not_expr(self) -> ASTNode:
        if self._check(TokenType.NOT):
            tok = self._advance()
            operand = self._not_expr()
            return UnaryOp(op="not", operand=operand,
                           line=tok.line, column=tok.column)
        return self._comparison()

    def _comparison(self) -> ASTNode:
        left = self._addition()
        cmp_tokens = {
            TokenType.EQ, TokenType.NEQ,
            TokenType.LT, TokenType.LTE,
            TokenType.GT, TokenType.GTE,
        }
        while self._peek().type in cmp_tokens:
            op = self._advance().value
            right = self._addition()
            left = BinaryOp(op=op, left=left, right=right,
                            line=left.line, column=left.column)
        return left

    def _addition(self) -> ASTNode:
        left = self._multiplication()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op = self._advance().value
            right = self._multiplication()
            left = BinaryOp(op=op, left=left, right=right,
                            line=left.line, column=left.column)
        return left

    def _multiplication(self) -> ASTNode:
        left = self._unary()
        while self._check(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._advance().value
            right = self._unary()
            left = BinaryOp(op=op, left=left, right=right,
                            line=left.line, column=left.column)
        return left

    def _unary(self) -> ASTNode:
        if self._check(TokenType.MINUS):
            tok = self._advance()
            operand = self._unary()
            return UnaryOp(op="-", operand=operand,
                           line=tok.line, column=tok.column)
        return self._primary()

    def _primary(self) -> ASTNode:
        tok = self._peek()

        if tok.type == TokenType.INT_LITERAL:
            self._advance()
            return IntLiteral(value=int(tok.value),
                              line=tok.line, column=tok.column)

        if tok.type == TokenType.FLOAT_LITERAL:
            self._advance()
            return FloatLiteral(value=float(tok.value),
                                line=tok.line, column=tok.column)

        if tok.type == TokenType.STRING_LITERAL:
            self._advance()
            return StringLiteral(value=tok.value,
                                 line=tok.line, column=tok.column)

        if tok.type == TokenType.BOOL_LITERAL:
            self._advance()
            return BoolLiteral(value=(tok.value == "true"),
                               line=tok.line, column=tok.column)

        # Grouped expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._expression()
            self._expect(
                TokenType.RPAREN,
                "Expected ')' to close parenthesised expression",
                "PARSE050",
                "Add a closing ')' after the expression",
            )
            return expr

        # Identifier or function call
        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            if self._check(TokenType.LPAREN):
                return self._finish_call(tok)
            return Identifier(name=tok.value,
                              line=tok.line, column=tok.column)

        # Error — unexpected token
        self.errors.append(
            ParseError(
                message=f"Unexpected token '{tok.value}' in expression",
                line=tok.line,
                column=tok.column,
                token=tok.value,
                error_code="PARSE060",
                suggestion=(
                    "Expected a value: integer, float, string, boolean, "
                    "variable name, or '(' expression ')'."
                ),
            )
        )
        self._advance()   # skip bad token
        return IntLiteral(value=0, line=tok.line, column=tok.column)

    def _finish_call(self, name_tok: Token) -> FunctionCall:
        self._advance()  # consume '('
        args: List[ASTNode] = []
        if not self._check(TokenType.RPAREN):
            args.append(self._expression())
            while self._match(TokenType.COMMA):
                args.append(self._expression())
        self._expect(
            TokenType.RPAREN,
            f"Expected ')' to close arguments of '{name_tok.value}'",
            "PARSE051",
            f"Add ')' after the arguments: {name_tok.value}(...)",
        )
        return FunctionCall(
            name=name_tok.value, args=args,
            line=name_tok.line, column=name_tok.column,
        )
