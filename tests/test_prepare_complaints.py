import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest
from collections import Counter
import duckdb

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', PROJECT / 'scripts/prepare_complaints.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.connection = duckdb.connect()
        self.connection.execute('CREATE TABLE scoped_input (' + ','.join(f'"{c}" VARCHAR' for c in p.COLUMNS) + ')')
        self.addCleanup(self.connection.close)

    def add(self, identity='001', received='2023-08-24', sent='2023-08-26', flag='Yes', issue='', state='CA'):
        values = [received, 'Debt collection', '', issue, '', '', 'Company', state, '001**', '', 'Web', sent, '', flag, identity]
        self.connection.execute('INSERT INTO scoped_input VALUES (' + ','.join('?' for _ in values) + ')', values)
        return values

    def build(self):
        self.connection.execute((PROJECT / 'sql/prepare_complaints.sql').read_text())

    def test_raw_preservation_and_bucket_collision(self):
        original = self.add(issue='missing:')
        self.add(identity='002', issue='  ')
        self.add(identity='003', issue='')
        self.build()
        projection = ','.join(f'"{c}"' for c in p.COLUMNS)
        self.assertEqual(list(self.connection.execute(f'SELECT {projection} FROM complaints WHERE complaint_id=\'001\'').fetchone()), original)
        self.assertEqual(self.connection.execute('SELECT issue_missing,issue_bucket FROM complaints ORDER BY complaint_id').fetchall(), [(False, 'value:missing:'), (False, 'value:  '), (True, 'missing:')])
        self.assertEqual(p.validate_table(self.connection), 3)

    def test_duplicate_and_missing_ids_fail(self):
        self.add()
        self.add()
        self.build()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            p.validate_table(self.connection)
        self.connection.execute("UPDATE complaints SET complaint_id='' WHERE complaint_id='001'")
        with self.assertRaises(ValueError):
            p.validate_table(self.connection)

    def test_routing_exceptions_and_flags(self):
        for i, (sent, flag) in enumerate([('', 'yes'), ('2023-02-30', 'NO'), ('2023-08-23', ' Yes'), ('2023-08-24', 'No'), ('2023-08-28', 'Yes')]):
            self.add(identity=str(i), sent=sent, flag=flag)
        self.build()
        self.assertEqual(self.connection.execute('SELECT routing_status,routing_days,timely_response_status FROM complaints ORDER BY complaint_id').fetchall(), [('missing_or_invalid', None, 'Unknown'), ('missing_or_invalid', None, 'Unknown'), ('negative', None, 'Unknown'), ('valid', 0, 'No'), ('valid', 4, 'Yes')])
        result = p.sql_metrics(self.connection, '')
        self.assertEqual((result['median_routing_days'], result['known'], result['unknown']), (2, 2, 3))
        self.assertEqual(p.validate_table(self.connection), 5)

    def test_boundary_partial_august_and_scope(self):
        for i, day in enumerate(['2023-07-31', '2023-08-01', '2023-08-23', '2023-08-24', '2023-08-31', '2023-09-01']):
            self.add(identity=str(i), received=day, sent=day)
        self.build()
        self.assertEqual(self.connection.execute('SELECT taxonomy_era,longitudinal_eligible FROM complaints ORDER BY complaint_id').fetchall(), [('pre_2023_08_24', True), ('pre_2023_08_24', False), ('pre_2023_08_24', False), ('post_2023_08_24', False), ('post_2023_08_24', False), ('post_2023_08_24', True)])
        self.assertEqual(p.validate_table(self.connection), 6)
        self.connection.execute("UPDATE complaints SET received_date=DATE '2026-01-01'")
        with self.assertRaises(ValueError):
            p.validate_table(self.connection)

    def test_invalid_received_blocks_validation(self):
        for received in ['', '2023-02-29', 'not a date', '20230824', '2023-W34-4', '2023-8-24', ' 2023-08-24']:
            with self.subTest(received=received):
                self.connection.execute('DELETE FROM scoped_input')
                self.assertIsNone(p.parse_date(received))
                self.add(received=received)
                self.build()
                self.assertEqual(self.connection.execute('SELECT routing_status FROM complaints').fetchone()[0], 'missing_or_invalid')
                with self.assertRaises(ValueError):
                    p.validate_table(self.connection)

    def test_empty_and_all_unknown(self):
        self.build()
        empty = p.sql_metrics(self.connection, '')
        self.assertEqual(empty['rows'], 0)
        self.assertIsNone(empty['timely_rate'])
        self.assertIsNone(empty['median_routing_days'])
        self.add(flag='unknown', sent='')
        self.build()
        result = p.sql_metrics(self.connection, '')
        self.assertIsNone(result['timely_rate'])
        self.assertEqual(result['unknown_rate'], 1)

    def test_reference_median(self):
        for counter, expected in [(Counter(), None), (Counter({0: 2, 4: 2}), 2), (Counter({1: 2, 8: 1}), 1), (Counter({3: 1000000, 4: 1000000}), 3.5)]:
            self.assertEqual(p.median(counter), expected)

    def test_full_csv_reference_filters(self):
        values = [self.add(), self.add(identity='002', received='2024-01-01', sent='2024-01-05', flag='No', state='NY')]
        self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scoped.csv'
            with path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(p.COLUMNS)
                writer.writerows(values)
            reference, groups = p.audit_csv(path)
        for key, where in p.FILTERS.items():
            self.assertEqual(reference[key], p.sql_metrics(self.connection, where))
        self.assertEqual(sum(groups['state'].values()), 2)

    def test_partition_guards_reject_hidden_extra_rows(self):
        self.add()
        self.build()
        for received in ['2026-01-01', 'not a date', '20230824', '2023-02-30']:
            with self.subTest(received=received):
                right = f'''SELECT * FROM scoped_input UNION ALL
                    SELECT '{received}', "Product", "Sub-product", "Issue", "Sub-issue",
                    "Company public response", "Company", "State", "ZIP code", "Tags",
                    "Submitted via", "Date sent to company", "Company response to consumer",
                    "Timely response?", 'extra' FROM scoped_input'''
                with self.assertRaisesRegex(ValueError, 'partition coverage'):
                    p.partitioned_difference(self.connection, 'SELECT * FROM scoped_input', right)
        with self.assertRaisesRegex(ValueError, 'counts differ'):
            p.partitioned_difference(self.connection, 'SELECT * FROM scoped_input', 'SELECT * FROM scoped_input UNION ALL SELECT * FROM scoped_input')
        self.assertEqual(p.partitioned_difference(self.connection, 'SELECT * FROM scoped_input', 'SELECT * FROM scoped_input'), 0)

    def test_except_all_detects_duplicate_multiplicity(self):
        self.add()
        self.build()
        self.assertEqual(p.difference(self.connection, 'SELECT * FROM scoped_input', 'SELECT * FROM scoped_input UNION ALL SELECT * FROM scoped_input'), 1)


if __name__ == '__main__':
    unittest.main()
