# Experimental Tree-sitter C/C++ backend

FuzzyC remains the default C/C++ parser. The Tree-sitter implementation preserves
Vanir's chunk interface and is available for explicit testing and evaluation:

```sh
VANIR_CPP_PARSER_BACKEND=tree_sitter ./bazel-bin/detector_runner \
  --vulnerability_file_name=/absolute/path/signatures.json \
  offline_directory_scanner /absolute/path/source
```

Use the same flag with signature generation if you are evaluating generated
signatures. The environment setting reaches worker processes; keep it consistent
between generation and detection. Invalid values raise `ValueError` rather than
silently falling back. `VANIR_CPP_PARSER_BACKEND=fuzzyc` explicitly selects the
legacy parser. For direct library use:

```python
from vanir.language_parsers.cpp import cpp_parser

result = cpp_parser.CppParser('/absolute/path/example.c',
                              backend='tree_sitter').get_chunks()
```

An explicit `backend` argument takes precedence over the environment. Selection
through `language_parsers.parse_file` and the higher-level `parser.Parser` uses
the environment. Files with `.c` use the C grammar; `.h` and supported C++
extensions use the C++ grammar. Header ambiguity is resolved deterministically;
there is no extension guessing or failed-parse fallback.

Pinned versions are Tree-sitter 0.25.0, C 0.24.1, C++ 0.23.4 and Java 0.23.2.
Java continues to use Vanir's existing ANTLR parser; installing its Tree-sitter
grammar does not switch it. FuzzyC and the shared ANTLR runtime remain build
dependencies during this comparison period. Lazy native imports reduce runtime
initialization; they do not remove native targets from Bazel's dependency graph.

## Signature compatibility

Treat this backend as experimental until the [acceptance gates](implementation-plan.md)
are met on your source corpus. Tree-sitter supports syntax that FuzzyC may
ignore, and both recovery and metadata can differ. Parser success does not prove
that existing function hashes or line hashes match. Do not regenerate stored
signatures or remove FuzzyC based only on the backend's unit tests.

The [differential corpus](../../vanir/language_parsers/cpp/equivalence/README.md)
compares ordered metadata, tokens, affected-line boundaries, normalization and
production hashes using the actual native reference. Its reference explicitly
selects FuzzyC even when the environment enables Tree-sitter. Run:

```sh
bazel test //vanir/language_parsers/cpp:tree_sitter_parser_test \
  //vanir/language_parsers/cpp:cpp_parser_backend_test \
  //vanir/language_parsers/cpp:differential_test \
  //vanir/language_parsers/cpp:parser_equivalence_test
bazel test //...
```

In this cloud environment, Bazel is installed at
`/workspace/.vanir-tools/bin/bazel`, with the cache and symlinks outside the
checkout. Java, a C++17 compiler and HTTPS access to the pinned dependency hosts
are required. When sandboxed ANTLR generation needs the cloud proxy and trust
configuration, pass the existing variable bindings without embedding values:

```sh
/workspace/.vanir-tools/bin/bazel \
  --output_user_root=/workspace/.vanir-tools/cache test \
  --jobs=4 --lockfile_mode=off \
  --symlink_prefix=/workspace/.vanir-tools/bazel- \
  --action_env=HTTPS_PROXY --action_env=HTTP_PROXY \
  --action_env=https_proxy --action_env=http_proxy \
  --action_env=SSL_CERT_FILE --action_env=REQUESTS_CA_BUNDLE //...
```

No service needs to run between commands. Use the existing isolated checkout;
creating a worktree is unnecessary. Current-instance validation and saved cloud
setup instructions do not establish that a published snapshot has been restored
in a new task.
