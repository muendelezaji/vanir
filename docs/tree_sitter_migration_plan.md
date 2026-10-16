# Tree-sitter migration plan for the Vanir C/C++ parser

Status: proposed. Stacked-PR sequence: (1) plan + fixtures, (2) equivalence
tests, (3) Tree-sitter backend, (4) FuzzyC removal.

## 1. Goals and non-goals

**Goals**
- Replace the C/C++ parser's dependency on FuzzyC / ANTLR C++ runtime with
  Tree-sitter (`tree-sitter-c`, `tree-sitter-cpp`).
- Preserve the `AbstractLanguageParser` / `CppParser` output contract
  (`ParseResults`, `FunctionChunkBase`, `LineChunkBase`, `ParseError`) so
  `parser.py`, signature generation, the refiner and the scanner need no
  semantic changes.
- Keep signature-generation behavior as close as practical (function and line
  hashes), and quantify any intentional deviation.

**Non-goals**
- Migrating the Java parser (it keeps ANTLR4). `tree-sitter-java==0.23.2` is
  pinned for dependency/test infrastructure only.
- Changing signature formats, matching algorithms, or public APIs.
- Full C preprocessing or semantic analysis.

## 2. Pinned versions

| Package | Version |
|---|---|
| `tree-sitter` | `0.25.0` (preferred; `0.23.1` permitted) |
| `tree-sitter-c` | `0.24.1` |
| `tree-sitter-cpp` | `0.23.4` |
| `tree-sitter-java` | `0.23.2` |

## 3. Architecture

Current: `cpp_parser.py` -> pybind11 `parser_core` (C++) -> FuzzyC module
parser (function boundaries, signature pieces) + FuzzyC function parser (locals,
calls, used types) driven by ANTLR token streams.

Target: a pure-Python backend (`cpp_parser.py`) built on the `tree_sitter`
Python bindings, avoiding a C++ binding to maintain. The class keeps
`get_supported_extensions()` and `get_chunks()`. During PR 3 the FuzzyC backend
stays available only as a test oracle; PR 4 removes it.

Extension policy: `.c` -> `tree-sitter-c`; `.cc .hh .cpp .hpp .cxx .hxx` ->
`tree-sitter-cpp`. `.h` is ambiguous; it is parsed with the C++ grammar (a
superset for common headers), consistently, and documented in the module
docstring. The decision is validated against the fixture corpus.

## 4. Dependency and build strategy

- Python: add pinned entries to `requirements/requirements.txt` and regenerate
  `requirements_lock_3.{10..13}.txt` (with hashes) per `requirements/README.md`.
- Bazel: wheels are consumed via `rules_python` `pip.parse`; add the packages to
  the `py_library` deps of `cpp_parser`. Remove `@fuzzyc` use in PR 4 from
  `MODULE.bazel`, `WORKSPACE.bazel`, `repositories.bzl`, `extensions.bzl`.
- CMake / scikit-build: add the packages to `pyproject.toml` runtime
  dependencies; drop `FetchContent(fuzzyc)` and the pybind `parser_core` target
  in PR 4.
- Portability: Tree-sitter ships binary wheels for common platforms; platforms
  without wheels need a C compiler. This is documented in the README.

## 5. Parser-output compatibility contract

For each file, for the same inputs and affected line ranges, the backend must
produce:
- `function_chunks`: `name`, `return_types` (list of token lists), `parameters`
  (names), `used_data_types`, `local_variables`, `called_functions`, `tokens`
  (function body tokens), restricted to functions overlapping the requested
  1-based inclusive line ranges (all functions if none given), in source order.
- `line_chunk.tokens`: map of 1-based line number -> token list for all
  non-blank, non-comment lines.
- `parse_errors`: `ParseError(line, column, bad_token, message)`.
- Encoding: UTF-8 first, then the existing alternative-encoding retry with the
  `Converting ... to UTF-8` log; undecodable input still raises `ValueError`.
  Missing files still fail with an error matching `Failed to open file`.

## 6. Tokenization strategy

Tree-sitter has no lexical stream with trivia. Tokens are the leaf nodes of the
tree in source order (anonymous and named leaves; `comment` nodes and
whitespace excluded). String and character literals are single tokens; leaves
spanning multiple lines are assigned to their start line. Multi-token
operators match FuzzyC (`->`, `==`, `::`). Lines are 1-based (`row + 1`).
Preprocessor directives are treated as FuzzyC does (compared in the
equivalence suite) and deviations are recorded in the compatibility report.

## 7. AST traversal strategy

- Function discovery: `function_definition` nodes (including those inside
  `namespace_definition`, `class_specifier`, `linkage_specification`,
  `template_declaration`, and preprocessor conditional blocks).
- Name/params/return type: walk the declarator chain
  (`pointer_/reference_/function_declarator`, `qualified_identifier`,
  `parameter_list`) and `type`/qualifier children.
- Locals / used types / calls: traverse the body for `declaration` (declarators),
  `type_identifier` / `primitive_type` / `sized_type_specifier` / qualified
  types, and `call_expression` (identifier, field, qualified callee).
- Declaration-only prototypes are not function chunks but contribute line
  tokens.

## 8. Error and recovery semantics

`ERROR` nodes and `MISSING` nodes are converted to `ParseError` using the
node's start point (line = row + 1, column) and text (or the missing node
type). Parsing is best-effort: tokens and functions outside broken regions are
still produced. Equivalence on malformed input is measured and reported, not
assumed identical.

## 9. Test corpus and differential-equivalence method

- `vanir/language_parsers/cpp/testdata/` holds fixtures; `.golden.json` files
  capture FuzzyC output. Existing `cpp_parser_test.py` expectations seed goldens.
- Categories: declarations/definitions, qualifiers/types, pointer/reference/
  array/function-pointer declarators, nested blocks, structs/classes/
  namespaces/templates, macros and preprocessor-heavy code, comments and
  whitespace, malformed/partial code, member/qualified calls, local
  declarations, non-UTF-8 input.
- PR 2 compares goldens (and FuzzyC live where it can be built) with the
  candidate: chunks, line tokens, errors, and downstream function/line
  signature hashes. Tests are deterministic with no network access.
- Differences are classified as `identical`, `intentional` (documented), or
  `regression` (blocking).

## 10. Rollout and removal

1. PR 1: plan + fixtures; no behavior change.
2. PR 2: equivalence suite.
3. PR 3: Tree-sitter backend, production switch once equivalence passes.
4. PR 4: remove FuzzyC, ANTLR C++ runtime and stale docs/metadata; Java ANTLR
   is retained.

## 11. Risks

- Signature churn from token or line-boundary differences (mitigated by hash
  comparison).
- Macro-heavy kernel-style code parses differently: Tree-sitter may emit
  `ERROR` where FuzzyC is tolerant.
- Throughput of a Python backend versus native code (benchmark on large files).
- Wheel availability on exotic platforms.
- Ambiguity of `.h`.

## 12. Milestones

M1 plan/fixtures; M2 equivalence suite green on goldens; M3 backend passes the
suite and existing tests; M4 FuzzyC removed and builds green on Bazel and
CMake.

## 13. Acceptance criteria

- `cpp_parser_test` and the contract/equivalence tests pass on the Tree-sitter
  backend with no weakened assertions.
- Function-hash and line-hash equivalence on the corpus, or each difference
  documented as intentional.
- Parser, signature, refiner and scanner tests pass unchanged.
- Bazel and CMake/scikit-build builds succeed and no `fuzzyc` references remain
  after PR 4; Java parsing tests are unaffected.
- Dependency pins are exactly as in section 2 in all requirement/lock/config files.
