"""
CEEA-Lang Lexer (Tokeniser)
============================
Converts raw source text → a stream of Token objects.

Token categories handled:
  • Whitespace / Comments  – skipped (# line comments)
  • Integer & Float literals
  • String literals  (double-quoted)
  • Boolean literals (true / false)
  • Keywords          (if, else, while, …)
  • Identifiers       (variable / function names)
  • Operators         (+ - * / % == != < <= > >= = and or not)
  • Delimiters        ( ) { } [ ] , ; :
  • ERROR token       for any unrecognised character

Usage
-----
    from lexer.lexer import Lexer
    tokens, errors = Lexer(source_code).tokenise()

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from lexer.tokens import KEYWORDS, Token, TokenType


# ─────────────────────────────────────────────────────────────────────────────
# Error dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LexerError:
    """Describes a single lexical error."""
    message:     str
    line:        int
    column:      int
    bad_char:    str
    error_code:  str = "LEX_ERR"
    suggestion:  str = ""

    def __str__(self) -> str:
        return (
            f"[Lexer Error {self.error_code}] line {self.line}, "
            f"col {self.column}: {self.message} (got {self.bad_char!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Lexer
# ─────────────────────────────────────────────────────────────────────────────

class Lexer:
    """
    Lexer for CEEA-Lang.

    Parameters
    ----------
    source : str
        Complete source code string.
    """

    def __init__(self, source: str) -> None:
        self.source:  str   = source
        self.pos:     int   = 0          # current character index
        self.line:    int   = 1          # current line (1-based)
        self.column:  int   = 1          # current column (1-based)

        self.tokens: List[Token]      = []
        self.errors: List[LexerError] = []

    # ── Public API ───────────────────────────────────────────────────────────

    def tokenise(self) -> Tuple[List[Token], List[LexerError]]:
        """Run the lexer and return (tokens, errors)."""
        while not self._at_end():
            self._scan_token()

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens, self.errors

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _at_end(self) -> bool:
        return self.pos >= len(self.source)

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.source):
            return "\0"
        return self.source[idx]

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line  += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _match(self, expected: str) -> bool:
        """Consume the next character only if it equals *expected*."""
        if self._at_end() or self._peek() != expected:
            return False
        self._advance()
        return True

    def _add_token(
        self,
        type_: TokenType,
        value: str,
        line: int | None = None,
        col: int | None = None,
    ) -> None:
        self.tokens.append(
            Token(type_, value, line or self.line, col or self.column)
        )

    def _add_error(
        self,
        message: str,
        bad_char: str,
        error_code: str = "LEX001",
        suggestion: str = "",
    ) -> None:
        err = LexerError(
            message=message,
            line=self.line,
            column=self.column,
            bad_char=bad_char,
            error_code=error_code,
            suggestion=suggestion,
        )
        self.errors.append(err)
        # Also produce an ERROR token so the parser can skip gracefully
        self._add_token(TokenType.ERROR, bad_char)

    # ── Main dispatch ────────────────────────────────────────────────────────

    def _scan_token(self) -> None:
        start_line = self.line
        start_col  = self.column
        ch = self._advance()

        # ── Whitespace (skip) ──────────────────────────────────────────────
        if ch in (" ", "\t", "\r", "\n"):
            return

        # ── Comments  (# to end of line) ──────────────────────────────────
        if ch == "#":
            while not self._at_end() and self._peek() != "\n":
                self._advance()
            return

        # ── String literals ────────────────────────────────────────────────
        if ch == '"':
            self._scan_string(start_line, start_col)
            return

        # ── Numeric literals ───────────────────────────────────────────────
        if ch.isdigit():
            self._scan_number(ch, start_line, start_col)
            return

        # ── Identifiers / Keywords ─────────────────────────────────────────
        if ch.isalpha() or ch == "_":
            self._scan_identifier(ch, start_line, start_col)
            return

        # ── Two-character operators ────────────────────────────────────────
        if ch == "=":
            if self._match("="):
                self._add_token(TokenType.EQ, "==", start_line, start_col)
            else:
                self._add_token(TokenType.ASSIGN, "=", start_line, start_col)
            return

        if ch == "!":
            if self._match("="):
                self._add_token(TokenType.NEQ, "!=", start_line, start_col)
            else:
                self._add_error(
                    "Expected '=' after '!'",
                    "!",
                    error_code="LEX002",
                    suggestion="Did you mean '!='?",
                )
            return

        if ch == "<":
            if self._match("="):
                self._add_token(TokenType.LTE, "<=", start_line, start_col)
            else:
                self._add_token(TokenType.LT, "<", start_line, start_col)
            return

        if ch == ">":
            if self._match("="):
                self._add_token(TokenType.GTE, ">=", start_line, start_col)
            else:
                self._add_token(TokenType.GT, ">", start_line, start_col)
            return

        # ── Single-character operators ─────────────────────────────────────
        single_map = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "%": TokenType.PERCENT,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
            ":": TokenType.COLON,
        }

        if ch in single_map:
            self._add_token(single_map[ch], ch, start_line, start_col)
            return

        # ── Unrecognised character ─────────────────────────────────────────
        self._add_error(
            f"Unexpected character '{ch}'",
            ch,
            error_code="LEX001",
            suggestion=(
                "Check if this character belongs here. "
                "CEEA-Lang supports: letters, digits, "
                "operators (+,-,*,/,%), and delimiters ( ) { } [ ] , ; :"
            ),
        )

    # ── Sub-scanners ─────────────────────────────────────────────────────────

    def _scan_string(self, start_line: int, start_col: int) -> None:
        """Scan a double-quoted string literal."""
        chars: List[str] = []
        while not self._at_end() and self._peek() != '"':
            if self._peek() == "\n":
                self._add_error(
                    "Unterminated string literal (newline inside string)",
                    '"',
                    error_code="LEX003",
                    suggestion='Close the string with a double-quote (") before the newline.',
                )
                return
            # Simple escape sequences
            if self._peek() == "\\" and self._peek(1) in ('"', "\\", "n", "t"):
                self._advance()  # consume backslash
                esc = self._advance()
                chars.append({"n": "\n", "t": "\t"}.get(esc, esc))
            else:
                chars.append(self._advance())

        if self._at_end():
            self._add_error(
                "Unterminated string literal (reached end of file)",
                '"',
                error_code="LEX003",
                suggestion='Add a closing double-quote (") to end the string.',
            )
            return

        self._advance()  # consume closing "
        self._add_token(
            TokenType.STRING_LITERAL,
            "".join(chars),
            start_line,
            start_col,
        )

    def _scan_number(self, first: str, start_line: int, start_col: int) -> None:
        """Scan an integer or float literal."""
        digits = [first]
        while self._peek().isdigit():
            digits.append(self._advance())

        if self._peek() == "." and self._peek(1).isdigit():
            digits.append(self._advance())  # consume '.'
            while self._peek().isdigit():
                digits.append(self._advance())
            self._add_token(
                TokenType.FLOAT_LITERAL,
                "".join(digits),
                start_line,
                start_col,
            )
        else:
            self._add_token(
                TokenType.INT_LITERAL,
                "".join(digits),
                start_line,
                start_col,
            )

    def _scan_identifier(
        self, first: str, start_line: int, start_col: int
    ) -> None:
        """Scan an identifier or keyword."""
        chars = [first]
        while self._peek().isalnum() or self._peek() == "_":
            chars.append(self._advance())
        word = "".join(chars)

        token_type = KEYWORDS.get(word, TokenType.IDENTIFIER)

        # Bool literals carry 'true'/'false' as value
        if token_type == TokenType.BOOL_LITERAL:
            self._add_token(token_type, word, start_line, start_col)
        else:
            self._add_token(token_type, word, start_line, start_col)


# ─────────────────────────────────────────────────────────────────────────────
# Quick standalone test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = """
# Simple CEEA-Lang program
func add(int a, int b) {
    return a + b
}

int result = add(3, 4)
print result
"""
    lexer = Lexer(sample)
    tokens, errors = lexer.tokenise()
    for t in tokens:
        print(t)
    if errors:
        print("\n--- ERRORS ---")
        for e in errors:
            print(e)
