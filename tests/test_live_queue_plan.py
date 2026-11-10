"""Queue membership, exact ties and nullable selection identity behaviour."""
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from live_queue_plan import build_plan, queue_query


class QueuePlanTests(unittest.TestCase):
    def test_nullable_identity_unknown_denominators_ties_and_minima(self):
        with duckdb.connect() as con, tempfile.TemporaryDirectory() as folder:
            con.execute('''CREATE TABLE typed(complaint_id BIGINT, received_date DATE,
                Company VARCHAR, Product VARCHAR, Issue VARCHAR, State VARCHAR,
                timely_response_status VARCHAR)''')
            rows = []
            # Identical company populations produce rational rank ties; unknowns count for volume only
            for company, volume in [(None, 100), ('same', 100), ('large', 200)]:
                for month in (1, 2, 3):
                    for issue in ('focus', None):
                        for n in range(volume):
                            flag = 'Unknown' if n == volume-1 else 'No' if issue == 'focus' and n < 10 else 'Yes'
                            rows.append((len(rows), dt.date(2023, month, 15), company,
                                         'Debt collection', issue, 'CA', flag))
            con.executemany('INSERT INTO typed VALUES (?,?,?,?,?,?,?)', rows)
            source = Path(folder) / 'typed.parquet'
            selection = Path(folder) / 'selection.parquet'
            con.sql('SELECT * FROM typed').write_parquet(str(source))
            con.sql('''SELECT row_number() OVER (ORDER BY Company NULLS FIRST,Issue NULLS FIRST) selection_key,
                Company company_raw,Product product_raw,Issue issue_raw,DATE '2023-03-01' window_end
                FROM typed GROUP BY Company,Product,Issue''').write_parquet(str(selection))
            cases = {case['id']: case for case in build_plan(con, source, selection_source=selection)}
            for scope in ('all', 'received_2023', 'debt_collection', 'california'):
                low = cases[f'{scope}_50']['expectedRows']
                mid = cases[f'{scope}_100']['expectedRows']
                high = cases[f'{scope}_200']['expectedRows']
                self.assertEqual(low, mid)
                self.assertEqual(len(low), 3)
                self.assertEqual(len(high), 1)
                tied = [r for r in low if r['window_complaints'] == 300]
                self.assertEqual(len(tied), 2)
                for row in tied:
                    self.assertEqual(row['rank'], 1)
                    self.assertEqual(row['window_no'], 30)
                    self.assertEqual(row['window_known'], 297)
                    self.assertEqual(row['window_peer_no'], 0)
                    self.assertEqual(row['window_peer_known'], 297)
                    self.assertEqual(row['elevated_months'], 3)
                    self.assertAlmostEqual(row['pooled_gap_pp'], 100*30/297)
                    self.assertEqual(row['passing_minima'], '50/100')
                self.assertEqual(high[0]['passing_minima'], '50/100/200')
                self.assertEqual(high[0]['rank'], 1)
                self.assertEqual(cases[f'{scope}_100']['keyColumns'], ['selection_key'])
            con.execute("DELETE FROM typed WHERE month(received_date)=2")
            con.sql('SELECT * FROM typed').write_parquet(str(source))
            empty = build_plan(con, source, selection_source=selection)
            self.assertTrue(all(not c['expectedRows'] for c in empty))

    def test_query_prunes_before_detail_and_preserves_global_rank(self):
        query = queue_query(["'Review Minimum'[Minimum] = 100"])
        self.assertIn('ADDCOLUMNS(FILTER(SUMMARIZECOLUMNS(', query)
        self.assertLess(query.index('NOT ISBLANK([rank])'), query.index('[Window No Count]'))
        self.assertIn('[Passing Minima]', query)
        self.assertNotIn('TOPN', query)
        self.assertNotIn('TREATAS', query)
        self.assertNotIn('[Review Reason]', query)


if __name__ == '__main__':
    unittest.main()
