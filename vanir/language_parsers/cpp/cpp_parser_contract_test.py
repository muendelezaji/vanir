# Copyright 2025 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Golden-file contract tests for the Vanir C/C++ parser.

Each fixture in testdata/ with a `.golden.json` is parsed and compared against
the recorded parser-facing output contract. The suite is backend-agnostic: it
only uses the public CppParser API so it can be reused for a Tree-sitter backend.
"""

import json
import os

from vanir.language_parsers.cpp import cpp_parser

from absl.testing import absltest
from absl.testing import parameterized

_TESTDATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')
_GOLDEN_SUFFIX = '.golden.json'


def _golden_files():
  return sorted(
      (name[: -len(_GOLDEN_SUFFIX)],)
      for name in os.listdir(_TESTDATA_DIR)
      if name.endswith(_GOLDEN_SUFFIX)
  )


def _find_source(stem):
  for ext in cpp_parser.CppParser.get_supported_extensions():
    path = os.path.join(_TESTDATA_DIR, stem + ext)
    if os.path.exists(path):
      return path
  raise FileNotFoundError(f'No source fixture for {stem}')


class CppParserContractTest(parameterized.TestCase):

  def test_golden_files_exist(self):
    self.assertNotEmpty(_golden_files())

  @parameterized.parameters(*_golden_files())
  def test_matches_golden(self, stem):
    with open(os.path.join(_TESTDATA_DIR, stem + _GOLDEN_SUFFIX)) as f:
      golden = json.load(f)
    parser = cpp_parser.CppParser(_find_source(stem))
    results = parser.get_chunks(
        [tuple(r) for r in golden.get('affected_line_ranges', [])]
    )

    if 'parse_errors' in golden:
      self.assertLen(results.parse_errors, len(golden['parse_errors']))
    if 'line_tokens' in golden:
      self.assertEqual(
          {str(k): list(v) for k, v in results.line_chunk.tokens.items()},
          golden['line_tokens'],
      )
    if 'function_chunks' in golden:
      self.assertEqual(
          [c.name for c in results.function_chunks],
          [c['name'] for c in golden['function_chunks']],
      )
      for actual, expected in zip(
          results.function_chunks, golden['function_chunks']
      ):
        for key in (
            'return_types',
            'parameters',
            'used_data_types',
            'local_variables',
            'called_functions',
        ):
          if key in expected:
            self.assertEqual(
                [list(x) if isinstance(x, (list, tuple)) else x
                 for x in getattr(actual, key)],
                expected[key],
                f'{actual.name}.{key}',
            )


if __name__ == '__main__':
  absltest.main()
