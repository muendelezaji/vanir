# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file or at https://developers.google.com/open-source/licenses/bsd

"""Tests that the differential harness detects signature and selection drift.

These validate the measuring tool independently of either C/C++ parser. They
are not evidence of backend equivalence; parser_equivalence_test supplies that.
"""

import dataclasses
import functools

from absl.testing import absltest
from absl.testing import parameterized
from vanir.language_parsers import common
from vanir.language_parsers.cpp.equivalence import differential

_FUNCTION = common.FunctionChunkBase(
    name='sample', return_types=[['int']], parameters=['argument'],
    used_data_types=[['int']], local_variables=['value'],
    called_functions=['consume'],
    tokens=['int', 'sample', '(', 'int', 'argument', ')', '{', 'int',
            'value', '=', 'argument', ';', 'consume', '(', 'value', ')', ';',
            'return', 'value', ';', '}'],
)
_LINES = {
    2: ['int', 'sample', '(', 'int', 'argument', ')', '{'],
    3: ['int', 'value', '=', 'argument', ';'],
    4: ['consume', '(', 'value', ')', ';', 'return', 'value', ';', '}'],
}


class _SingleUseParser:
  """Small fixture enforcing the real native parser's single-use contract."""

  def __init__(self, chunk=_FUNCTION, lines=None, start=2, end=4, errors=()):
    self._chunk = chunk
    self._lines = _LINES if lines is None else lines
    self._start = start
    self._end = end
    self._errors = errors
    self._consumed = False

  def get_chunks(self, affected=None):
    if self._consumed:
      raise AssertionError('Harness reused a consumed parser')
    self._consumed = True
    include = not affected or any(
        start <= self._end and end >= self._start for start, end in affected)
    return common.ParseResults(
        [self._chunk] if include else [], common.LineChunkBase(self._lines),
        list(self._errors),
    )


class DifferentialHarnessTest(parameterized.TestCase):

  def test_identical_outputs_and_single_use_parsers(self):
    self.assertEmpty(differential.differences(
        differential.snapshot(_SingleUseParser, 5),
        differential.snapshot(_SingleUseParser, 5),
    ))

  @parameterized.named_parameters(
      ('name', {'name': 'different'}),
      ('return_type', {'return_types': [['long']]}),
      ('parameters', {'parameters': []}),
      ('data_type', {'used_data_types': [['long']]}),
      ('locals', {'local_variables': []}),
      ('calls', {'called_functions': []}),
      ('tokens', {'tokens': ['return', '1', ';']}),
  )
  def test_metadata_drift_is_detected(self, mutation):
    changed = dataclasses.replace(_FUNCTION, **mutation)
    dimensions = differential.differences(
        differential.snapshot(_SingleUseParser, 5),
        differential.snapshot(functools.partial(_SingleUseParser, chunk=changed), 5),
    )
    self.assertIn('functions', dimensions)

  def test_normalization_drift_changes_function_hash(self):
    changed = dataclasses.replace(_FUNCTION, local_variables=[])
    dimensions = differential.differences(
        differential.snapshot(_SingleUseParser, 5),
        differential.snapshot(functools.partial(_SingleUseParser, chunk=changed), 5),
    )
    self.assertIn('normalized_functions', dimensions)
    self.assertIn('function_hashes', dimensions)

  def test_line_drift_changes_real_ngram_hash_and_used_line_numbers(self):
    changed = {**_LINES, 5: ['return', '-1', ';']}
    dimensions = differential.differences(
        differential.snapshot(_SingleUseParser, 5),
        differential.snapshot(functools.partial(_SingleUseParser, lines=changed), 5),
    )
    self.assertIn('line_tokens', dimensions)
    self.assertIn('normalized_lines', dimensions)
    self.assertIn('line_hashes', dimensions)

  def test_off_by_one_boundary_is_detected(self):
    dimensions = differential.differences(
        differential.snapshot(_SingleUseParser, 5),
        differential.snapshot(functools.partial(_SingleUseParser, end=3), 5),
    )
    self.assertEqual(dimensions, ['function_selection'])

  def test_diagnostic_text_is_not_a_compatibility_dimension(self):
    reference = differential.snapshot(functools.partial(
        _SingleUseParser, errors=[common.ParseError(2, 0, 'int', 'native')]), 5)
    candidate = differential.snapshot(functools.partial(
        _SingleUseParser, errors=[common.ParseError(2, 0, 'int', 'tree-sitter')]), 5)
    self.assertNotEqual(reference['diagnostics'], candidate['diagnostics'])
    self.assertEmpty(differential.differences(reference, candidate))

  def test_diagnostic_location_drift_is_detected(self):
    reference = differential.snapshot(functools.partial(
        _SingleUseParser, errors=[common.ParseError(2, 0, 'int', 'error')]), 5)
    candidate = differential.snapshot(functools.partial(
        _SingleUseParser, errors=[common.ParseError(3, 0, 'int', 'error')]), 5)
    self.assertEqual(differential.differences(reference, candidate),
                     ['error_locations'])


if __name__ == '__main__':
  absltest.main()
