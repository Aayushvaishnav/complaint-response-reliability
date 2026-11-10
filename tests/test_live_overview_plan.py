import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from live_overview_plan import build_plan, overview_query, SCOPES


class OverviewPlanTests(unittest.TestCase):
    def test_source_relation_and_empty_undefined_values(self):
        with tempfile.TemporaryDirectory(prefix="f1'overview-") as folder, duckdb.connect() as con:
            source = Path(folder) / 'source.parquet'
            con.execute('CREATE TABLE fixture(received_date DATE, product VARCHAR, state VARCHAR, timely_response_status VARCHAR, routing_status VARCHAR, routing_days INTEGER)')
            con.executemany('INSERT INTO fixture VALUES (?, ?, ?, ?, ?, ?)', [
                (dt.date(2023, 1, 5), 'Debt collection', 'CA', 'Yes', 'valid', 1),
                (dt.date(2025, 10, 20), 'Debt collection', 'CA', 'No', 'valid', 3),
                (dt.date(2025, 12, 15), 'Other', 'NY', 'Unknown', 'negative', -1),
                (dt.date(2025, 12, 16), 'Other', 'NY', None, 'missing', None),
            ])
            con.sql('SELECT * FROM fixture').write_parquet(str(source))
            cases = {case['id']: case for case in build_plan(con, source)}
            custom = build_plan(con, source, scopes={
                'two_states': ("state IN ('CA', 'NY')", ["FILTER(ALL('Geography'), 'Geography'[State] IN {\"CA\", \"NY\"})"]),
            })
            self.assertEqual(len(custom), 1)
            self.assertEqual(custom[0]['expected'], cases['all']['expected'])
            self.assertIn('"NY"', custom[0]['query'])
        self.assertEqual(cases['all']['expected']['complaints'], 4)
        self.assertEqual(cases['all']['expected']['known'], 2)
        self.assertEqual(cases['all']['expected']['unknown'], 2)
        self.assertEqual(cases['all']['expected']['median_routing_days'], 2)
        self.assertEqual(cases['all']['expected']['timely_rate'], .5)
        self.assertEqual(cases['partial_months']['expected']['complaints'], 2)
        self.assertEqual(cases['received_2023']['expected']['complaints'], 1)
        self.assertEqual(cases['california']['expected']['complaints'], 2)
        self.assertEqual(cases['empty']['expected']['complaints'], 0)
        self.assertIsNone(cases['empty']['expected']['timely_rate'])
        self.assertIsNone(cases['empty']['expected']['median_routing_days'])

    def test_dax_filters_apply_to_entire_row(self):
        query = overview_query(["'Date'[Year] = 2023"])
        self.assertTrue(query.startswith('EVALUATE CALCULATETABLE(ROW('))
        self.assertTrue(query.endswith(", 'Date'[Year] = 2023)"))
        self.assertIn('[Complaint Count]', query)
        self.assertNotIn('CALCULATETABLE', overview_query([]))

    def test_grouped_labels_are_filtered_with_their_identity_table(self):
        self.assertIn("FILTER(ALL('Product')", SCOPES['debt_collection'][1][0])
        self.assertIn("FILTER(ALL('Geography')", SCOPES['california'][1][0])


if __name__ == '__main__':
    unittest.main()
