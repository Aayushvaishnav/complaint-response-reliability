"""Behavioral tests use synthetic complaints only."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('review_contract', ROOT / 'scripts/review_contract.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()
        self.db.execute('CREATE TABLE contract_input(complaint_id VARCHAR, received_date DATE, company VARCHAR, product VARCHAR, issue VARCHAR, state VARCHAR, timely_flag VARCHAR)')
        self.seq = 0

    def tearDown(self):
        self.db.close()

    def add(self, month, issue='target', total=100, no=2, unknown=0, company='A', product='P', state='CA'):
        rows = []
        for i in range(total):
            self.seq += 1
            flag = 'No' if i < no else ('unknown' if i < no+unknown else 'Yes')
            rows.append((str(self.seq), f'{month}-15', company, product, issue, state, flag))
        if rows:
            self.db.execute('''INSERT INTO contract_input SELECT
                unnest(?::VARCHAR[]), unnest(?::DATE[]), unnest(?::VARCHAR[]),
                unnest(?::VARCHAR[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[]),
                unnest(?::VARCHAR[])''', [list(column) for column in zip(*rows)])

    def run_rule(self, **kwargs):
        return module.evaluate(self.db, start_date=kwargs.pop('start_date', '2024-01-01'), end_date=kwargs.pop('end_date', '2024-04-01'), **kwargs)

    def target(self, **kwargs):
        return [r for r in self.run_rule(**kwargs) if r['issue']=='target']

    def fixture(self, total=100, elevated=3, peer_total=100, **kwargs):
        for i, month in enumerate(['2024-01','2024-02','2024-03']):
            self.add(month, total=total, no=1 if i < elevated else 0, **kwargs)
            self.add(month, issue='peer', total=peer_total, no=0, **kwargs)

    def test_inclusive_minima_and_sensitivities(self):
        for minimum in [50,100,200]:
            for n in [minimum-1,minimum,minimum+1]:
                with self.subTest(minimum=minimum,n=n):
                    self.db.execute('DELETE FROM contract_input')
                    self.fixture(total=n,peer_total=n)
                    r=self.target(minimum=minimum)[-1]
                    self.assertEqual(r['window_eligible'],n>=minimum)
        for n in [99,100,101]:
            self.db.execute('DELETE FROM contract_input')
            self.fixture(peer_total=n)
            self.assertEqual(self.target()[-1]['window_eligible'],n>=100)

    def test_exact_one_pp_and_persistence(self):
        for elevated in [1,2,3]:
            self.db.execute('DELETE FROM contract_input')
            self.fixture(elevated=elevated)
            r=self.target()[-1]
            self.assertEqual(r['elevated_months'],elevated)
            self.assertEqual(r['persistent'],elevated>=2)
            self.assertEqual(r['priority_rank'] is not None,elevated>=2)

    def test_unknown_counts_but_not_rate_denominator(self):
        for month in ['2024-01','2024-02','2024-03']:
            self.add(month,no=1,unknown=50)
            self.add(month,issue='',no=0)
        r=self.target()[-1]
        self.assertEqual(r['known'],50)
        self.assertEqual(r['complaints'],100)
        self.assertEqual(r['peer_complaints'],100)
        self.assertTrue(r['persistent'])
        self.assertAlmostEqual(r['pooled_excess_pp'],2)

    def test_elevation_nonzero_comparator_and_just_below(self):
        for segment_total, segment_no, peer_no, expected in [(100,2,1,True),(101,2,1,False),(100,1,0,True),(101,1,0,False)]:
            self.db.execute('DELETE FROM contract_input')
            for month in ['2024-01','2024-02','2024-03']:
                self.add(month,total=segment_total,no=segment_no)
                self.add(month,issue='peer',no=peer_no)
            self.assertEqual(self.target()[-1]['persistent'],expected)

    def test_missing_peer_month_ineligible(self):
        for month in ['2024-01','2024-02','2024-03']:
            self.add(month)
            if month!='2024-02':
                self.add(month,issue='peer')
        r=self.target()[-1]
        self.assertFalse(r['window_eligible'])
        self.assertIsNone(r['priority_rank'])

    def test_ranking_uses_full_tuple_in_order(self):
        scenarios=[('three',3,100,2),('excess',2,100,3),('no_count',2,200,4),('volume',2,300,6),('last',2,100,2)]
        for company,elevated,total,no in scenarios:
            for i,month in enumerate(['2024-01','2024-02','2024-03']):
                self.add(month,company=company,total=total,no=no if i<elevated else 0)
                self.add(month,issue='peer',company=company,no=0)
        ranked=[r for r in self.run_rule() if r['priority_rank'] is not None]
        self.assertEqual([r['company'] for r in ranked],['three','excess','volume','no_count','last'])
        self.assertEqual([r['priority_rank'] for r in ranked],[1,2,3,4,5])

    def test_empty_population(self):
        self.assertEqual(self.run_rule(),[])

    def test_rank_final_complaint_count_criterion(self):
        for company,unknown in [('more',10),('less',0)]:
            for month in ['2024-01','2024-02','2024-03']:
                self.add(month,company=company,total=100+unknown,unknown=unknown,no=2)
                self.add(month,issue='peer',company=company,no=0)
        ranked=[r for r in self.run_rule() if r['priority_rank'] is not None]
        self.assertEqual([r['company'] for r in ranked],['more','less'])
        self.assertEqual([r['priority_rank'] for r in ranked],[1,2])

    def test_all_unknown_segment_or_peers_ineligible(self):
        for issue in ['target','peer']:
            self.db.execute('DELETE FROM contract_input')
            for month in ['2024-01','2024-02','2024-03']:
                self.add(month,no=0,unknown=100 if issue=='target' else 0)
                self.add(month,issue='peer',no=0,unknown=100 if issue=='peer' else 0)
            result = self.target()[-1]
            self.assertFalse(result['window_eligible'])
            self.assertFalse(result['elevated'])

    def test_comparator_excludes_self_and_keeps_geography(self):
        self.fixture()
        for month in ['2024-01','2024-02','2024-03']:
            self.add(month,issue='outside',total=100,no=100,state='NY')
        r=self.target(states=['CA'],issues=['target'])[-1]
        self.assertEqual(r['peer_complaints'],100)
        self.assertEqual(r['peer_untimely'],0)
        self.assertTrue(r['persistent'])
        self.assertFalse(self.target(states=['CA','NY'])[-1]['persistent'])

    def test_no_borrowing_peers_from_company_or_product(self):
        for dimension in ['company','product']:
            self.db.execute('DELETE FROM contract_input')
            for month in ['2024-01','2024-02','2024-03']:
                self.add(month)
                self.add(month,issue='peer',**{dimension:'other'})
            r=[r for r in self.target() if r['company']=='A' and r['product']=='P'][-1]
            self.assertFalse(r['window_eligible'])
            self.assertEqual(r['peer_complaints'],0)

    def test_missing_month_is_zero_not_previous_available(self):
        for month in ['2024-01','2024-03']:
            self.add(month)
            self.add(month,issue='peer')
        rows=self.target()
        self.assertEqual(rows[1]['complaints'],0)
        self.assertIsNone(rows[2]['prior_issue_share'])
        self.assertFalse(rows[2]['window_eligible'])

    def test_absent_prior_issue_in_nonempty_cohort_is_zero(self):
        self.add('2024-01',issue='peer')
        self.add('2024-02')
        self.add('2024-02',issue='peer')
        rows=self.target()
        self.assertEqual(rows[0]['complaints'],0)
        self.assertEqual(rows[1]['prior_issue_share'],0)
        self.assertEqual(rows[1]['issue_share_change_pp'],50)

    def test_august_retained_but_no_longitudinal_boundary(self):
        for month in ['2023-06','2023-07','2023-08','2023-09','2023-10','2023-11']:
            self.add(month,no=1)
            self.add(month,issue='peer',no=0)
        rows=self.target(start_date='2023-06-01',end_date='2023-12-01')
        self.assertEqual(rows[2]['complaints'],100)
        self.assertEqual(rows[2]['issue_share'],.5)
        for i in [2,3,4]:
            self.assertFalse(rows[i]['window_eligible'])
        self.assertIsNone(rows[2]['issue_share_change_pp'])
        self.assertIsNone(rows[3]['issue_share_change_pp'])
        self.assertTrue(rows[5]['persistent'])

    def test_partial_selected_months_not_silently_trimmed(self):
        self.fixture()
        r=self.target(start_date='2024-01-10')[-1]
        self.assertEqual(r['window_complaints'],300)
        self.assertFalse(r['window_eligible'])
        r=self.target(end_date='2024-03-20')[-1]
        self.assertEqual(r['complaints'],100)
        self.assertFalse(r['window_eligible'])
        rows=self.target(start_date='2024-01-20',end_date='2024-03-10')
        self.assertEqual([r['complaints'] for r in rows],[0,100,0])
        self.assertFalse(rows[-1]['window_eligible'])
        self.assertTrue(self.target()[-1]['persistent'])

    def test_dense_rank_ties_labels_not_criteria(self):
        self.fixture(company='A')
        self.fixture(company='B')
        ranked=[r for r in self.run_rule() if r['priority_rank'] is not None]
        self.assertEqual(len(ranked),2)
        self.assertEqual([r['priority_rank'] for r in ranked],[1,1])
        self.assertEqual([r['company'] for r in ranked],['A','B'])

    def test_scope_filters_before_aggregation_two_scopes(self):
        self.fixture(company='A',state='CA')
        self.fixture(company='B',product='Q',state='NY')
        for filters, company, product in [({'companies':['A'],'products':['P'],'states':['CA']},'A','P'),({'companies':['B'],'products':['Q'],'states':['NY']},'B','Q')]:
            rows=self.run_rule(**filters,issues=['target'])
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[-1]['company'],company)
            self.assertEqual(rows[-1]['product'],product)
            self.assertEqual(rows[-1]['issue_share'],.5)
            self.assertTrue(rows[-1]['persistent'])
        self.assertEqual(self.run_rule(companies=[]),[])

    def test_missing_keys_preserve_raw_empty_and_null(self):
        for month in ['2024-01','2024-02','2024-03']:
            self.add(month,issue=None,company=None,product=None,state=None,no=1)
            self.add(month,issue='',company=None,product=None,state=None,no=0)
        rows=self.run_rule(companies=[None],products=[None],states=[None],issues=[None])
        self.assertEqual(len(rows),3)
        self.assertTrue(rows[-1]['issue_key']['is_null'])
        self.assertEqual(rows[-1]['peer_complaints'],100)
        self.assertTrue(rows[-1]['persistent'])

    def test_validation(self):
        for value in [True,99,100.0,'100']:
            with self.assertRaises(ValueError):
                self.run_rule(minimum=value)
        with self.assertRaises(ValueError):
            self.run_rule(start_date='2024-04-01')
        with self.assertRaises(ValueError):
            self.run_rule(companies='A')
        with self.assertRaises(ValueError):
            self.run_rule(companies=None)
        self.assertEqual(self.run_rule(companies=module.Selection.ALL), [])
        rule=module.load_rule()
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as temp:
            path=Path(temp)/'rule.json'
            for key,value in [('contract_status','pending'),('window_months',True),('allowed_minima',[50,100,200.0]),('extra',1)]:
                bad=dict(rule); bad[key]=value
                path.write_text(json.dumps(bad),encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.run_rule(config_path=path)


if __name__=='__main__':
    unittest.main()
