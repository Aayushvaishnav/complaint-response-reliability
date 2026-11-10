"""Independent SQL window oracle versus sparse Python shift joins; no DAX engine."""
import random
from contextlib import closing
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from priority_population import optimized_population


def sparse(rows, minimum):
    monthly = {}
    for company, product, issue, month, fc, fk, fn, pc, pk, pn, complete in rows:
        if month == 8 or not complete or min(fc, pc) < 50 or min(fk, pk) <= 0:
            continue
        monthly[company, product, issue, month] = (fc, fk, fn, pc, pk, pn)
    shifts = [{(*key[:3], key[3] + offset): value for key, value in monthly.items()}
              for offset in range(3)]
    result = {}
    for key in shifts[0].keys() & shifts[1].keys() & shifts[2].keys():
        months = [shift[key] for shift in shifts]
        volume = min(min(row[0], row[3]) for row in months)
        elevated = sum(100 * (fn * pk - pn * fk) >= fk * pk
                       for fc, fk, fn, pc, pk, pn in months)
        if volume >= minimum:
            result[key] = (volume, elevated, *(sum(row[index] for row in months)
                                              for index in (2, 1, 5, 4, 0)),
                           int(volume >= 200 and elevated >= 2), int(elevated >= 2))
    return result


def canonical_sql(rows, minimum):
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('CREATE TABLE monthly(c,p,i,m,fc,fk,fn,pc,pk,pn,complete)')
        db.executemany('INSERT INTO monthly VALUES(?,?,?,?,?,?,?,?,?,?,?)', rows)
        # Canonical candidate windows require all three actual months, not adjacent rows;
        # rejected months remain present until the final eligibility predicate.
        values = db.execute('''
            WITH ends AS (SELECT DISTINCT c,p,i,m FROM monthly),
            windows AS (
                SELECT e.c,e.p,e.i,e.m, COUNT(*) AS months,
                    MIN(x.complete) AS complete,
                    SUM(x.m=8) AS august,
                    MIN(MIN(x.fc,x.pc)) AS volume,
                    MIN(MIN(x.fk,x.pk)) AS known,
                    SUM(x.fk>0 AND x.pk>0 AND
                        100*(x.fn*x.pk-x.pn*x.fk)>=x.fk*x.pk) AS elevated,
                    SUM(x.fn) AS no, SUM(x.fk) AS knownCount,
                    SUM(x.pn) AS peerNo, SUM(x.pk) AS peerKnown, SUM(x.fc) AS complaints
                FROM ends e JOIN monthly x ON x.c=e.c AND x.p=e.p AND x.i=e.i
                    AND x.m BETWEEN e.m-2 AND e.m
                GROUP BY e.c,e.p,e.i,e.m
            )
            SELECT c,p,i,m,volume,elevated,no,knownCount,peerNo,peerKnown,complaints,
                volume>=200 AND elevated>=2, elevated>=2
            FROM windows WHERE months=3 AND complete=1 AND august=0
                AND known>0 AND volume>=?
        ''', (minimum,)).fetchall()
    return {tuple(row[:4]): tuple(row[4:]) for row in values}


class PopulationOracleTests(unittest.TestCase):
    def test_boundary_fixture(self):
        rows = []
        cases = [(49, 50, 50, True), (50, 50, 50, True),
                 (99, 100, 100, True), (100, 100, 100, True),
                 (199, 200, 200, True), (200, 200, 200, True),
                 (200, 49, 200, True), (200, 200, 0, True),
                 (200, 200, 200, False)]
        for issue, (fc, pc, known, complete) in enumerate(cases):
            for month in range(1, 13):
                if issue == 2 and month == 2:
                    continue
                rows.append((1, 1, issue, month, fc, known, known // 2,
                             pc, known, 0, int(complete or month != 2)))
        for minimum in (50, 100, 200):
            with self.subTest(minimum=minimum):
                result = sparse(rows, minimum)
                self.assertEqual(result, canonical_sql(rows, minimum))
                self.assertFalse(any(key[3] in (8, 9, 10) for key in result))
                self.assertNotIn((1, 1, 0, 3), result)
                self.assertNotIn((1, 1, 8, 3), result)
        self.assertIn((1, 1, 1, 3), sparse(rows, 50))
        self.assertNotIn((1, 1, 1, 3), sparse(rows, 100))
        self.assertEqual(sparse(rows, 200)[1, 1, 5, 3][-2:], (1, 1))

    def test_random_sparse_populations_and_integer_gap_boundary(self):
        rng = random.Random(341)
        for trial in range(20):
            rows = []
            for company in (1, 2):
                for product in (1, 2):
                    for issue in range(4):
                        for month in range(1, 17):
                            if rng.random() < .12:
                                continue
                            fc, pc = rng.choices((0, 49, 50, 99, 100, 199, 200, 500), k=2)
                            fk, pk = rng.randrange(fc + 1), rng.randrange(pc + 1)
                            rows.append((company, product, issue, month, fc, fk,
                                         rng.randrange(fk + 1), pc, pk, rng.randrange(pk + 1),
                                         int(rng.random() >= .08)))
            for minimum in (50, 100, 200):
                with self.subTest(trial=trial, minimum=minimum):
                    self.assertEqual(sparse(rows, minimum), canonical_sql(rows, minimum))
        for no, elevated in ((0, 0), (1, 3), (2, 3)):
            rows = [(1, 1, 1, month, 100, 100, no, 100, 100, 0, 1)
                    for month in (1, 2, 3)]
            self.assertEqual(sparse(rows, 50)[1, 1, 1, 3][1], elevated)


class GeneratorTests(unittest.TestCase):
    def test_sparse_grouping_and_compatible_contract(self):
        dax = optimized_population()
        for var in ('selectedDates', 'ends', 'minimum', 'identities', 'statistics', 'evaluated', 'qualified'):
            self.assertIn(f'VAR _{var} =', dax)
        for field in ('key', 'segment', 'company', 'product', 'issue', 'end', 'complete',
                      'era', 'known', 'volume', 'elevated', 'no', 'knownCount', 'peerNo',
                      'peerKnown', 'complaints'):
            self.assertIn(f'"__{field}"', dax)
        self.assertEqual(dax.count('IGNORE(CALCULATE('), 3)
        self.assertEqual(dax.count('NATURALINNERJOIN('), 3)
        self.assertNotIn('COALESCE', dax)
        self.assertNotIn('GENERATE(', dax)
        self.assertNotIn('CALCULATE(', dax.split('VAR _withPeers =')[1])
        for offset in range(3):
            self.assertIn(f'EDATE(\'Date\'[Month Start], {offset})', dax)
        self.assertIn("EDATE('Review Selection'[Window End], 0)", dax)
        self.assertIn('"__selectedDays", COUNTROWS(\'Date\')', dax)
        self.assertIn("TREATAS(_completeMonths, 'Date'[Month Start])", dax)
        self.assertIn("ALLSELECTED('Date')", dax)
        self.assertIn("REMOVEFILTERS('Issue')", dax)
        self.assertIn('[__fc] >= 50 && [__pc] >= 50', dax)
        self.assertIn('[__fk] > 0 && [__pk] > 0', dax)
        self.assertIn('100 * ([__fn] * [__pk] - [__pn] * [__fk]) >= [__fk] * [__pk]', dax)
        self.assertEqual(dax, optimized_population())


if __name__ == '__main__':
    unittest.main()
