"""Behaviour checks on original typed schema; no model projection expectations."""
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from live_priority_plan import build_plan, canonical_sql, parameters, summary


class PriorityPlanTests(unittest.TestCase):
    def setUp(self):
        self.connection = duckdb.connect()
        self.connection.execute('''CREATE TABLE typed(complaint_id BIGINT,received_date DATE,
            Company VARCHAR,Product VARCHAR,Issue VARCHAR,State VARCHAR,timely_response_status VARCHAR)''')
        rows = []
        for month in (1, 2, 3):
            for issue, no in [('focus', 2), ('peer', 0)]:
                for n in range(200):
                    rows.append((len(rows), dt.date(2023, month, 15), 'test', 'Debt collection', issue, 'CA', 'No' if n < no else 'Yes'))
        self.connection.executemany('INSERT INTO typed VALUES (?,?,?,?,?,?,?)', rows)

    def tearDown(self):
        self.connection.close()

    def test_all_minima_scopes_and_stability(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'typed.parquet'
            self.connection.execute('COPY typed TO ? (FORMAT PARQUET)', [str(source)])
            cases = build_plan(self.connection, source)
        self.assertEqual(len(cases), 12)
        for case in cases:
            self.assertEqual(case['expected'], dict(eligible_windows=2, qualifying_windows=1,
                                                   qualifying_segments=1, stable_windows=1))
            self.assertTrue(case['query'].startswith('EVALUATE CALCULATETABLE(ROW('))
            self.assertIn(f"'Review Minimum'[Minimum] = {case['minimum']}", case['query'])

    def test_no_preceding_observed_substitution_and_partial_dates(self):
        self.connection.execute('''CREATE VIEW contract_input AS SELECT complaint_id,received_date,
            Company company,Product product,Issue issue,State state,timely_response_status timely_flag FROM typed''')
        sql = canonical_sql()
        partial = summary(self.connection, sql, parameters(start='2023-01-16', end='2023-04-01'))
        self.assertEqual(partial['eligible_windows'], 0)
        self.connection.execute("DELETE FROM typed WHERE month(received_date)=2")
        missing = summary(self.connection, sql, parameters(end='2023-04-01'))
        self.assertEqual(missing['eligible_windows'], 0)
        self.assertEqual(missing['qualifying_windows'], 0)

    def test_explicit_multistate_scope_and_empty_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'typed.parquet'
            self.connection.execute('COPY typed TO ? (FORMAT PARQUET)', [str(source)])
            cases = build_plan(self.connection, source, scopes={
                'two_states': ('2026-01-01', None, ['CA', 'NY'], []),
                'no_states': ('2026-01-01', None, [], []),
            })
        self.assertEqual(len(cases), 6)
        for case in cases:
            self.assertEqual(case['expected']['eligible_windows'], 2 if case['scope'] == 'two_states' else 0)
            self.assertEqual(case['expected']['qualifying_windows'], 1 if case['scope'] == 'two_states' else 0)


if __name__ == '__main__':
    unittest.main()
