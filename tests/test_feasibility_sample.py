import csv
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import build_feasibility_sample as SAMPLE
from validate_source import COLUMNS, PROJECT


def complaint(identifier, received='2023-01-01', sent='2023-01-02', timely='Yes', product='Debt collection'):
    record = dict.fromkeys(COLUMNS, '')
    record.update({'Complaint ID': identifier, 'Date received': received,
                   'Date sent to company': sent, 'Timely response?': timely,
                   'Product': product, 'Company': 'Example company',
                   'Issue': 'Quoted, "multiline"\nissue', 'State': 'CA', 'ZIP code': '00123'})
    return record


class FeasibilitySampleTests(unittest.TestCase):
    def staging(self, records):
        connection = duckdb.connect()
        self.addCleanup(connection.close)
        declaration = ', '.join(f'"{name}" VARCHAR' for name in COLUMNS)
        connection.execute('CREATE TABLE raw_complaints (' + declaration + ')')
        if records:
            placeholders = ', '.join(['?'] * len(COLUMNS))
            connection.executemany('INSERT INTO raw_complaints VALUES (' + placeholders + ')',
                                   [[record[column] for column in COLUMNS] for record in records])
        connection.execute((PROJECT / 'sql/validate_source.sql').read_text())
        return connection

    def output(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_lowest_text_ids_and_month_product_flag_coverage(self):
        records = [complaint('30'), complaint('20'), complaint('10'), complaint('2'),
                   complaint('31', timely='No'), complaint('40', product='Other product'),
                   complaint('50', received='2024-01-01', sent='2024-01-01')]
        connection = self.staging(records)
        destination = self.output()
        result = SAMPLE.build_sample(connection, destination, 2)
        with (destination / 'gate_a_sample.csv').open(newline='') as handle:
            selected = list(csv.DictReader(handle))
        self.assertEqual({row['Complaint ID'] for row in selected}, {'10', '2', '31', '40', '50'})
        self.assertCountEqual(selected, [r for r in records if r['Complaint ID'] in {'10', '2', '31', '40', '50'}])
        self.assertEqual(result['strata'], 4)
        self.assertTrue(result['source_stratum_coverage_verified'])
        self.assertEqual(result['parquet_value_differences'], 0)
        self.assertTrue(all(item['passed'] for item in result['metric_filter_checks']))

    def test_selection_is_independent_of_input_order(self):
        records = [complaint('3'), complaint('1'), complaint('2')]
        first = SAMPLE.build_sample(self.staging(records), self.output(), 2)
        second = SAMPLE.build_sample(self.staging(list(reversed(records))), self.output(), 2)
        self.assertEqual(first['sample_csv_sha256'], second['sample_csv_sha256'])

    def test_received_date_boundaries(self):
        records = [complaint('1', received='2022-12-31'), complaint('2'),
                   complaint('3', received='2025-12-31'), complaint('4', received='2026-01-01')]
        result = SAMPLE.build_sample(self.staging(records), self.output(), 3)
        self.assertEqual(result['rows'], 2)
        self.assertEqual(result['received_months'], ['2023-01', '2025-12'])

    def test_unknown_flags_and_invalid_lags_are_preserved_and_reconciled(self):
        records = [complaint('1', timely=''), complaint('2', timely='Unexpected', sent='2022-12-31'),
                   complaint('3', timely='No', sent=''), complaint('4', timely='Yes')]
        result = SAMPLE.build_sample(self.staging(records), self.output(), 3)
        metrics = result['metric_filter_checks'][0]['sql']
        self.assertEqual(metrics['complaints'], 4)
        self.assertEqual(metrics['unknown'], 2)
        self.assertEqual(metrics['known'], 2)
        self.assertEqual(metrics['timely_rate'], 0.5)
        self.assertEqual(metrics['valid_lags'], 2)

    def test_zero_known_response_denominator_is_blank(self):
        records = [complaint('1', timely='unknown', sent='')]
        result = SAMPLE.build_sample(self.staging(records), self.output(), 3)
        metrics = result['metric_filter_checks'][0]['sql']
        self.assertIsNone(metrics['timely_rate'])
        self.assertIsNone(metrics['untimely_rate'])
        self.assertIsNone(metrics['median_routing_days'])
        self.assertEqual(metrics['unknown_rate'], 1)

    def test_empty_cohort_has_zero_counts_and_blank_rates(self):
        metrics = SAMPLE.reconcile_metrics(self.staging([]), [])[0]['sql']
        self.assertEqual(metrics['complaints'], 0)
        self.assertIsNone(metrics['timely_rate'])
        self.assertIsNone(metrics['unknown_rate'])

    def test_even_and_odd_routing_medians(self):
        for sent_dates, expected in [(['2023-01-01', '2023-01-03'], 1),
                                     (['2023-01-01', '2023-01-03', '2023-01-06'], 2)]:
            with self.subTest(sent_dates=sent_dates):
                records = [complaint(str(i), sent=sent) for i, sent in enumerate(sent_dates)]
                result = SAMPLE.reconcile_metrics(self.staging(records), records)[0]['sql']
                self.assertEqual(result['median_routing_days'], expected)

    def test_invalid_sent_date_retains_complaint_and_timeliness(self):
        records = [complaint('1', sent='not-a-date', timely='No')]
        metrics = SAMPLE.reconcile_metrics(self.staging(records), records)[0]['sql']
        self.assertEqual(metrics['complaints'], 1)
        self.assertEqual(metrics['untimely'], 1)
        self.assertEqual(metrics['valid_lags'], 0)
        self.assertIsNone(metrics['median_routing_days'])

    def test_response_category_does_not_replace_timely_flag(self):
        record = complaint('1', timely='Yes')
        record['Company response to consumer'] = 'Untimely response'
        metrics = SAMPLE.reconcile_metrics(self.staging([record]), [record])[0]['sql']
        self.assertEqual(metrics['timely'], 1)
        self.assertEqual(metrics['untimely'], 0)

    def test_duplicate_source_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            SAMPLE.build_sample(self.staging([complaint('1'), complaint('1')]), self.output(), 3)

    def test_nonpositive_or_noninteger_sample_limits_are_rejected(self):
        for value in [0, -1, True, 1.5, '3']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                SAMPLE.build_sample(self.staging([complaint('1')]), self.output(), value)

    def test_out_of_scope_only_source_has_no_feasibility_sample(self):
        with self.assertRaises(ValueError):
            SAMPLE.build_sample(self.staging([complaint('1', received='2026-01-01')]), self.output(), 3)

    def test_sample_rebuild_keeps_identity(self):
        connection = self.staging([complaint('1')])
        directory = self.output()
        first = SAMPLE.build_sample(connection, directory, 3)
        second = SAMPLE.build_sample(connection, directory, 3)
        self.assertEqual(first['sample_csv_sha256'], second['sample_csv_sha256'])


if __name__ == '__main__':
    unittest.main()
