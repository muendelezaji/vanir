# C/C++ parser equivalence corpus

These are original, synthetic sources. They intentionally avoid copying code
from third-party projects. `kernel_style.c` models opaque structures, pointer
parameters, early returns, and external calls common in kernel code;
`gnu_extensions.c` separately exercises compiler-specific syntax. Additional
lexical regressions cover nested comments, postfix type qualifiers, a template
function prefix, macro-separated adjacent strings, and Latin-1 with CRLF. The cases
reflect the two-stage FuzzyC contract implemented in `cpp/parser_core.cc` and
its normalizer/hasher consumers. Reference projects for future expansion:

- <https://third-party-mirror.googlesource.com/fuzzyc>
- <https://github.com/joernio/joern>
- <https://github.com/octopus-platform/joern>

`manifest.json` classifies every fixture exactly once. Both `compatible` and
`extended_syntax` are strict compatibility gates. `recovery` explicitly allows
different function extraction and parser diagnostics on invalid translation
units, but still requires identical retained tokens and line signatures. A
recovery difference is not evidence that function signatures are compatible.
The experimental backend must remain opt-in until the migration's wider release
gates are met.

The test compares complete `FunctionChunkBase` metadata, source tokens, normalized
function strings, Murmur3 function signatures, normalized lines, and real line
n-gram signatures. A fresh parser is created for every affected-line selection
because the native reference exposes single-use chunk objects. Every individual
source line, the positions immediately outside the file, combined disjoint
ranges, reversed range ordering, and whole-file selection are exercised. This
checks function boundaries even though the public chunk datatype has no range
field, and distinguishes same-name functions using their token sequences.

Diagnostic text is parser-specific and excluded from exact compatibility.
Structured locations and offending tokens are compared on strict fixtures.
Malformed-source tests require Tree-sitter diagnostics and deterministic recovery
on repeated parses; partial fragments must retain their following intact
function. Native errors are preserved in differential snapshots for inspection.

Validate the measuring tool independently first (these tests do not establish
parser equivalence):

```sh
python -m vanir.language_parsers.cpp.equivalence.differential_test
```

Run the actual two-parser gate using the repository's supported test runner:

```sh
bazel test //vanir/language_parsers/cpp:parser_equivalence_test
```

The 21 fixtures establish a targeted regression corpus, not a statistical claim
of equivalence for all C/C++ dialects. Grow it with real-world failures before
considering removal of the reference parser or migration of stored signatures.

The GNU `typeof(item->value)` fixture remains a strict release gate. The pinned
C grammar diagnoses that expression form; the compatibility adapter must handle
it while retaining FuzzyC's function boundary, empty return type, omitted call
metadata, and signature. The function-pointer case uses different base and
argument types so ordering and duplicate type captures are checked independently.
