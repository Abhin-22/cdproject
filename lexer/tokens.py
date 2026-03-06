"""
CEEA-Lang Token Definitions
============================
Defines all token types for the simple CEEA language.

CEEA-Lang is a minimal, educational programming language designed to
demonstrate compiler phases clearly. It supports:
  - Integer and float literals
  - String literals
  - Variables (identifiers)
  - Arithmetic, comparison, and logical operators
  - Control flow: if / else / while / for
  - Functions: func / return
  - Print statement
  - Block delimiters: { }
  - Type keywords: int, float, str, bool

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

from enum import Enum, auto


class TokenType(Enum):
    # ── Literals ────────────────────────────────────────────────────────────
    INT_LITERAL    = auto()   # e.g.  42
    FLOAT_LITERAL  = auto()   # e.g.  3.14
    STRING_LITERAL = auto()   # e.g.  "hello"
    BOOL_LITERAL   = auto()   # true / false

    # ── Identifiers ─────────────────────────────────────────────────────────
    IDENTIFIER     = auto()   # variable / function names

    # ── Type Keywords ───────────────────────────────────────────────────────
    INT            = auto()   # int
    FLOAT          = auto()   # float
    STR            = auto()   # str
    BOOL           = auto()   # bool

    # ── Control-Flow Keywords ───────────────────────────────────────────────
    IF             = auto()   # if
    ELSE           = auto()   # else
    WHILE          = auto()   # while
    FOR            = auto()   # for
    BREAK          = auto()   # break
    CONTINUE       = auto()   # continue

    # ── Function Keywords ───────────────────────────────────────────────────
    FUNC           = auto()   # func
    RETURN         = auto()   # return

    # ── I/O Keywords ────────────────────────────────────────────────────────
    PRINT          = auto()   # print

    # ── Assignment ──────────────────────────────────────────────────────────
    ASSIGN         = auto()   # =

    # ── Arithmetic Operators ─────────────────────────────────────────────────
    PLUS           = auto()   # +
    MINUS          = auto()   # -
    STAR           = auto()   # *
    SLASH          = auto()   # /
    PERCENT        = auto()   # %

    # ── Comparison Operators ─────────────────────────────────────────────────
    EQ             = auto()   # ==
    NEQ            = auto()   # !=
    LT             = auto()   # <
    LTE            = auto()   # <=
    GT             = auto()   # >
    GTE            = auto()   # >=

    # ── Logical Operators ────────────────────────────────────────────────────
    AND            = auto()   # and
    OR             = auto()   # or
    NOT            = auto()   # not

    # ── Delimiters ───────────────────────────────────────────────────────────
    LPAREN         = auto()   # (
    RPAREN         = auto()   # )
    LBRACE         = auto()   # {
    RBRACE         = auto()   # }
    LBRACKET       = auto()   # [
    RBRACKET       = auto()   # ]
    COMMA          = auto()   # ,
    SEMICOLON      = auto()   # ;
    COLON          = auto()   # :

    # ── Special ──────────────────────────────────────────────────────────────
    NEWLINE        = auto()   # \n (optional statement terminator)
    EOF            = auto()   # end of file
    ERROR          = auto()   # unrecognised character (triggers NLP explanation)


# Maps keyword strings → their TokenType
KEYWORDS: dict[str, TokenType] = {
    "int":      TokenType.INT,
    "float":    TokenType.FLOAT,
    "str":      TokenType.STR,
    "bool":     TokenType.BOOL,
    "true":     TokenType.BOOL_LITERAL,
    "false":    TokenType.BOOL_LITERAL,
    "if":       TokenType.IF,
    "else":     TokenType.ELSE,
    "while":    TokenType.WHILE,
    "for":      TokenType.FOR,
    "break":    TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "func":     TokenType.FUNC,
    "return":   TokenType.RETURN,
    "print":    TokenType.PRINT,
    "and":      TokenType.AND,
    "or":       TokenType.OR,
    "not":      TokenType.NOT,
}


class Token:
    """
    Represents a single lexical unit produced by the Lexer.

    Attributes
    ----------
    type    : TokenType   – category of this token
    value   : str         – exact text from the source
    line    : int         – 1-based line number
    column  : int         – 1-based column number
    """

    __slots__ = ("type", "value", "line", "column")

    def __init__(
        self,
        type_: TokenType,
        value: str,
        line: int = 0,
        column: int = 0,
    ) -> None:
        self.type   = type_
        self.value  = value
        self.line   = line
        self.column = column

    def __repr__(self) -> str:
        return (
            f"Token({self.type.name}, {self.value!r}, "
            f"line={self.line}, col={self.column})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Token):
            return NotImplemented
        return self.type == other.type and self.value == other.value
