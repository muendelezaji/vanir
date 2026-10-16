# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file or at https://developers.google.com/open-source/licenses/bsd

"""Parser-neutral, signature-aware differential measurements.

There is deliberately no comparison of parser-specific error messages: they are
retained in reports while compatibility compares the structured error locations.
Function ranges are measured through the public affected-lines API, rather than
assuming unique function names or relying on either native parser's ABI.
"""

import dataclasses
from typing import Any, Callable

from vanir import hasher
from vanir import normalizer
from vanir.language_parsers import abstract_language_parser


def snapshot(
    parser_factory: Callable[
        [], abstract_language_parser.AbstractLanguageParser
    ],
    source_line_count: int,
) -> dict[str, Any]:
  """Captures externally meaningful parser behavior, including signature output.

  Query every individual source line to detect off-by-one ranges, same-name
  functions, interior blank lines, and selection outside the source. Each call
  obtains fresh results: the native parser's chunk objects are single-use.
  """
  results = parser_factory().get_chunks()
  normalized_lines = normalizer.normalize_line_chunk(results.line_chunk)
  ranges = [None, [(0, 0)], [(source_line_count + 1, source_line_count + 1)]]
  ranges.extend([[(line, line)] for line in range(1, source_line_count + 1)])
  if source_line_count:
    ranges.extend([
        [(1, 1), (source_line_count, source_line_count)],
        [(source_line_count, source_line_count), (1, 1)],
        [(1, source_line_count)],
    ])
  selections = []
  line_hashes = []
  for affected in ranges:
    chunks = parser_factory().get_chunks(affected).function_chunks
    selections.append({
        'ranges': affected,
        # Include the token sequence to distinguish repeated function names.
        'functions': [[chunk.name, list(chunk.tokens)] for chunk in chunks],
    })
    hashes, used = hasher.hash_line_chunk(normalized_lines, affected or [])
    line_hashes.append({
        'ranges': affected, 'hashes': hashes, 'used_lines': used,
    })
  return {
      'functions': [
          dataclasses.asdict(chunk) for chunk in results.function_chunks
      ],
      'line_tokens': dict(results.line_chunk.tokens),
      'function_selection': selections,
      'normalized_functions': [
          normalizer.normalize_function_chunk(chunk)
          for chunk in results.function_chunks
      ],
      'function_hashes': [
          hasher.hash_function_chunk(normalizer.normalize_function_chunk(chunk))
          for chunk in results.function_chunks
      ],
      'normalized_lines': dict(normalized_lines),
      'line_hashes': line_hashes,
      'error_locations': [
          [error.line, error.column, error.bad_token]
          for error in results.parse_errors
      ],
      'diagnostics': [
          dataclasses.asdict(error) for error in results.parse_errors
      ],
  }


def differences(
    reference: dict[str, Any], candidate: dict[str, Any]
) -> list[str]:
  """Returns changed contract dimensions; diagnostics are parser-specific."""
  return sorted(
      key for key in reference
      if key != 'diagnostics' and reference[key] != candidate[key]
  )
