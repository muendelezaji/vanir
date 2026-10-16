# Tree-sitter migration: stacked PR handoff

The sandbox can only push the branch it is on, so stages 2-4 are delivered as a
git bundle (`tree-sitter-stack.bundle`, exact bytes incl. CRLF fixtures).
Each commit subject starts with `[copilot]`. Local test results:
`bazel test //...` -> stage 3: 35/35 pass, stage 4: 34/34 pass.

Stage 1 (plan + fixtures + golden contract test) is on the pushed branch
`copilot/copilottree-sitter-migration` (its first commit lacks the `[copilot]`
prefix and cannot be rewritten from the sandbox).

```sh
git fetch origin copilot/copilottree-sitter-migration
git checkout copilot/copilottree-sitter-migration
git fetch docs/stacked_prs/tree-sitter-stack.bundle \
  copilot/tree-sitter-equivalence-tests:copilot/tree-sitter-equivalence-tests \
  copilot/tree-sitter-cpp-backend:copilot/tree-sitter-cpp-backend \
  copilot/remove-fuzzyc:copilot/remove-fuzzyc
git push origin copilot/tree-sitter-equivalence-tests copilot/tree-sitter-cpp-backend copilot/remove-fuzzyc

gh pr create --base main --head copilot/copilottree-sitter-migration \
  --title "[copilot] Tree-sitter migration plan and parser contract fixtures"
gh pr create --base copilot/copilottree-sitter-migration --head copilot/tree-sitter-equivalence-tests \
  --title "[copilot] Add C/C++ parser equivalence suite with FuzzyC goldens"
gh pr create --base copilot/tree-sitter-equivalence-tests --head copilot/tree-sitter-cpp-backend \
  --title "[copilot] Add Tree-sitter C/C++ parser backend"
gh pr create --base copilot/tree-sitter-cpp-backend --head copilot/remove-fuzzyc \
  --title "[copilot] Remove FuzzyC and C/C++ native parser build"
```

The bundle's branches are stacked: equivalence-tests -> cpp-backend ->
remove-fuzzyc, with the equivalence commit parented on `5ffeb5e` (stage 1 tip).
See `docs/tree_sitter_migration_plan.md` section 14 for compatibility findings
and intentional deviations. Delete this directory once the PRs are pushed.
