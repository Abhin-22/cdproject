"""
CEEA-Lang Test Suite
=====================
Tests for all compiler phases.

Run with:
    python -m pytest tests/ -v
or:
    python tests/test_compiler.py

Author: CEEA Project (Siddharth Singh, 24CSB0A72)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from lexer.lexer import Lexer
from lexer.tokens import TokenType
from parser.parser import Parser
from semantic.analyser import SemanticAnalyser
from codegen.interpreter import Interpreter
from nlp.explainer import NLPExplainer
from compiler import CEEACompiler


# ─────────────────────────────────────────────────────────────────────────────
# Lexer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLexer(unittest.TestCase):

    def _tokenise(self, src):
        tokens, errors = Lexer(src).tokenise()
        return tokens, errors

    def test_integer_literal(self):
        tokens, errors = self._tokenise("42")
        self.assertEqual(errors, [])
        self.assertEqual(tokens[0].type, TokenType.INT_LITERAL)
        self.assertEqual(tokens[0].value, "42")

    def test_float_literal(self):
        tokens, errors = self._tokenise("3.14")
        self.assertEqual(errors, [])
        self.assertEqual(tokens[0].type, TokenType.FLOAT_LITERAL)

    def test_string_literal(self):
        tokens, errors = self._tokenise('"hello world"')
        self.assertEqual(errors, [])
        self.assertEqual(tokens[0].type, TokenType.STRING_LITERAL)
        self.assertEqual(tokens[0].value, "hello world")

    def test_bool_literals(self):
        tokens, _ = self._tokenise("true false")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        self.assertIn(TokenType.BOOL_LITERAL, types)

    def test_keywords(self):
        src = "if else while for func return print int float str bool"
        tokens, errors = self._tokenise(src)
        self.assertEqual(errors, [])
        types = {t.type for t in tokens}
        self.assertIn(TokenType.IF, types)
        self.assertIn(TokenType.WHILE, types)
        self.assertIn(TokenType.FUNC, types)

    def test_operators(self):
        src = "+ - * / % == != < <= > >= ="
        tokens, errors = self._tokenise(src)
        self.assertEqual(errors, [])
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        self.assertIn(TokenType.PLUS, types)
        self.assertIn(TokenType.EQ, types)
        self.assertIn(TokenType.NEQ, types)
        self.assertIn(TokenType.LTE, types)

    def test_comment_skipped(self):
        tokens, errors = self._tokenise("# this is a comment\n42")
        self.assertEqual(errors, [])
        self.assertEqual(tokens[0].type, TokenType.INT_LITERAL)

    def test_unterminated_string(self):
        tokens, errors = self._tokenise('"unterminated')
        self.assertTrue(len(errors) > 0)
        self.assertEqual(errors[0].error_code, "LEX003")

    def test_unexpected_character(self):
        tokens, errors = self._tokenise("$")
        self.assertTrue(len(errors) > 0)
        self.assertEqual(errors[0].error_code, "LEX001")

    def test_invalid_bang(self):
        tokens, errors = self._tokenise("!x")
        self.assertTrue(len(errors) > 0)
        self.assertEqual(errors[0].error_code, "LEX002")

    def test_identifiers(self):
        tokens, errors = self._tokenise("myVar _private var123")
        self.assertEqual(errors, [])
        ident_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        self.assertEqual(len(ident_tokens), 3)

    def test_multi_line(self):
        src = "int x = 1\nint y = 2\n"
        tokens, errors = self._tokenise(src)
        self.assertEqual(errors, [])
        # Should have INT, IDENT, ASSIGN, INT_LIT × 2 + EOF
        self.assertTrue(len(tokens) > 4)

    def test_line_numbers(self):
        src = "int x\nint y"
        tokens, _ = self._tokenise(src)
        ident_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        self.assertEqual(ident_tokens[0].line, 1)
        self.assertEqual(ident_tokens[1].line, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParser(unittest.TestCase):

    def _parse(self, src):
        tokens, _ = Lexer(src).tokenise()
        ast, errors = Parser(tokens).parse()
        return ast, errors

    def test_var_declaration(self):
        ast, errors = self._parse("int x = 5")
        self.assertEqual(errors, [])
        self.assertTrue(len(ast.body) > 0)

    def test_function_declaration(self):
        src = "func add(int a, int b) { return a + b }"
        ast, errors = self._parse(src)
        self.assertEqual(errors, [])

    def test_if_else(self):
        src = "if x > 0 { print x } else { print 0 }"
        ast, errors = self._parse(src)
        # May have ident errors but structure should parse
        from parser.ast_nodes import IfStatement
        if_nodes = [n for n in ast.body if isinstance(n, IfStatement)]
        self.assertTrue(len(if_nodes) > 0)

    def test_while_loop(self):
        src = "while x < 10 { x = x + 1 }"
        ast, errors = self._parse(src)
        from parser.ast_nodes import WhileStatement
        while_nodes = [n for n in ast.body if isinstance(n, WhileStatement)]
        self.assertTrue(len(while_nodes) > 0)

    def test_for_loop(self):
        src = "for i in range(0, 5) { print i }"
        ast, errors = self._parse(src)
        from parser.ast_nodes import ForStatement
        for_nodes = [n for n in ast.body if isinstance(n, ForStatement)]
        self.assertTrue(len(for_nodes) > 0)

    def test_binary_expression(self):
        ast, errors = self._parse("int result = 3 + 4 * 2")
        self.assertEqual(errors, [])

    def test_missing_brace_error(self):
        src = "if x > 0 print x"
        ast, errors = self._parse(src)
        self.assertTrue(len(errors) > 0)

    def test_nested_calls(self):
        src = """
