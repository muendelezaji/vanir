# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Opt-in Tree-sitter C/C++ parser using Vanir's existing chunk interface.

Tree-sitter supplies structural information; an independent lexical pass supplies
signature tokens. In particular, comments, preprocessor branches and recovery
nodes must not silently disappear from line signatures. This backend does not
claim that its recovery or metadata are identical to FuzzyC on all input.
"""

import bisect
import dataclasses
import os
import re
from typing import Optional, Sequence, Tuple

import tree_sitter
import tree_sitter_c
import tree_sitter_cpp

from vanir.language_parsers import abstract_language_parser
from vanir.language_parsers import common


# Keep tokenization independent of the grammar's node shapes (a string literal,
# for example, consists of several Tree-sitter leaves but is one lexer token).
# These boundaries deliberately preserve the historical signature lexer. In
# particular directives are whole-line tokens, defines are omitted, literal
# prefixes remain identifiers, and adjacent strings are one token.
_STRING = r'"(?:\\.|[^"\\])*"'
_TOKEN = re.compile(
    r'(?P<skip>[ \r\t\f\n]+|/\*.*?\*/|//[^\n]*(?:\n|$)'
    r'|#define[^\r\n]*\r?\n)'
    r'|(?P<directive>\#(?:ifdef|ifndef|if|else|elif|endif)[^\r\n]*\r?\n)'
    r'|(?P<string>' + _STRING
    + r'(?:[ \r\t\f\n]*(?:[a-zA-Z_~][a-zA-Z0-9_]*[ \r\t\f\n]*)*'
    + _STRING + r')*)'
    r"|(?P<char>'(?:\\.|[^'\\])')"
    r'|(?P<number>(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?[fFdD]?'
    r'|\d+[eE][+-]?\d+[fFdD]?|\d+[fFdD]'
    r'|(?:0[xX][\da-fA-F]+|0b[01]+|\d+)(?:[uU]?[lL]|[uU][lL]?)?)'
    r'|(?P<identifier>[a-zA-Z_~][a-zA-Z0-9_]*)'
    r'|(?P<operator><<=|>>=|->\*|\.\.\.|::|->|\+\+|--|&&|\|\||'
    r'<=|>=|==|!=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|[{}()\[\];,:.?+*/%&|^!<>=-])'
    r'|(?P<other>.)',
    re.DOTALL,
)



@dataclasses.dataclass(frozen=True)
class _Token:
  text: str
  start: int
  end: int
  line: int


def _walk(node, named_only=True):
  """Yield named syntax nodes in source order without Python recursion limits."""
  stack = [node]
  while stack:
    current = stack.pop()
    yield current
    children = current.named_children if named_only else current.children
    stack.extend(reversed(children))


def _declarator_name(node):
  """Find the identifier declared by nested pointer/array/function declarators."""
  if node is None:
    return None
  while node.child_by_field_name('declarator') is not None:
    node = node.child_by_field_name('declarator')
  if node.type in ('identifier', 'field_identifier', 'qualified_identifier',
                   'destructor_name', 'operator_name'):
    return node
  for child in node.named_children:
    if child.type not in ('parameter_list', 'argument_list'):
      result = _declarator_name(child)
      if result is not None:
        return result
  return None


class TreeSitterCppParser(abstract_language_parser.AbstractLanguageParser):
  """Parse C/C++ while retaining the public common.ParseResults contract."""

  def __init__(self, filename: str):
    try:
      with open(filename, encoding='UTF-8', newline='') as source_file:
        source = source_file.read()
    except UnicodeDecodeError:
      converted = self._convert_to_utf8(filename)
      try:
        with open(converted, encoding='UTF-8') as source_file:
          source = source_file.read()
      finally:
        os.remove(converted)
    self._source = source.encode('UTF-8')
    # Headers use C++'s superset grammar, matching the legacy extension policy.
    language_module = (tree_sitter_c if filename.endswith('.c')
                       else tree_sitter_cpp)
    parser = tree_sitter.Parser(tree_sitter.Language(language_module.language()))
    self._tree = parser.parse(self._source)
    self._tokens = []
    byte_offset = 0
    previous_end = 0
    line = 1
    for match in _TOKEN.finditer(source):
      gap = source[previous_end:match.start()]
      byte_offset += len(gap.encode('UTF-8'))
      line += gap.count('\n')
      text = match.group()
      end = byte_offset + len(text.encode('UTF-8'))
      if match.lastgroup not in ('skip', 'other'):
        self._tokens.append(_Token(text, byte_offset, end, line))
      byte_offset = end
      line += text.count('\n')
      previous_end = match.end()
    self._token_starts = [token.start for token in self._tokens]
    self._functions = [
        node for node in _walk(self._tree.root_node)
        if node.type == 'function_definition'
    ]

  @classmethod
  def get_supported_extensions(cls) -> Sequence[str]:
    return ['.c', '.h', '.cc', '.hh', '.cpp', '.hpp', '.cxx', '.hxx']

  def _text(self, node):
    return self._source[node.start_byte:node.end_byte].decode('UTF-8')

  def _node_tokens(self, node):
    return self._range_tokens(node.start_byte, node.end_byte)

  def _range_tokens(self, start, end):
    first = bisect.bisect_left(self._token_starts, start)
    last = bisect.bisect_left(self._token_starts, end)
    return [token.text for token in self._tokens[first:last]]

  def _type_tokens(self, declaration):
    """Collect qualifiers and the type, excluding storage and pointer syntax."""
    type_node = declaration.child_by_field_name('type')
    if type_node is None:
      return []
    start = type_node.start_byte
    for child in declaration.named_children:
      if child.type == 'type_qualifier' and child.start_byte < start:
        start = child.start_byte
    return self._range_tokens(start, type_node.end_byte)

  def get_function_ranges(self) -> Sequence[Tuple[int, int]]:
    """Return inclusive, one-based function ranges for compatibility audits."""
    return [(node.start_point.row + 1, node.end_point.row + 1)
            for node in self._functions]

  def _function_chunk(self, node):
    declarator = node.child_by_field_name('declarator')
    name = _declarator_name(declarator)
    parameters = []
    used_types = []
    # Follow the declared name, retaining its closest parameter list. A
    # function returning a function pointer has an additional outer list.
    parameter_list = None
    current = declarator
    while current is not None:
      current_parameters = current.child_by_field_name('parameters')
      if current_parameters is not None:
        parameter_list = current_parameters
      inner = current.child_by_field_name('declarator')
      if inner is None and current.type == 'parenthesized_declarator':
        inner = next(iter(current.named_children), None)
      current = inner
    if parameter_list is not None:
      for parameter in parameter_list.named_children:
        if parameter.type not in ('parameter_declaration',
                                  'optional_parameter_declaration'):
          continue
        parameter_name = _declarator_name(
            parameter.child_by_field_name('declarator'))
        if parameter_name is not None:
          parameters.append(self._text(parameter_name))
        type_tokens = self._type_tokens(parameter)
        if type_tokens:
          used_types.append(type_tokens)
    locals_ = []
    calls = []
    body = node.child_by_field_name('body')
    if body is not None:
      for child in _walk(body):
        if child.type in ('declaration', 'type_descriptor'):
          type_tokens = self._type_tokens(child)
          if type_tokens:
            used_types.append(type_tokens)
        if child.type == 'declaration':
          for declared in child.children_by_field_name('declarator'):
            local_name = _declarator_name(declared)
            if local_name is not None:
              locals_.append(self._text(local_name))
        elif child.type == 'call_expression':
          function = child.child_by_field_name('function')
          if function is not None and function.type == 'identifier':
            calls.append(self._text(function))
    return common.FunctionChunkBase(
        name=''.join(self._node_tokens(name)) if name is not None else '',
        return_types=[self._type_tokens(node)],
        parameters=parameters,
        used_data_types=used_types,
        local_variables=locals_,
        called_functions=calls,
        tokens=self._node_tokens(node),
    )

  def get_chunks(
      self,
      affected_line_ranges_for_functions: Optional[
          Sequence[Tuple[int, int]]
      ] = None,
  ) -> common.ParseResults:
    ranges = affected_line_ranges_for_functions or []
    functions = []
    for node, (start, end) in zip(self._functions, self.get_function_ranges()):
      if not ranges or any(first <= end and last >= start
                           for first, last in ranges):
        functions.append(self._function_chunk(node))
    lines = {}
    for token in self._tokens:
      lines.setdefault(token.line, []).append(token.text)
    errors = []
    for node in _walk(self._tree.root_node, named_only=False):
      if node.is_error or node.is_missing:
        errors.append(common.ParseError(
            line=node.start_point.row + 1,
            column=node.start_point.column,
            bad_token=self._text(node),
            message=('TreeSitter: missing ' if node.is_missing
                     else 'TreeSitter: unexpected syntax in ') + node.type,
        ))
    return common.ParseResults(functions, common.LineChunkBase(lines), errors)


# A short spelling is useful to callers selecting a backend dynamically.
TreeSitterParser = TreeSitterCppParser
