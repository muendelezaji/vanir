# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file or at https://developers.google.com/open-source/licenses/bsd

"""Signature compatibility gates for the experimental Tree-sitter C/C++ parser."""

import dataclasses
import json
import os
from pathlib import Path
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized
from vanir.language_parsers import common
from vanir.language_parsers.cpp import cpp_parser
from vanir.language_parsers.cpp import tree_sitter_parser
from vanir.language_parsers.cpp.equivalence import differential

_CORPUS = Path(__file__).parent / 'equivalence'
_MANIFEST = json.loads((_CORPUS / 'manifest.json').read_text())


def _reference_parser(filename):
  # An environment opt-in must never turn a differential test into a self-test.
  return cpp_parser.CppParser(filename, backend='fuzzyc')


class ParserEquivalenceTest(parameterized.TestCase):

  def test_reference_backend_ignores_environment_opt_in(self):
    with mock.patch.dict(os.environ, {'VANIR_CPP_PARSER_BACKEND': 'tree_sitter'}):
      with mock.patch.object(cpp_parser, 'CppParser') as constructor:
        _reference_parser('fixture.c')
    constructor.assert_called_once_with('fixture.c', backend='fuzzyc')

  def _parse_both(self, filename):
    path = _CORPUS / 'fixtures' / filename
    line_count = len(path.read_bytes().splitlines())
    return (
        differential.snapshot(lambda: _reference_parser(str(path)), line_count),
        differential.snapshot(
            lambda: tree_sitter_parser.TreeSitterCppParser(str(path)), line_count
        ),
    )

  @parameterized.named_parameters(
      [(name.replace('.', '_'), name) for name in _MANIFEST['compatible']]
  )
  def test_compatible_corpus(self, filename):
    reference, candidate = self._parse_both(filename)
    for dimension in reference:
      if dimension == 'diagnostics':
        continue  # Text belongs to the parser; structured locations are checked.
      with self.subTest(dimension=dimension):
        self.assertEqual(reference[dimension], candidate[dimension])

  @parameterized.named_parameters(
      ('basic', 'basic.c', [('add', 4, 7), ('notify', 9, 11)]),
      ('kernel', 'kernel_style.c', [('process_packet', 2, 8)]),
      ('empty', 'empty.c', []),
      ('crlf', 'crlf.c', [('windows', 1, 3)]),
  )
  def test_independent_function_boundary_oracle(self, filename, expected):
    for implementation in (_reference_parser,
                           tree_sitter_parser.TreeSitterCppParser):
      path = _CORPUS / 'fixtures' / filename
      line_count = len(path.read_bytes().splitlines())
      for line in range(line_count + 2):
        with self.subTest(backend=implementation.__name__, line=line):
          names = [chunk.name for chunk in implementation(str(path)).get_chunks(
              [(line, line)]).function_chunks]
          self.assertEqual(
              names, [name for name, start, end in expected
                      if start <= line <= end])

  def test_manifest_covers_every_fixture_exactly_once(self):
    listed = [name for group in _MANIFEST.values() for name in group]
    self.assertLen(listed, len(set(listed)))
    self.assertCountEqual(
        listed, [path.name for path in (_CORPUS / 'fixtures').iterdir()]
    )

  @parameterized.named_parameters(
      [(name.replace('.', '_'), name) for name in _MANIFEST['recovery']]
  )
  def test_recovery_preserves_source_and_reports_diagnostics(self, filename):
    reference, candidate = self._parse_both(filename)
    # Error recovery differs intentionally. Token retention remains a hard gate.
    self.assertEqual(reference['line_tokens'], candidate['line_tokens'])
    self.assertEqual(reference['line_hashes'], candidate['line_hashes'])
    self.assertNotEmpty(candidate['diagnostics'])
    path = _CORPUS / 'fixtures' / filename
    self.assertEqual(
        candidate,
        differential.snapshot(
            lambda: tree_sitter_parser.TreeSitterCppParser(str(path)),
            len(path.read_bytes().splitlines()),
        ),
    )
    expected_functions = []
    if filename == 'partial_fragment.c':
      expected_functions = [dataclasses.asdict(common.FunctionChunkBase(
          name='recovered', return_types=[['int']], parameters=['value'],
          used_data_types=[['int']], local_variables=[], called_functions=[],
          tokens=['int', 'recovered', '(', 'int', 'value', ')', '{',
                  'return', 'value', '+', '1', ';', '}'],
      ))]
    self.assertEqual(candidate['functions'], expected_functions)
    expected_location = [3, 0] if filename == 'partial_fragment.c' else [1, 0]
    self.assertEqual(
        [location[:2] for location in candidate['error_locations']],
        [expected_location],
    )
    for selection in candidate['function_selection']:
      affected = selection['ranges']
      includes_recovered = filename == 'partial_fragment.c' and (
          not affected or any(start <= 6 and end >= 4 for start, end in affected)
      )
      self.assertEqual(
          [function[0] for function in selection['functions']],
          ['recovered'] if includes_recovered else [],
      )

  @parameterized.named_parameters(
      [(name.replace('.', '_'), name) for name in _MANIFEST['extended_syntax']]
  )
  def test_extended_syntax_signature_compatibility(self, filename):
    reference, candidate = self._parse_both(filename)
    self.assertEmpty(differential.differences(reference, candidate))


if __name__ == '__main__':
  absltest.main()
