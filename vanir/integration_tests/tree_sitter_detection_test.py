# Copyright 2026 Google LLC
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Proves legacy persisted signatures still detect code with either backend."""

import concurrent.futures
import multiprocessing
import os
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized
from vanir import parser
from vanir import reporter
from vanir import signature
from vanir.scanners import scanner_base


# Deliberately longer than ShortFunctionFilter's default threshold. The loop,
# branches and indexing exercise normalization beyond a trivial return.
_VULNERABLE_SOURCE = """static int read_packet(int *buffer, int count) {
  int accumulator = 0;
  int index = 0;
  for (index = 0; index < count; index++) {
    accumulator += buffer[index];
    if (buffer[index] < 0) {
      accumulator -= buffer[index];
    } else {
      accumulator += index;
    }
  }
  if (count > 16) {
    accumulator *= count;
  }
  return accumulator;
}
"""
_PATCHED_SOURCE = """static int read_packet(int *buffer, int count) {
  return 0;
}
"""
_TARGET = 'packet.c'
_PATCH_SOURCE = 'https://example.com/patches/read-packet-bounds'


def _scan_with_backend(source_dir, signatures, backend):
  # The feature flag is process-scoped. Each detector process must select it
  # before scanner_base starts its forkserver and parser workers.
  with mock.patch.dict(os.environ, VANIR_CPP_PARSER_BACKEND=backend):
    return scanner_base.scan(
        source_dir, signature.SignatureBundle(signatures)
    )


class TreeSitterDetectionTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.source_dir = self.create_tempdir()
    self.source_file = self.source_dir.create_file(
        _TARGET, content=_VULNERABLE_SOURCE
    )
    # Generate with the real legacy native parser, then persist and reload the
    # public OSV signature format before either detector gets to consume it.
    with mock.patch.dict(os.environ, VANIR_CPP_PARSER_BACKEND='fuzzyc'):
      legacy_parser = parser.Parser(self.source_file.full_path, _TARGET)
    functions = legacy_parser.get_function_chunks()
    self.assertLen(functions, 1)
    self.assertGreater(len(functions[0].normalized_code), 100)
    factory = signature.SignatureFactory('TREE-SITTER-SMOKE')
    generated = [
        factory.create_from_function_chunk(functions[0], _PATCH_SOURCE),
        factory.create_from_line_chunk(
            legacy_parser.get_line_chunk(), _PATCH_SOURCE,
            containment_threshold=1.0,
        ),
    ]
    self.signatures = [
        signature.Signature.from_osv_dict(item.to_osv_dict())
        for item in generated
    ]
    self.assertEqual(self.signatures, generated)

  def _scan(self, backend):
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1, mp_context=multiprocessing.get_context('spawn')
    ) as executor:
      return executor.submit(
          _scan_with_backend, self.source_dir.full_path,
          self.signatures, backend,
      ).result(timeout=60)

  @parameterized.parameters('fuzzyc', 'tree_sitter')
  def test_legacy_function_and_line_signatures_detect_vulnerable_source(
      self, backend
  ):
    findings, stats = self._scan(backend)
    self.assertEqual(stats.analyzed_files, 1)
    self.assertEqual(stats.skipped_files, 0)
    self.assertFalse(stats.errors)
    # Run the production false-positive filter as detector_runner does.
    findings = scanner_base.ShortFunctionFilter().filter(findings)
    self.assertCountEqual(findings, self.signatures)
    reports = reporter.generate_reports(findings)
    self.assertLen(reports, 2)
    self.assertCountEqual(
        [(report.unpatched_file, report.unpatched_function_name)
         for report in reports],
        [(_TARGET, 'read_packet'), (_TARGET, '')],
    )

  @parameterized.parameters('fuzzyc', 'tree_sitter')
  def test_legacy_signatures_reject_patched_source(self, backend):
    self.source_file.write_text(_PATCHED_SOURCE)
    findings, stats = self._scan(backend)
    self.assertEqual(stats.analyzed_files, 1)
    self.assertEqual(stats.skipped_files, 0)
    self.assertFalse(stats.errors)
    self.assertEmpty(findings)
    self.assertEmpty(reporter.generate_reports(findings))


if __name__ == '__main__':
  absltest.main()
