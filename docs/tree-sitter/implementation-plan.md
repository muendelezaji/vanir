# Tree-sitter migration implementation plan

## Goal and compatibility boundary

Add an explicitly selected Tree-sitter C/C++ parser to `muendelezaji/vanir`, preserving `common.ParseResults`, `FunctionChunkBase`, `LineChunkBase`, affected-line filtering, and the existing normalization and hashing pipeline. FuzzyC remains the default until compatibility evidence supports a separate promotion decision. No existing signatures are silently regenerated.

Use `tree-sitter==0.25.0`, `tree-sitter-c==0.24.1`, `tree-sitter-cpp==0.23.4`, and `tree-sitter-java==0.23.2`. Pin all supported Python lockfiles consistently. Java migration is outside the initial C/C++ implementation: ANTLR's C++ runtime is shared with the Java parser and cannot be removed solely by replacing FuzzyC. The pinned Java grammar prepares a later independent migration; it does not imply Java parity.

## Delivery and stacked pull requests

Each branch starts with `codex/`; each PR title starts with `[codex]`. PRs use the preceding branch as their base, so each diff is reviewable separately. Preserve the stack's order when integrating.

1. **Plan and compatibility contract** (`codex/tree-sitter-plan`, base `main`). Record the public contracts, acceptance gates, validation commands, and rollout limits in this document.
2. **Equivalence corpus and differential harness** (`codex/tree-sitter-equivalence`, base step 1). Add original, small fixtures with provenance notes and independent expected outputs. Cover ordinary C, C++, kernel idioms, macros, preprocessor conditionals, line continuations, strings/comments, malformed input, and incomplete snippets. Compare function order/names, inclusive source ranges through affected-line probes, ordered metadata, lexical tokens by line, normalized functions, and function/line hashes. Separate strict compatibility fixtures from recovery characterization. Do not blanket-accept mismatches or skip failing comparisons.
3. **Opt-in backend and integration** (`codex/tree-sitter-backend`, base step 2). Add the backend, pinned dependencies, Bazel targets, explicit selection, validation of invalid selections, and user documentation. Preserve default FuzzyC behavior. Ensure import selection works in multiprocessing and Tree-sitter mode can initialize without importing native FuzzyC. Validate the actual parser entry point as well as direct backend calls.
4. **Compatibility hardening** (a further `codex/` PR only if needed). Fix failures using the corpus; expand cases for discovered regressions. Every accepted semantic difference must identify its signature impact and regression test. Publish observed parity and remaining gaps. Do not declare equivalence from a zero-test or partial run.
5. **Promotion/removal gate** (future separate PR, conditional). Make Tree-sitter default only after strict parity gates pass and intentional differences have an approved migration policy. Remove FuzzyC only after rollout, legacy-signature verification and rollback planning. Remove ANTLR C++ dependencies only after the Java parser also stops using them. This gate is deliberately not activated by an experimental backend PR.

## Parser implementation requirements

- Select C grammar for `.c`, C++ grammar for C++ extensions; document `.h` ambiguity and choose a deterministic policy.
- Parse source bytes consistently, preserving one-based line numbering and zero-based diagnostic columns; retain the existing UTF-8 then Latin-1 fallback behavior.
- Use syntax trees for function identification and metadata. Handle nested declarators, pointer/reference returns, arrays, function pointer parameters, qualified names and methods deliberately.
- Preserve lexical punctuation, literal, comment and preprocessor treatment when generating tokens. Tree-sitter leaves alone may tokenize operators and strings differently from FuzzyC; test this explicitly.
- Keep function tokens and metadata in source order; match duplicate handling. Include the function declaration and braces in the legacy function-token contract.
- Apply inclusive range intersection to functions while leaving full-file line tokens unchanged. Empty/absent ranges mean all functions.
- Expose parse recovery diagnostics truthfully. ERROR and missing nodes must not cause crashes, fabricated functions, or silently absent error reports. Diagnostic wording need not equal ANTLR, but ranges and recovery behavior must be asserted.
- Keep backend state per parser instance, with no mutable cross-file parser cache. Bound processing to input size; test deep nesting and repeated calls when practical.

