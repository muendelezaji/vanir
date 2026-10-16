# Tree-sitter migration validation

Validated in the cloud onboarding instance on 16 October 2026.

## Delivered behavior

The C/C++ Tree-sitter backend is explicitly selected with
`VANIR_CPP_PARSER_BACKEND=tree_sitter` or the `CppParser` constructor's `backend`
argument. FuzzyC remains the default, including when callers import the
Tree-sitter implementation first. Java retains its existing parser and shared
ANTLR runtime. The requested grammar versions and Tree-sitter 0.25.0 are pinned
in package declarations and regenerated locks for Python 3.10–3.13.

The compatibility adapter preserves legacy lexer boundaries (including unusual
preprocessor, adjacent-string and nested-comment behavior), ordered metadata,
template ranges, nested function-pointer types and legacy GNU recovery. Error
recovery is characterized separately where diagnostics intentionally differ.
No strict compatibility assertion was disabled or waived to achieve green.

## Executed checks

| Check | Result |
| --- | --- |
| Full `bazel test //...` | **38/38 targets passed**, exit 0 |
| Current JUnit XML reports | 657 recorded cases including subtests; 0 failures, 0 errors, 0 skipped |
| Actual native FuzzyC / Tree-sitter differential gate | **28 test methods passed** over 21 original fixtures; includes 238 XML cases with subtests |
| Tree-sitter backend contract suite | **18 passed** |
| Production routing and import-order suite | **7 passed** |
| Differential-harness mutation suite | **13 passed** |
| Legacy-signature scanner integration | **4 passed** |
| Existing hermetic missing-patch integration | Passed |
| `//:detector_runner` build | Passed, including native parsers and generated OSV protobuf modules |
| Saved installation script re-execution | Passed; verified binary/JAR checksums and reused detector build |
| Pylint with repository configuration | Passed for all changed Python files |
| Mypy for seven new Python modules and parser dispatcher | Passed |
| `git diff --check` | Passed |

The full test command, run from `/workspace/vanir`, was:

```sh
/workspace/.vanir-tools/bin/bazel \
  --output_user_root=/workspace/.vanir-tools/cache test \
  --jobs=4 --lockfile_mode=off \
  --symlink_prefix=/workspace/.vanir-tools/bazel- --test_output=errors \
  --action_env=HTTPS_PROXY --action_env=HTTP_PROXY \
  --action_env=https_proxy --action_env=http_proxy \
  --action_env=SSL_CERT_FILE --action_env=REQUESTS_CA_BUNDLE //...
```

Mypy on the existing C++/Java native wrappers still reports four absent native
module/stub errors in the source-only development venv. The original wrappers
had those same four errors plus two return-type errors; the latter were fixed.
These are distinct from the passing Bazel tests and new-module type checks.
A pip-wheel installation/type-check workflow was not validated.

## Actual detector CLI checks

The fixture generator used real FuzzyC parsing and Vanir's production signature
factory, then persisted v1 function and line signatures in OSV format. Four
separate detector processes exercised the real offline scanner:

| Backend | Vulnerable source | Patched source |
| --- | --- | --- |
| FuzzyC | Exactly 2 expected findings | 0 findings |
| Tree-sitter | Exactly the same 2 findings | 0 findings |

JSON findings were compared across backends and every JSON and HTML output was
verified. Retained local artifacts and logs are under
`/workspace/.vanir-tools/smoke/`; `run_cli.py` repeats these checks. The tracked
`//vanir/integration_tests:tree_sitter_detection_test` independently exercises
production scanner workers and false-positive filtering with the same positive
and negative contract.

## Environment and reproducibility

Bazel 9.0.0 was verified against the official SHA256 digest. ANTLR 4.11.1 and
4.13.2 JAR downloads retained HTTPS verification and were checked against Maven's
published checksums; the reusable installer additionally pins their SHA256
fingerprints. Standard Maven-cache creation/population used approved filesystem
escalation. No TLS verification or assertions were disabled.

Initial network denials for FuzzyC and the GitHub API were resolved and the
operations retried successfully. The saved custom domain additions are
`releases.bazel.build`, `bcr.bazel.build`,
`third-party-mirror.googlesource.com`, `repo.maven.apache.org` and
`api.github.com`; existing package-manager presets remain intact. Existing
platform GitHub authentication supports Git and PR creation; no new secrets
were requested.

Reusable `install_script` and `start_skill` were saved to the environment draft.
They capture the working directory, verified tool/JAR installation, four-job
Bazel commands, proxy/trust forwarding, feature selection and readiness checks.
The installer was exercised again successfully. No persistent service is
needed. The user must review/save the environment settings and publish the
prepared environment; publication and restoration in a new task have not been
validated here.

## Rollout limits

These tests establish compatibility on a targeted regression corpus, not all
C/C++ syntax or existing real-world signatures. The backend remains experimental.
Before changing the default or removing FuzzyC, expand the versioned real-source
corpus, measure mismatch and resource behavior, and decide how intentional
signature changes will be versioned. Removing the shared ANTLR runtime also
requires an independently validated Java migration. See the
[implementation plan](implementation-plan.md) for those acceptance gates and
[usage instructions](usage.md) for explicit selection and rollback.
