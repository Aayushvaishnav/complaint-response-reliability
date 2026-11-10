"""Behavioral integration checks for the Gate C population runner."""
import copy
from datetime import date
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
from population_analysis import (check_identity, evaluate_scope, fingerprint,
                                 query_rows, reconcile_overview)


class PopulationAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        shutil.copytree(PROJECT / 'sql', self.project / 'sql')
        (self.project / 'outputs').mkdir()
        self.con = duckdb.connect()
        self.addCleanup(self.con.close)
        self.con.execute('''CREATE TABLE complaints(complaint_id BIGINT, received_date DATE,
            received_month DATE, Company VARCHAR, Product VARCHAR, Issue VARCHAR,
            State VARCHAR, "Timely response?" VARCHAR,
            "Company response to consumer" VARCHAR, response_missing BOOLEAN,
            routing_days INTEGER, routing_status VARCHAR)''')
        # Equal-rate portfolios give genuine rank ties; volume cutoffs split membership.
        for company, volume, state in [('A', 60, 'CA'), ('B', 120, 'NY'),
                                       ('C', 240, 'CA'), ('D', 240, 'CA')]:
            for month in range(1, 4):
                for issue in ('target', 'peer'):
                    self.con.execute('''INSERT INTO complaints SELECT
                        row_number() OVER (), ?, ?, ?, 'Debt collection', ?, ?,
                        CASE WHEN i >= ? THEN NULL WHEN ?='target' AND i < ? THEN 'No' ELSE 'Yes' END,
                        'Closed', false, CASE WHEN i%2=0 THEN 2 ELSE 4 END, 'valid'
                        FROM range(?) t(i)''', [date(2023, month, 1), date(2023, month, 1),
                        company, issue, state, volume, issue, volume // 10,
                        volume + month])
        self.select('TRUE')

    def select(self, where):
        self.con.execute('CREATE OR REPLACE VIEW selected_complaints AS SELECT * FROM complaints WHERE ' + where)
        self.con.execute('''CREATE OR REPLACE VIEW contract_input AS SELECT complaint_id,
            received_date, Company company, Product product, Issue issue, State state,
            "Timely response?" timely_flag FROM selected_complaints''')

    def run_scope(self, scope='all', minima=(50, 100, 200)):
        expected = self.con.execute('''SELECT count(*), count(*) FILTER(WHERE "Timely response?"='Yes'),
            count(*) FILTER(WHERE "Timely response?"='No'), count("Timely response?"),
            count(*)-count("Timely response?"), count(routing_days) FROM selected_complaints''').fetchone()
        audit = dict(zip(('rows', 'yes', 'no', 'known', 'unknown', 'valid_lags'), expected))
        (self.project / 'outputs/typed_preparation_validation.json').write_text(
            json.dumps({'rows': expected[0], 'independent': {scope: audit}}))
        output = {key: [] for key in ('overview', 'queue', 'summary', 'history')}
        result = evaluate_scope(self.con, scope, '2024-01-01', minima, self.project, output)
        return result, output

    def test_three_actual_month_peer_totals_and_sensitivity(self):
        result, output = self.run_scope()
        queues = output['queue']
        self.assertEqual([run['persistent_windows'] for run in result['runs']], [4, 3, 2])
        self.assertTrue(result['checks']['nested_volume_sensitivity'])
        for row in queues:
            volume = {'A': 60, 'B': 120, 'C': 240, 'D': 240}[row['company']]
            self.assertEqual(row['month'], date(2023, 3, 1))
            self.assertEqual(row['window_peer_complaints'], 3 * volume + 6)
            self.assertEqual(row['window_peer_unknown'], 6)
            self.assertEqual(row['window_unknown'], 6)
            self.assertEqual(row['passing_minima'], {'A': '50', 'B': '50/100', 'C': '50/100/200', 'D': '50/100/200'}[row['company']])
            self.assertEqual(row['stable_across_volume_minima'], row['company'] in ('C', 'D'))
        low = {row['company']: row for row in queues if row['minimum'] == 50}
        self.assertEqual(low['C']['priority_rank'], low['D']['priority_rank'])
        self.assertLess(low['C']['priority_rank'], low['B']['priority_rank'])
        self.assertLess(low['B']['priority_rank'], low['A']['priority_rank'])
        self.assertEqual(result['runs'][0]['exact_rank_replay']['distinct_tuples'], 3)

    def test_filtered_context_recomputes_portfolios(self):
        self.select("State='CA' AND Company='C'")
        result, output = self.run_scope('CA', (100,))
        self.assertEqual(result['checks']['complaints'], 1452)
        self.assertEqual({r['company'] for r in output['queue']}, {'C'})
        self.assertEqual(len(output['queue']), 1)
        self.assertEqual(output['queue'][0]['priority_rank'], 1)
        self.assertEqual(output['queue'][0]['passing_minima'], '100')
        self.assertFalse(output['queue'][0]['stable_across_volume_minima'])
        self.assertEqual({r['issue'] for r in output['history']}, {'target'})

    def test_nonempty_population_with_empty_queue_is_valid(self):
        self.con.execute('UPDATE complaints SET "Timely response?"=\'Yes\'')
        result, output = self.run_scope()
        self.assertEqual(output['queue'], [])
        self.assertEqual(output['history'], [])
        self.assertTrue(output['overview'])
        self.assertEqual(result['checks']['stable_windows'], 0)
        self.assertTrue(all(run['exact_rank_replay']['distinct_tuples'] == 0 for run in result['runs']))

    def test_reconciliation_rejects_corruption(self):
        rows = [query_rows(self.con, (self.project / 'sql' / name).read_text()) for name in
                ('monthly_overview.sql', 'segment_month_counts.sql', 'routing_distribution.sql', 'response_mix.sql')]
        overview = rows[0]
        expected = {source: sum(r[field] for r in overview) for field, source in
                    [('complaints', 'rows'), ('timely', 'yes'), ('untimely', 'no'),
                     ('known', 'known'), ('unknown', 'unknown'), ('valid_routing', 'valid_lags')]}
        reconcile_overview(*rows, expected)
        for index, field in [(0, 'unknown'), (1, 'complaints'), (2, 'complaints'),
                             (2, 'routing_days'), (3, 'untimely')]:
            corrupted = copy.deepcopy(rows)
            corrupted[index][0][field] += 1
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                reconcile_overview(*corrupted, expected)

    def test_changed_accepted_artifact_is_rejected(self):
        paths = ['data/processed/complaints_typed.parquet', 'config/review_rule.json',
                 'sql/longitudinal_contract.sql', 'scripts/review_contract.py',
                 'outputs/typed_preparation_validation.json', 'config/source.json']
        for path in paths:
            target = self.project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes((PROJECT / path).read_bytes() if path == 'config/review_rule.json' else b'fixture')
        accepted = {'status': 'passed', 'checks': {'fixture': True},
                    'artifact_sha256': {p: fingerprint(self.project / p) for p in paths}}
        (self.project / 'outputs/gate_b_acceptance.json').write_text(json.dumps(accepted))
        self.assertEqual(check_identity(self.project), accepted['artifact_sha256'])
        for path in paths:
            target = self.project / path
            original = target.read_bytes()
            target.write_bytes(original + b'\n')
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Gate B artifact changed'):
                check_identity(self.project)
            target.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