## Corpus and evidence

Fixtures should be independently authored. The FuzzyC grammars and Vanir's existing C++ parser tests are behavioral references. Joern repositories can suggest language constructs, but copied fixtures require compatible licensing and provenance. Do not import whole external suites or download unlicensed samples. Include a fixture manifest describing each purpose and expected parity/recovery category.

Strict fixtures must assert exact complete dataclass outputs or compare both real backends, including ordered nested metadata. Hash checks must call Vanir's production normalizer/hasher rather than reimplementing them. Include positive findings and patched/negative cases where practical; token counts or successful parsing alone do not establish detection equivalence. Never replace a missing FuzzyC oracle with a mock and call that differential validation.

Recovery fixtures may have intentionally different syntax-error messages and extraction, but their expected results must be concrete, reviewed and documented. A recovery fixture is not evidence of exact signature compatibility.

## Acceptance criteria

### Initial opt-in release

- Existing FuzzyC selection remains the default; explicit Tree-sitter selection and invalid values have automated coverage through the production entry point.
- All new backend unit tests and strict differential fixtures pass with both actual parsers installed. Every test executes; skips are reported separately.
- Exact identity, metadata, token and production-hash parity holds on the designated strict corpus. Every discovered difference becomes a failing regression case until fixed or moves to an explicitly justified characterization case with documented impact; never relabel ordinary failures merely to achieve green.
- Existing `bazel test //...` passes, including native C++/Java parser tests and hermetic missing-patch integration. Investigate baseline failures independently.
- Build `//:detector_runner`; exercise a representative local offline scan with repository signatures and verify JSON/HTML output and expected findings. Perform with both backends and compare results where the fixture is in the strict compatibility set.
- No secret credentials are needed for hermetic tests. Builds retain TLS, artifact-checksum and package verification.
- Dependency pins, startup instructions and test commands are reproducible. Tracked generated artifacts and unrelated dependency updates are excluded.

### Default switch and removal

- Expand validation to a versioned representative real-source corpus (kernel, userspace C and modern C++), with recorded hashes, measured mismatch categories and an explicit accepted threshold. Exact equality is required wherever existing signatures are promised compatible; a numerical extraction-rate target cannot substitute for that promise.
- Measure wall time and peak memory on the same inputs and hardware; investigate regressions before promotion.
- Test old signatures against both backends, plus any new signature format/version identifier. If intentional changes affect hashes, version signature generation and make scanning compatibility explicit rather than silently changing existing signatures.
- Document rollback to FuzzyC and preserve a comparison tool through the transition.
- Java migration and ANTLR runtime removal receive their own parity and integration evidence.

## Validation and environment

The repository pins Bazel 9.0.0. Use Java >=11 and a C++17 compiler, with four build jobs on this machine. Use the existing isolated `/workspace/vanir` checkout; do not create worktrees unless requested. Keep external tooling/caches under `/workspace/.vanir-tools`.

```sh
cd /workspace/vanir
/workspace/.vanir-tools/bin/bazel --output_user_root=/workspace/.vanir-tools/cache test --jobs=4 --lockfile_mode=off --symlink_prefix=/workspace/.vanir-tools/bazel- --test_output=errors //...
/workspace/.vanir-tools/bin/bazel --output_user_root=/workspace/.vanir-tools/cache build --jobs=4 --lockfile_mode=off --symlink_prefix=/workspace/.vanir-tools/bazel- //:detector_runner
```

The initial build identified a required network destination blocked by current policy: `third-party-mirror.googlesource.com` (pinned FuzzyC source). Save required domains to environment settings and retry after runtime policy updates. GitHub API access is also required for creating PRs; HTTPS Git read access does not prove API access. Report any external blocker, never claim passing differential tests or created PRs without execution evidence.

## Execution record

Implementation and verification results belong in a separate validation report, including exact commands, passed/failed/skipped counts, corpus mismatches, environment blockers, commit IDs and PR links. This document states the gates; it does not assert that they have already passed.
