# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests explicit C/C++ backend selection through the production entry point."""

import os
import subprocess
import sys
from unittest import mock

from absl.testing import absltest
from vanir.language_parsers import language_parsers
from vanir.language_parsers.cpp import cpp_parser


class CppParserBackendTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.source = self.create_tempfile(
        'selection.c', content='int twice(int value) { return value * 2; }\n'
    ).full_path

  def test_environment_selection_through_parse_file(self):
    with mock.patch.dict(
        os.environ, {'VANIR_CPP_PARSER_BACKEND': 'tree_sitter'}
    ):
      result = language_parsers.parse_file(self.source)
    self.assertLen(result.function_chunks, 1)
    self.assertEqual(result.function_chunks[0].name, 'twice')
    self.assertEqual(result.function_chunks[0].parameters, ['value'])
    self.assertEqual(result.line_chunk.tokens[1][-1], '}')
    self.assertEmpty(result.parse_errors)

  def test_explicit_argument_overrides_environment(self):
    with mock.patch.dict(os.environ, {'VANIR_CPP_PARSER_BACKEND': 'invalid'}):
      result = cpp_parser.CppParser(
          self.source, backend='tree_sitter'
      ).get_chunks()
    self.assertEqual(result.function_chunks[0].name, 'twice')

  def test_invalid_environment_fails_before_loading_native_extension(self):
    with mock.patch.dict(os.environ, {'VANIR_CPP_PARSER_BACKEND': 'invalid'}):
      with self.assertRaisesRegex(ValueError, 'must be fuzzyc or tree_sitter'):
        language_parsers.parse_file(self.source)

  def test_empty_explicit_selection_is_rejected(self):
    with self.assertRaisesRegex(ValueError, 'must be fuzzyc or tree_sitter'):
      cpp_parser.CppParser(self.source, backend='')

  def test_ranges_filter_functions_but_preserve_line_tokens(self):
    parser = cpp_parser.CppParser(self.source, backend='tree_sitter')
    complete = parser.get_chunks()
    filtered = parser.get_chunks([(2, 2)])
    self.assertEmpty(filtered.function_chunks)
    self.assertEqual(complete.line_chunk, filtered.line_chunk)

  def test_import_order_cannot_bypass_explicit_backend_selection(self):
    script = """
from vanir.language_parsers.cpp import tree_sitter_parser
from vanir.language_parsers import language_parsers
from vanir.language_parsers.cpp import cpp_parser
assert language_parsers.get_parser_class('sample.c') is cpp_parser.CppParser
assert language_parsers.get_parser_class('sample.cpp') is cpp_parser.CppParser
assert language_parsers.get_parser_class('sample.h') is cpp_parser.CppParser
"""
    process_env = dict(os.environ)
    process_env.pop('VANIR_CPP_PARSER_BACKEND', None)
    process_env['PYTHONPATH'] = os.pathsep.join(sys.path)
    process = subprocess.run(
        [sys.executable, '-c', script], capture_output=True,
        text=True, check=False, env=process_env,
    )
    self.assertEqual(process.returncode, 0, process.stderr)

  def test_spawned_interpreter_inherits_selection_without_native_imports(self):
    script = '''
import sys
from vanir.language_parsers import language_parsers
result = language_parsers.parse_file(sys.argv[1])
assert [chunk.name for chunk in result.function_chunks] == ['twice']
assert 'vanir.language_parsers.cpp.python.parser_core' not in sys.modules
assert 'vanir.language_parsers.java.python.parser_core' not in sys.modules
assert 'pybind11_abseil.status' not in sys.modules
'''
    # Bazel's launcher adds runfiles imports to sys.path in this process.
    # Preserve those paths when launching the interpreter directly.
    process_env = dict(os.environ)
    process_env['VANIR_CPP_PARSER_BACKEND'] = 'tree_sitter'
    process_env['PYTHONPATH'] = os.pathsep.join(sys.path)
    process = subprocess.run(
        [sys.executable, '-c', script, self.source],
        capture_output=True, text=True, check=False, env=process_env,
    )
    self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == '__main__':
  absltest.main()