func double(int x) { return x * 2 }
int result = double(5)
"""
        ast, errors = self._parse(src)
        self.assertEqual(errors, [])


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Analyser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticAnalyser(unittest.TestCase):

    def _analyse(self, src):
        tokens, _ = Lexer(src).tokenise()
        ast, _    = Parser(tokens).parse()
        errors    = SemanticAnalyser().analyse(ast)
        return errors

    def test_clean_program_no_errors(self):
        src = """
func add(int a, int b) {
    return a + b
}
int x = add(3, 4)
"""
        errors = self._analyse(src)
        self.assertEqual(len(errors), 0)

    def test_undeclared_variable(self):
        errors = self._analyse("int x = z + 1")
        codes = [e.error_code for e in errors]
        self.assertIn("SEM040", codes)

    def test_type_mismatch_assignment(self):
        errors = self._analyse('int x = "hello"')
        codes = [e.error_code for e in errors]
        self.assertIn("SEM021", codes)

    def test_redeclared_variable(self):
        src = "int x = 1\nint x = 2"
        errors = self._analyse(src)
        codes = [e.error_code for e in errors]
        self.assertIn("SEM020", codes)

    def test_break_outside_loop(self):
        errors = self._analyse("break")
        codes = [e.error_code for e in errors]
        self.assertIn("SEM110", codes)

    def test_wrong_arg_count(self):
        src = """
func add(int a, int b) { return a + b }
int r = add(1, 2, 3)
"""
        errors = self._analyse(src)
        codes = [e.error_code for e in errors]
        self.assertIn("SEM072", codes)

    def test_undeclared_function_call(self):
        errors = self._analyse("int x = foo(1, 2)")
        codes = [e.error_code for e in errors]
        self.assertIn("SEM070", codes)

    def test_nested_scope(self):
        src = """
int outer = 10
func test(int x) {
    int inner = outer + x
    return inner
}
"""
        errors = self._analyse(src)
        self.assertEqual(len(errors), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Interpreter Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestInterpreter(unittest.TestCase):

    def _run(self, src):
        tokens, _  = Lexer(src).tokenise()
        ast, _     = Parser(tokens).parse()
        interp     = Interpreter()
        output     = interp.run(ast)
        return output

    def test_print_integer(self):
        out = self._run("print 42")
        self.assertIn("42", out)

    def test_arithmetic(self):
        out = self._run("int x = 3 + 4\nprint x")
        self.assertIn("7", out)

    def test_function_call(self):
        src = """
