"""Behavior checks for compact Import inputs; no model or DAX acceptance."""
from datetime import date
import importlib.util
from pathlib import Path
import statistics
import sys
import unittest

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
spec = importlib.util.spec_from_file_location('projection', PROJECT / 'scripts/export_import_projection.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ImportProjectionTests(unittest.TestCase):
    def setUp(self):
        self.c = duckdb.connect()
        self.addCleanup(self.c.close)
        self.c.execute('''CREATE TABLE projection_input(received_date DATE,Company VARCHAR,
            Product VARCHAR,Issue VARCHAR,State VARCHAR,routing_status VARCHAR,
            routing_days BIGINT,timely_response_status VARCHAR)''')

    def add(self, issue='issue', company='company', product='product', state='CA',
            lag=0, status='valid', flag='Yes', day='2023-01-01'):
        self.c.execute('INSERT INTO projection_input VALUES (?,?,?,?,?,?,?,?)',
                       [day, company, product, issue, state, status, lag, flag])

    def test_conservation_and_null_safe_join_with_literal_collisions(self):
        labels = [None, '', '[Empty]', '[SQL NULL]', 'missing:', 'value:', '  ']
        for index, label in enumerate(labels):
            for _ in range(index+1):
                self.add(company=label,product=label,issue=label,state=label,
                         flag=['Yes','No','Unknown'][index % 3])
        p.build(self.c)
        result = p.validate(self.c)
        self.assertEqual(result['source_counts'], result['projected_counts'])
        self.assertEqual(result['source_counts']['complaint_rows'], 28)
        self.assertEqual(result['reconstruction_difference_rows'], 0)
        for dim in p.DIMENSIONS:
            self.assertEqual(self.c.execute(f'SELECT count(DISTINCT {dim}_key) FROM {dim}').fetchone()[0],7)
            self.assertEqual(self.c.execute(f'SELECT raw_value FROM {dim}').fetchall(),[(x,) for x in labels[:2]+sorted(labels[2:])])
            # Display labels are presentation only; integer keys preserve colliding labels
            self.assertLess(self.c.execute(f'SELECT count(DISTINCT display_label) FROM {dim}').fetchone()[0],7)
        self.assertEqual(self.c.execute('SELECT count(DISTINCT segment_key) FROM review_selection').fetchone()[0],7)

    def test_typed_routing_invalid_lags_excluded_not_replaced(self):
        for status,lag in [('valid',0),('valid',4),('negative',None),('missing_or_invalid',None)]:
            self.add(status=status,lag=lag)
        p.build(self.c)
        self.assertEqual(p.weighted_median(self.c),2)
        self.assertEqual(self.c.execute("SELECT sum(complaint_rows) FROM complaint_cohorts WHERE routing_status<>'valid' AND routing_days IS NULL").fetchone()[0],2)
        schema = dict((r[0],r[1]) for r in self.c.execute('DESCRIBE complaint_cohorts').fetchall())
        self.assertEqual(schema['received_date'],'DATE')
        self.assertEqual(schema['complaint_rows'],'BIGINT')
        self.assertEqual(schema['routing_days'],'BIGINT')
        p.validate(self.c)

    def test_weighted_even_odd_empty_matches_complaint_grain(self):
        for lags in [[],[0],[0,0,2,10],[0,0,2,10,10],[1,1,1,1,7,9]]:
            with self.subTest(lags=lags):
                self.c.execute('DELETE FROM projection_input')
                for lag in lags:
                    self.add(lag=lag)
                self.add(status='negative',lag=None)
                p.build(self.c)
                expected = statistics.median(lags) if lags else None
                self.assertEqual(p.weighted_median(self.c),expected)
                self.assertEqual(p.weighted_median(self.c,"received_date=DATE '2025-01-01'"),None)
                p.validate(self.c)

    def test_calendar_and_independent_minima(self):
        p.build(self.c)
        self.assertEqual(self.c.execute('SELECT count(*),min(date),max(date) FROM "date"').fetchone(),
                         (1096,date(2023,1,1),date(2025,12,31)))
        self.assertEqual(self.c.execute('SELECT count(*) FROM "date" WHERE boundary_month').fetchone()[0],31)
        self.assertEqual(self.c.execute('SELECT count(*) FROM review_window').fetchone()[0],36)
        self.c.execute('DELETE FROM review_minimum WHERE minimum=50')
        self.assertEqual(self.c.execute('SELECT minimum FROM sensitivity_minimum ORDER BY minimum').fetchall(),[(50,),(100,),(200,)])
        self.assertEqual(p.validate(self.c)['source_counts']['complaint_rows'],0)

    def test_observed_month_candidates_lossless_under_population_filters(self):
        # Every eligible window has positive ending-month volume; filtering cannot create observations
        for month in [1,2,3,5]:
            for state in ['CA','NY']:
                for _ in range(3):
                    self.add(day=f'2023-{month:02d}-01',state=state)
        self.add(issue='sparse',day='2023-03-01')
        p.build(self.c)
        for minimum in [1,2,3]:
            for predicate in ['TRUE',"State='CA'","State='NY'","State='XX'"]:
                eligible = self.c.execute(f'''WITH monthly AS (
                    SELECT Issue,date_trunc('month',received_date)::DATE AS month_start,count(*) n
                    FROM projection_input WHERE {predicate} GROUP BY ALL)
                    SELECT a.Issue,a.month_start FROM monthly a JOIN monthly b
                    ON a.Issue=b.Issue AND b.month_start=a.month_start-INTERVAL 1 MONTH
                    JOIN monthly c ON a.Issue=c.Issue AND c.month_start=a.month_start-INTERVAL 2 MONTH
                    WHERE a.n>={minimum} AND b.n>={minimum} AND c.n>={minimum}''').fetchall()
                candidates = set(self.c.execute('SELECT issue_raw,window_end FROM review_selection').fetchall())
                self.assertTrue(set(eligible)<=candidates)
        self.assertEqual(self.c.execute('SELECT count(*) FROM review_selection').fetchone()[0],5)
        self.assertEqual(self.c.execute('SELECT count(DISTINCT segment_key) FROM review_selection').fetchone()[0],2)
        p.validate(self.c)


if __name__ == '__main__':
    unittest.main()
