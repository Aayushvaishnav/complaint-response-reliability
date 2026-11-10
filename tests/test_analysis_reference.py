"""Compact-reference checks against the frozen SQL, including corruptions."""
import datetime as dt
import sys
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from analysis_reference import validate_analysis
from review_contract import evaluate


class AnalysisReferenceTests(unittest.TestCase):
    def fixture(self, start='2023-01-01', end='2023-12-15'):
        counts, expanded = [], []
        for month in range(1, 13):
            if month == 5:
                continue
            for company in ('A', 'B'):
                for issue, no in ((None, 1), ('', 0), ('other', 0)):
                    day = dt.date(2023, month, 1)
                    if not dt.date.fromisoformat(start) <= day < dt.date.fromisoformat(end):
                        continue
                    counts.append(dict(company=company, product='P', issue=issue,
                                       month=day, complaints=100, known=100 if issue != 'other' else 50,
                                       untimely=no))
                    flags = ['No']*no + ['Yes']*((100 if issue != 'other' else 50)-no)
                    flags += ['Unknown']*(100-len(flags))
                    expanded.extend((company, 'P', issue, day, flag, 'CA') for flag in flags)
        con = duckdb.connect()
        con.execute('CREATE TABLE contract_input(company VARCHAR, product VARCHAR, issue VARCHAR, received_date DATE, timely_flag VARCHAR, state VARCHAR)')
        con.executemany('INSERT INTO contract_input VALUES (?, ?, ?, ?, ?, ?)', expanded)
        actual = evaluate(con, start_date=start, end_date=end, minimum=100)
        con.close()
        return counts, actual, dict(start_date=start, end_date=end, minimum=100)

    def test_full_diagnostics_and_rational_ties(self):
        counts, actual, options = self.fixture()
        result = validate_analysis(iter(counts), iter(actual), **options)
        self.assertEqual(result['rows'], 72)
        self.assertGreater(result['persistent_rows'], 0)
        self.assertTrue(any(r['persistent'] and r['priority_rank'] == 1 for r in actual))
        self.assertFalse(any(r['window_eligible'] for r in actual if r['month'].month in (8, 9, 10, 12)))

    def test_corruptions_rejected(self):
        counts, actual, options = self.fixture()
        for field in ('peer_known', 'eligible_month', 'issue_share', 'pooled_excess_pp', 'priority_rank'):
            rows = [dict(r) for r in actual]
            target = next(r for r in rows if r['persistent'])
            target[field] = not target[field] if isinstance(target[field], bool) else target[field]+1
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_analysis(counts, rows, **options)
        with self.assertRaises(ValueError):
            validate_analysis(counts, actual[:-1], **options)
        with self.assertRaises(ValueError):
            validate_analysis(counts, actual + actual[:1], **options)

    def test_partial_start(self):
        counts, actual, options = self.fixture(start='2023-01-02')
        self.assertFalse(any(r['persistent'] for r in actual if r['month'].month == 1))
        validate_analysis(counts, actual, **options)


if __name__ == '__main__':
    unittest.main()