func square(int n) { return n * n }
int r = square(5)
print r
"""
        out = self._run(src)
        self.assertIn("25", out)

    def test_if_true_branch(self):
        src = "if 1 == 1 { print \"yes\" } else { print \"no\" }"
        out = self._run(src)
        self.assertIn("yes", out)

    def test_while_loop(self):
        src = """
int i = 0
int s = 0
while i < 5 {
    s = s + i
    i = i + 1
}
print s
"""
        out = self._run(src)
        self.assertIn("10", out)

    def test_for_loop(self):
        src = """
int total = 0
for k in range(1, 6) {
    total = total + k
}
print total
"""
        out = self._run(src)
        self.assertIn("15", out)

    def test_string_concat(self):
        out = self._run('str s = "Hello" + " World"\nprint s')
        self.assertIn("Hello World", out)

    def test_boolean_logic(self):
        out = self._run("bool b = true and false\nprint b")
        self.assertIn("false", out[0].lower() if out else "")

    def test_nested_functions(self):
        src = """
func double(int x) { return x * 2 }
func quad(int x)   { return double(double(x)) }
print quad(3)
"""
        out = self._run(src)
        self.assertIn("12", out)


# ─────────────────────────────────────────────────────────────────────────────
# NLP Explainer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNLPExplainer(unittest.TestCase):

    def setUp(self):
        self.explainer = NLPExplainer(use_model=False)

    def test_known_error_code(self):
        report = self.explainer.explain("SEM021", "Type mismatch", 5, 3)
        self.assertNotEqual(report.beginner_explanation, "")
        self.assertNotEqual(report.intermediate_explanation, "")
        self.assertNotEqual(report.expert_explanation, "")

    def test_unknown_error_code(self):
        report = self.explainer.explain("ZZZ999", "Unknown error", 1, 1)
        self.assertNotEqual(report.beginner_explanation, "")

    def test_suggestions_present(self):
        report = self.explainer.explain("SEM040", "Undeclared var", 3, 5)
        self.assertTrue(len(report.suggestions) > 0)

    def test_display_beginner(self):
        report = self.explainer.explain("LEX001", "Unexpected char", 1, 5)
        text = report.display("beginner")
        self.assertIn("LEX001", text)

    def test_explain_many(self):
        errors = [
            {"error_code": "SEM040", "message": "Undeclared 'x'", "line": 1, "column": 1},
            {"error_code": "SEM021", "message": "Type mismatch", "line": 2, "column": 5},
        ]
        reports = self.explainer.explain_many(errors, ["int y = x", 'int n = "hi"'])
        self.assertEqual(len(reports), 2)


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end Compiler Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCompilerEndToEnd(unittest.TestCase):

    def _compile(self, src, level="beginner"):
        c = CEEACompiler(user_level=level)
        return c.compile(src)

    def test_hello_world_success(self):
        result = self._compile('print "Hello, World!"')
        self.assertTrue(result.success)
        self.assertEqual(result.error_count, 0)

    def test_semantic_error_detected(self):
        result = self._compile("int x = undeclared_var")
        self.assertFalse(result.success)
        self.assertGreater(len(result.explanations), 0)

    def test_lexer_error_detected(self):
        result = self._compile("int x = @@@")
        self.assertFalse(result.success)
        self.assertGreater(len(result.lex_errors), 0)

    def test_complete_program(self):
        src = """
func fib(int n) {
    if n <= 1 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}
int f = fib(6)
print f
"""
        result = self._compile(src)
        self.assertTrue(result.success)
        self.assertIn("8", result.output)

    def test_compile_time_recorded(self):
        result = self._compile("print 1")
        self.assertGreater(result.compile_time, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()
    for cls in [
        TestLexer, TestParser, TestSemanticAnalyser,
        TestInterpreter, TestNLPExplainer, TestCompilerEndToEnd,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
