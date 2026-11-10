import contextlib
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/validate_source.py'
SPEC = importlib.util.spec_from_file_location('validate_source', SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def complaint(identifier, received='2023-01-01', sent='2023-01-02', timely='Yes'):
    values = {name: '' for name in VALIDATOR.COLUMNS}
    values.update({'Complaint ID': str(identifier), 'Date received': received,
                   'Date sent to company': sent, 'Timely response?': timely,
                   'Product': 'Example product', 'Issue': 'Quoted, multiline\nissue',
                   'Company': 'Example company', 'Company response to consumer': 'In progress',
                   'ZIP code': '00123'})
    return values


class SourceValidationTests(unittest.TestCase):
    def execute(self, records):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / 'source.csv'
        project = root / 'project'
        with source.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=VALIDATOR.COLUMNS)
            writer.writeheader()
            writer.writerows(records)
        return source, project

    def report(self, project):
        return json.loads((project / 'outputs/source_validation.json').read_text())

    def run_quietly(self, source, project):
        with contextlib.redirect_stdout(io.StringIO()):
            VALIDATOR.run(source, project)

    def test_date_boundaries_unknowns_negative_lags_and_raw_values(self):
        records = [complaint(1, '2022-12-31'), complaint(2),
                   complaint(3, '2025-12-31', '2025-12-30', ''),
                   complaint(4, '2026-01-01'),
                   complaint(5, '2024-02-29', '', 'Unexpected')]
        source, project = self.execute(records)
        self.run_quietly(source, project)
        report = self.report(project)
        self.assertTrue(all(report['checks'].values()))
        self.assertEqual(report['full']['rows'], 5)
        self.assertEqual(report['scoped']['rows'], 3)
        self.assertEqual(report['scoped']['unknown_timely_flags'], 2)
        self.assertEqual(report['scoped']['negative_routing_lags'], 1)
        self.assertEqual(report['scoped']['invalid_or_missing_sent_dates'], 1)
        self.assertEqual(source.read_bytes(), (project / 'data/raw/complaints.csv').read_bytes())
        with (project / 'data/processed/complaints_2023_2025.csv').open(newline='') as handle:
            retained = list(csv.DictReader(handle))
        self.assertCountEqual(retained, [records[1], records[2], records[4]])

    def test_duplicate_ids_block_export_instead_of_silent_deduplication(self):
        source, project = self.execute([complaint(1), complaint(1)])
        with self.assertRaises(ValueError):
            self.run_quietly(source, project)
        self.assertEqual(self.report(project)['full']['duplicate_extra_rows'], 1)
        self.assertFalse((project / 'data/processed/complaints_2023_2025.csv').exists())

    def test_invalid_received_dates_block_export(self):
        source, project = self.execute([complaint(1, '2023-02-29')])
        with self.assertRaises(ValueError):
            self.run_quietly(source, project)
        self.assertEqual(self.report(project)['full']['invalid_or_missing_received_dates'], 1)

    def test_non_numeric_or_missing_ids_block_export(self):
        for identifier in ['', 'abc']:
            with self.subTest(identifier=identifier):
                source, project = self.execute([complaint(identifier)])
                with self.assertRaises(ValueError):
                    self.run_quietly(source, project)
                self.assertFalse(self.report(project)['checks']['unique_nonblank_numeric_source_ids'])

    def test_empty_date_cohort_blocks_export(self):
        source, project = self.execute([complaint(1, '2022-01-01')])
        with self.assertRaises(ValueError):
            self.run_quietly(source, project)
        self.assertFalse(self.report(project)['checks']['nonempty_date_cohort'])

    def test_different_existing_snapshot_is_preserved(self):
        source, project = self.execute([complaint(1)])
        destination = project / 'data/raw/complaints.csv'
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b'existing snapshot')
        with self.assertRaises(ValueError):
            self.run_quietly(source, project)
        self.assertEqual(destination.read_bytes(), b'existing snapshot')

    def test_schema_drift_is_rejected(self):
        source, project = self.execute([complaint(1)])
        source.write_text('unexpected\nvalue\n')
        with self.assertRaises(ValueError):
            self.run_quietly(source, project)

    def test_bom_and_special_text_survive_export(self):
        record = complaint(1, timely=' Yes ')
        record['Sub-issue'] = 'NULL'
        record['Issue'] = '  Quoted "issue"\r\nwith whitespace  '
        source, project = self.execute([record])
        source.write_bytes(b'\xef\xbb\xbf' + source.read_bytes())
        self.run_quietly(source, project)
        with (project / 'data/processed/complaints_2023_2025.csv').open(newline='') as handle:
            retained = list(csv.DictReader(handle))
        self.assertEqual(retained, [record])
        self.assertEqual(self.report(project)['scoped']['unknown_timely_flags'], 1)

    def test_malformed_records_fail_strict_import(self):
        for fields in [['too', 'few'], ['extra'] * 16]:
            with self.subTest(fields=len(fields)):
                source, project = self.execute([complaint(1)])
                with source.open('a', newline='') as handle:
                    csv.writer(handle).writerow(fields)
                with self.assertRaises(VALIDATOR.duckdb.Error):
                    self.run_quietly(source, project)
                self.assertFalse((project / 'data/processed/complaints_2023_2025.csv').exists())

    def test_rerun_reconciles_the_same_source(self):
        source, project = self.execute([complaint(1)])
        self.run_quietly(source, project)
        first = self.report(project)
        self.run_quietly(source, project)
        second = self.report(project)
        self.assertEqual(first['source']['sha256'], second['source']['sha256'])
        self.assertEqual(first['export']['sha256'], second['export']['sha256'])
        self.assertTrue(all(second['checks'].values()))


if __name__ == '__main__':
    unittest.main()
