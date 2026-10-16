# C/C++ parser fixtures

Each `<name>.<ext>` source may have a `<name>.golden.json` describing the
expected parser contract (see `cpp_parser_contract_test.py`). Goldens must be
produced by the incumbent FuzzyC parser or be copied from existing verified test
expectations; never hand-edit them to match a new backend. Keys absent from a
golden are not asserted. Sources without a golden are the pending corpus for the
equivalence-suite PR.
