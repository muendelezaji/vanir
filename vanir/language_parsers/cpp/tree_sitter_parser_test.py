# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Behavioral contract tests for the opt-in Tree-sitter C/C++ backend."""

from unittest import mock

from absl.testing import absltest
from vanir.language_parsers import abstract_language_parser
from vanir.language_parsers.cpp import tree_sitter_parser


class TreeSitterCppParserTest(absltest.TestCase):

  def parse(self, source, suffix='.c'):
    filename = self.create_tempfile('source' + suffix, content=source).full_path
    return tree_sitter_parser.TreeSitterCppParser(filename)

  def test_legacy_metadata_contract(self):
    parser = self.parse('''
int test_func1(const unsigned int64 test_arg) {
  const struct teststruct *testvar = (struct teststruct *)globalvar->data;
  test_func2(test_arg, testvar); // comment
  0xe8();
  return 0;
}
void test_func_decl(int myarg);
void test_func_def(int myarg) {}
''')
    results = parser.get_chunks([(4, 5)])
    self.assertEmpty(results.parse_errors)
    self.assertLen(results.function_chunks, 1)
    chunk = results.function_chunks[0]
    self.assertEqual(chunk.name, 'test_func1')
    self.assertEqual(chunk.return_types, [['int']])
    self.assertEqual(chunk.parameters, ['test_arg'])
    self.assertEqual(chunk.used_data_types, [
        ['const', 'unsigned', 'int64'], ['const', 'struct', 'teststruct'],
        ['struct', 'teststruct']])
    self.assertEqual(chunk.local_variables, ['testvar'])
    self.assertEqual(chunk.called_functions, ['test_func2'])
    self.assertEqual(chunk.tokens[:3], ['int', 'test_func1', '('])
    self.assertEqual(chunk.tokens[-1], '}')
    self.assertEqual(results.line_chunk.tokens[5], ['0xe8', '(', ')', ';'])

  def test_inclusive_ranges_and_unfiltered_lines(self):
    parser = self.parse('int first() {\nreturn 0;\n}\n\nint second() {}\n')
    self.assertEqual(parser.get_function_ranges(), [(1, 3), (5, 5)])
    self.assertLen(parser.get_chunks().function_chunks, 2)
    self.assertLen(parser.get_chunks([]).function_chunks, 2)
    self.assertEqual([c.name for c in parser.get_chunks([(3, 3)]).function_chunks],
                     ['first'])
    self.assertEmpty(parser.get_chunks([(4, 4)]).function_chunks)
    self.assertLen(parser.get_chunks([(3, 5), (1, 1)]).function_chunks, 2)
    self.assertEqual(parser.get_chunks([(99, 99)]).line_chunk,
                     parser.get_chunks().line_chunk)

  def test_comments_strings_and_operators(self):
    results = self.parse('''/* comment */
int f() {
  const char *s = "a // b /* c */ \\"d";
  char c = '\\''; // ignored
  x >>= 2; y++; foo->bar();
}
''').get_chunks()
    self.assertNotIn(1, results.line_chunk.tokens)
    self.assertEqual(results.line_chunk.tokens[3],
                     ['const', 'char', '*', 's', '=', '"a // b /* c */ \\"d"', ';'])
    self.assertEqual(results.line_chunk.tokens[4],
                     ['char', 'c', '=', "'\\''", ';'])
    self.assertEqual(results.line_chunk.tokens[5],
                     ['x', '>>=', '2', ';', 'y', '++', ';', 'foo', '->',
                      'bar', '(', ')', ';'])
    self.assertEmpty(results.function_chunks[0].called_functions)

  def test_cpp_qualified_names_and_multiple_declarators(self):
    results = self.parse('''namespace ns {
int Thing::method(int x, const char *name) {
  int a = 1, *b = &a;
  direct(x); object.member(); ns::qualified();
  return x;
}
}''', '.cpp').get_chunks()
    chunk = results.function_chunks[0]
    self.assertEqual(chunk.name, 'Thing::method')
    self.assertEqual(chunk.parameters, ['x', 'name'])
    self.assertEqual(chunk.local_variables, ['a', 'b'])
    self.assertEqual(chunk.called_functions, ['direct'])
    self.assertEqual(chunk.used_data_types,
                     [['int'], ['const', 'char'], ['int']])

  def test_raw_string_preserves_legacy_prefix_boundary(self):
    results = self.parse('const char *x = R"tag(a\n// b)tag";', '.cpp').get_chunks()
    self.assertEqual(results.line_chunk.tokens,
                     {1: ['const', 'char', '*', 'x', '=',
                          'R', '"tag(a\n// b)tag"'], 2: [';']})

  def test_preprocessor_branches_remain_in_line_tokens(self):
    parser = self.parse('''#if ENABLED
int yes() { return 1; }
#else
int no() { return 0; }
#endif
''')
    results = parser.get_chunks()
    self.assertEqual([chunk.name for chunk in results.function_chunks],
                     ['yes', 'no'])
    self.assertEqual(results.line_chunk.tokens[1], ['#if ENABLED\n'])
    self.assertEqual(results.line_chunk.tokens[3], ['#else\n'])
    self.assertEqual(results.line_chunk.tokens[5], ['#endif\n'])

  def test_malformed_source_reports_diagnostics_and_preserves_tokens(self):
    results = self.parse('int broken() { return (1 + ); }\nint good() {}').get_chunks()
    self.assertNotEmpty(results.parse_errors)
    self.assertTrue(all(error.line >= 1 and error.column >= 0
                        for error in results.parse_errors))
    self.assertIn('good', [chunk.name for chunk in results.function_chunks])
    self.assertEqual(results.line_chunk.tokens[1],
                     ['int', 'broken', '(', ')', '{', 'return', '(', '1',
                      '+', ')', ';', '}'])

  def test_utf8_byte_offsets_and_multiline_comment(self):
    parser = self.parse('// café\n/* λ\n * comment */ int f() { return 1; }\n')
    results = parser.get_chunks()
    self.assertEqual(results.function_chunks[0].name, 'f')
    self.assertEqual(results.line_chunk.tokens,
                     {3: ['int', 'f', '(', ')', '{', 'return', '1', ';', '}']})
    self.assertEqual(parser.get_function_ranges(), [(3, 3)])

  def test_non_utf8_uses_existing_encoding_fallback(self):
    path = self.create_tempfile('latin1.c', content='// café\nint f() {}',
                                encoding='LATIN-1').full_path
    self.assertEqual(tree_sitter_parser.TreeSitterCppParser(path)
                     .get_chunks().function_chunks[0].name, 'f')
    with mock.patch.object(abstract_language_parser, '_ALTERNATIVE_ENCODINGS', []):
      with self.assertRaisesRegex(ValueError, 'Failed to decode'):
        tree_sitter_parser.TreeSitterCppParser(path)

  def test_arrays_function_pointers_and_returned_function_pointer(self):
    results = self.parse('''int (*factory(int (*callback)(int), int values[4]))(int) {
  int (*local)(int) = callback;
  int table[4], value = values[0];
  return local;
}''').get_chunks()
    self.assertEmpty(results.parse_errors)
    chunk = results.function_chunks[0]
    self.assertEqual(chunk.name, 'factory')
    self.assertEqual(chunk.parameters, ['callback', 'values'])
    self.assertEqual(chunk.local_variables, ['local', 'table', 'value'])
    self.assertEqual(chunk.used_data_types, [['int']] * 4)

  def test_nested_namespaces_and_methods_do_not_include_prototypes(self):
    results = self.parse('''namespace outer { namespace inner {
class Box {
 public:
  int get() const { return value; }
  void set(int next);
 private:
  int value;
};
void Box::set(int next) { value = next; }
}}''', '.cpp').get_chunks()
    self.assertEmpty(results.parse_errors)
    self.assertEqual([chunk.name for chunk in results.function_chunks],
                     ['get', 'Box::set'])
    self.assertEqual(results.function_chunks[1].parameters, ['next'])

  def test_missing_unnamed_punctuation_reports_diagnostic(self):
    results = self.parse('int f() { return 1 }').get_chunks()
    self.assertNotEmpty(results.parse_errors)
    self.assertTrue(any('missing' in error.message for error in results.parse_errors))

  def test_missing_file(self):
    with self.assertRaises(FileNotFoundError):
      tree_sitter_parser.TreeSitterCppParser('/nonexistent/vanir-source.c')


if __name__ == '__main__':
  absltest.main()
