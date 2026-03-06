# CEEA Compiler – README

**Project:** Compiler Error Explanation with AI (CEEA)  
**Language:** CEEA-Lang (custom simple language)  
**Author:** Siddharth Singh (24CSB0A72)

---

## Quick Start

```bash
# Install Python 3.9+  (no extra packages needed for the core compiler)

# Run the compiler on a file
python compiler.py examples/hello.cea

# Interactive REPL
python compiler.py

# Choose explanation level
python compiler.py examples/errors_demo.cea --level intermediate

# Show bytecode listing
python compiler.py examples/functions.cea --bytecode

# Evaluate a one-liner
python compiler.py --eval "print 42"

# Run tests
python tests/test_compiler.py
```

---

## Project Structure

```
ceea_compiler/
├── compiler.py              ← Main entry point (CLI + API)
├── lexer/
│   ├── tokens.py            ← Token types and definitions
│   └── lexer.py             ← Lexical analyser (tokeniser)
├── parser/
│   ├── ast_nodes.py         ← AST node classes
│   └── parser.py            ← Recursive-descent parser
├── semantic/
│   └── analyser.py          ← Type checker + scope analyser
├── codegen/
│   └── interpreter.py       ← Tree-walking interpreter + bytecode emitter
├── nlp/
│   └── explainer.py         ← NLP error explanation engine
├── examples/
│   ├── hello.cea            ← Hello World
│   ├── functions.cea        ← Functions + loops
│   └── errors_demo.cea      ← Deliberate errors (shows NLP explanations)
└── tests/
    └── test_compiler.py     ← 48 unit + integration tests
```

---

## CEEA-Lang Language Reference

### Types
| Type    | Example       |
|---------|---------------|
| `int`   | `42`          |
| `float` | `3.14`        |
| `str`   | `"hello"`     |
| `bool`  | `true / false`|

### Variables
```
int x = 10
float pi = 3.14
str name = "CEEA"
bool flag = true
```

### Operators
```
+  -  *  /  %           # arithmetic
==  !=  <  <=  >  >=    # comparison
and  or  not             # logical
=                        # assignment
```

### Control Flow
```
if condition {
    ...
} else {
    ...
}

while condition {
    ...
}

for i in range(0, 10) {
    ...
}
```

### Functions
```
func add(int a, int b) {
    return a + b
}

int result = add(3, 4)
```

### I/O
```
print "Hello"
print 42
print result
```

### Comments
```
# This is a comment
```
