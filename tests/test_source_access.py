import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_source_access as ACCESS
from validate_source import COLUMNS


class SourceAccessTests(unittest.TestCase):
    def test_extracts_literal_header_without_executing_publisher_code(self):
        pairs = [(str(i), label) for i, label in enumerate(COLUMNS)]
        source = 'raise RuntimeError("must not execute")\nCSV_ORDERED_HEADERS = OrderedDict(' + repr(pairs) + ')'
        self.assertEqual(ACCESS.publisher_headers(source), COLUMNS)

    def test_executable_header_values_are_rejected(self):
        with self.assertRaises(ValueError):
            ACCESS.publisher_headers('CSV_ORDERED_HEADERS = OrderedDict(make_headers())')

    def test_missing_or_structurally_different_headers_are_rejected(self):
        for source in ['UNRELATED = 1', 'CSV_ORDERED_HEADERS = make_headers()',
                       'CSV_ORDERED_HEADERS = OrderedDict([("field", 1)])']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                ACCESS.publisher_headers(source)

    def test_http_403_is_explicit_evidence_instead_of_success(self):
        url = 'https://example.test/single-complaint'
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ACCESS, 'urlopen', side_effect=HTTPError(url, 403, 'Forbidden', {}, None)):
                result = ACCESS.fetch_reference('example', url, Path(directory))
            self.assertEqual(result['status'], 'http_error')
            self.assertEqual(result['http_status'], 403)
            self.assertFalse(list(Path(directory).iterdir()))

    def test_reviewed_publisher_excerpt_keeps_its_evidence_basis_explicit(self):
        evidence = {
            'evidence_type': 'reviewed_official_domain_search_excerpt',
            'reviewed_on': '2026-10-23', 'source_url': 'https://example.test/publisher.pdf',
            'quote': 'Publisher statement', 'full_document_review_state': 'not_read; HTTP 403',
        }
        result = ACCESS.validate_reviewed_excerpt(evidence, evidence['source_url'], 'Publisher statement')
        self.assertEqual(result['method'], 'manually_reviewed_official_search_excerpt')
        self.assertEqual(result['full_document_review_state'], 'not_read; HTTP 403')
        for key, replacement in [('source_url', 'https://wrong.test/paper.pdf'),
                                 ('quote', 'Unrelated statement'),
                                 ('evidence_type', 'unreviewed')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                ACCESS.validate_reviewed_excerpt({**evidence, key: replacement},
                                                evidence['source_url'], 'Publisher statement')


if __name__ == '__main__':
    unittest.main()
