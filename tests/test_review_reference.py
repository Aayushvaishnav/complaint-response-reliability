"""Independent exact-arithmetic behavioral oracle; synthetic complaints only."""
import calendar
from collections import Counter, defaultdict
import datetime as dt
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import random
import unittest

import duckdb

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reference_contract', ROOT / 'scripts/review_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def months(start, end):
    day = start.replace(day=1)
    while day < end:
        yield day
        day = (day + dt.timedelta(days=calendar.monthrange(day.year, day.month)[1]))


def ratio(n, d):
    return Fraction(n, d) if d else None


def reference(rows, start_date, end_date, minimum=100, companies=None, products=None, states=None, issues=None):
    start, end = map(dt.date.fromisoformat, (start_date, end_date))
    scoped = [r for r in rows if start <= r[1] < end and all(f is None or value in f for value, f in zip((r[2], r[3], r[5]), (companies, products, states)))]
    counts = defaultdict(Counter)
    segments = set()
    for _, day, company, product, issue, _, flag in scoped:
        key = (company, product, issue)
        segments.add(key)
        counts[key, day.replace(day=1)]['complaints'] += 1
        counts[key, day.replace(day=1)]['known'] += flag in ('Yes', 'No')
        counts[key, day.replace(day=1)]['untimely'] += flag == 'No'
    out = {}
    dates = list(months(start, end))
    complete = {m: start <= m and m + dt.timedelta(days=calendar.monthrange(m.year, m.month)[1]) <= end for m in dates}
    era = lambda m: 0 if m < dt.date(2023, 8, 1) else 1 if m >= dt.date(2023, 9, 1) else -1
    for key in segments:
        history = []
        for m in dates:
            own = counts[key, m]
            peer = Counter()
            for other in segments:
                if other[:2] == key[:2] and other != key:
                    peer.update(counts[other, m])
            total = own['complaints'] + peer['complaints']
            r = {field: own[field] for field in ('complaints', 'known', 'untimely')}
            r.update({'peer_' + field: peer[field] for field in ('complaints', 'known', 'untimely')})
            r['issue_share'] = ratio(own['complaints'], total)
            r['eligible_month'] = complete[m] and era(m) != -1 and own['complaints'] >= minimum and peer['complaints'] >= minimum and own['known'] > 0 and peer['known'] > 0
            elevated = own['known'] > 0 and peer['known'] > 0 and ratio(own['untimely'], own['known']) - ratio(peer['untimely'], peer['known']) >= Fraction(1, 100)
            r['_elevated'] = elevated
            if r['eligible_month']:
                r['elevated'] = elevated
            prior = history[-1] if history else None
            comparable = prior is not None and complete[m] and complete[dates[len(history)-1]] and era(m) != -1 and era(m) == era(dates[len(history)-1])
            r['prior_issue_share'] = prior['issue_share'] if comparable else None
            r['issue_share_change_pp'] = 100 * (r['issue_share'] - r['prior_issue_share']) if r['issue_share'] is not None and r['prior_issue_share'] is not None else None
            window = (history + [r])[-3:]
            window_dates = dates[max(0, len(history)-2):len(history)+1]
            r['window_eligible'] = len(window) == 3 and all(x['eligible_month'] for x in window) and len({era(d) for d in window_dates}) == 1
            r['elevated_months'] = sum(x['_elevated'] and x['eligible_month'] for x in window)
            r['persistent'] = r['window_eligible'] and r['elevated_months'] >= 2
            if r['persistent']:
                no = sum(x['untimely'] for x in window)
                excess = ratio(no, sum(x['known'] for x in window)) - ratio(sum(x['peer_untimely'] for x in window), sum(x['peer_known'] for x in window))
                r['pooled_excess_pp'] = 100 * excess
                r['_rank'] = (r['elevated_months'], excess, no, sum(x['complaints'] for x in window))
            history.append(r)
            out[key + (m,)] = r
    for m in dates:
        tuples = sorted({r['_rank'] for k, r in out.items() if k[-1] == m and r['persistent']}, reverse=True)
        for k, r in out.items():
            if k[-1] == m:
                r['priority_rank'] = tuples.index(r['_rank']) + 1 if r['persistent'] else None
    return {k: r for k, r in out.items() if issues is None or k[2] in issues}


def add(rows, month, company, product, issue, state, total, known, no):
    for i in range(total):
        flag = 'No' if i < no else 'Yes' if i < known else ('unknown', '', None, ' Yes')[i % 4]
        rows.append((str(len(rows)), month, company, product, issue, state, flag))


class ReferenceChecks(unittest.TestCase):
    def compare(self, rows, **context):
        expected = reference(rows, **context)
        with duckdb.connect() as db:
            db.execute('CREATE TABLE contract_input(complaint_id VARCHAR, received_date DATE, company VARCHAR, product VARCHAR, issue VARCHAR, state VARCHAR, timely_flag VARCHAR)')
            db.execute('INSERT INTO contract_input SELECT unnest($a), unnest($b), unnest($c), unnest($d), unnest($e), unnest($f), unnest($g)', dict(zip('abcdefg', map(list, zip(*rows)))))
            actual = {(r['company'], r['product'], r['issue'], r['month']): r for r in contract.evaluate(db, **context)}
        self.assertEqual(actual.keys(), expected.keys())
        for key, wanted in expected.items():
            for field, value in wanted.items():
                if field.startswith('_'):
                    continue
                with self.subTest(key=key, field=field):
                    if isinstance(value, Fraction):
                        self.assertAlmostEqual(actual[key][field], float(value), places=11)
                    else:
                        self.assertEqual(actual[key][field], value)
        return len(expected)

    def test_seeded_contexts(self):
        rng = random.Random(470123)
        rows = []
        for m in months(dt.date(2023, 5, 1), dt.date(2024, 4, 1)):
            for company, product in [('A', 'P'), ('B', 'Q'), (None, 'P')]:
                for state in ['CA', 'NY', None]:
                    for issue in [None, '', 'unknown', ' ', '  ', 'target']:
                        if rng.random() < .19 or (m.month == 12 and company == 'B'):
                            continue
                        total = rng.choice([49, 50, 99, 100, 199, 200, 230])
                        known = rng.choice([0, 1, total // 2, total])
                        no = rng.randrange(known + 1)
                        add(rows, m.replace(day=15), company, product, issue, state, total, known, no)
        contexts = [dict(start_date='2023-05-01', end_date='2024-04-01', companies=['A', None], products=['P'], states=['CA', None]), dict(start_date='2023-06-16', end_date='2024-03-17', companies=['B'], products=['Q'], states=['NY'], issues=[None, '', ' ', 'target'])]
        self.checked = sum(self.compare(rows, minimum=n, **ctx) for ctx in contexts for n in [50, 100, 200])

    def test_exact_tie_and_inclusive_gap(self):
        rows = []
        for month in [dt.date(2024, m, 15) for m in [1, 2, 3]]:
            for company, known, peer_known, peer_no in [('tie-a', 10, 165, 42), ('tie-b', 11, 10, 2)]:
                add(rows, month, company, 'P', 'target', 'CA', 200, known, 6)
                add(rows, month, company, 'P', 'peer', 'CA', 200, peer_known, peer_no)
            add(rows, month, 'inclusive', 'P', 'target', 'CA', 200, 100, 2)
            add(rows, month, 'inclusive', 'P', 'peer', 'CA', 200, 100, 1)
        self.compare(rows, start_date='2024-01-01', end_date='2024-04-01', minimum=200)


if __name__ == '__main__':
    unittest.main()
