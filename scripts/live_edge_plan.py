"""Live-focused and arithmetic engine checks; expectations use canonical SQL and Fraction."""
from fractions import Fraction
import json
from pathlib import Path
import random

from rank_arithmetic import ArithmeticPlan, SOURCE_LIMIT, INPUTS

ROOT = Path(__file__).resolve().parents[1]


def arithmetic_case():
    rng = random.Random(1381)
    counts = [(1, 3, 0, 2, 2, 6, 0, 4), (1, 100, 0, 100, 2, 200, 0, 200),
              (0, 100, 10, 100, 0, 200, 20, 200),
              (1, 101, 0, 100, 1, 100, 0, 100)]
    for _ in range(100):
        pairs = []
        for _ in range(2):
            n = rng.randint(1, SOURCE_LIMIT - 1)
            m = rng.randint(1, SOURCE_LIMIT - n)
            pairs.extend((rng.randint(0, n), n, rng.randint(0, m), m))
        counts.append(tuple(pairs))
    columns = ', '.join(f'"{name}", INTEGER' for name in ('id', *[name[1:] for name in INPUTS]))
    data = ', '.join('{' + ', '.join(map(str, (i, *row))) + '}' for i, row in enumerate(counts))
    bindings = '\n'.join(f'VAR {name} = [{name[1:]}]' for name in INPUTS)
    query = f'''EVALUATE SELECTCOLUMNS(ADDCOLUMNS(DATATABLE({columns}, {{{data}}}),
        "comparison", ({bindings}\n{ArithmeticPlan().dax()})), "id", [id], "comparison", [comparison])
        ORDER BY [id]'''
    expected = []
    for i, (a, n, b, m, c, p, d, q) in enumerate(counts):
        left, right = Fraction(a, n) - Fraction(b, m), Fraction(c, p) - Fraction(d, q)
        expected.append(dict(id=i, comparison=(left > right) - (left < right)))
    return dict(id='exact_comparator', query=query, expectedRows=expected, keyColumns=['id'])


def focused_cases(plan):
    focal = plan['focal']
    key = focal['selection_key']
    row = focal['diagnostics'][-1]
    cases = []
    fields = {'rank': 'Priority Rank', 'qualifies': 'Window Qualifies', 'no': 'Window No Count',
              'known': 'Window Known Count', 'peer_no': 'Window Peer No Count',
              'peer_known': 'Window Peer Known Count', 'months': 'Elevated Months', 'gap_pp': 'Pooled Gap pp'}
    expressions = ', '.join(f'"{name}", [{measure}]' for name, measure in fields.items())
    expected = dict(rank=row['priority_rank'], qualifies=int(row['persistent']), no=row['window_no'],
                    known=row['window_known'], peer_no=row['window_peer_no'], peer_known=row['window_peer_known'],
                    months=row['elevated_months'], gap_pp=row['pooled_excess_pp'])
    cases.append(dict(id='focal_window', query=f'EVALUATE CALCULATETABLE(ROW({expressions}), \'Review Selection\'[Selection Key] = {key})', expected=expected))
    for minimum in (50, 100, 200):
        qualifies = all(month['complaints'] >= minimum and month['peer_complaints'] >= minimum
                        and month['known'] > 0 and month['peer_known'] > 0 for month in focal['diagnostics'])
        qualifies = qualifies and sum(month['elevated'] for month in focal['diagnostics']) >= 2
        cases.append(dict(id=f'focal_sensitivity_{minimum}',
            query=f'''EVALUATE CALCULATETABLE(ROW("result", [Sensitivity Result]),
                'Review Selection'[Selection Key] = {key}, 'Sensitivity Minimum'[Minimum] = {minimum})''',
            expected=dict(result='Qualifies' if qualifies else 'Does not qualify')))
    monthly_fields = {'complaints': 'Focused Monthly Complaint Count', 'no': 'Focused Monthly No Count',
                      'known': 'Focused Monthly Known Count', 'peer_no': 'Focused Monthly Peer No Count',
                      'peer_known': 'Focused Monthly Peer Known Count'}
    query = 'EVALUATE CALCULATETABLE(SELECTCOLUMNS(SUMMARIZECOLUMNS(\'Date\'[Month Start], ' + ', '.join(
        f'"{name}", [{measure}]' for name, measure in monthly_fields.items()) + "), " + ', '.join(
        ['"month", FORMAT(\'Date\'[Month Start], "yyyy-MM-dd")'] + [f'"{name}", [{name}]' for name in monthly_fields]) + f"), 'Review Selection'[Selection Key] = {key}) ORDER BY [month]"
    expected_rows = [dict(month=month['month'], complaints=month['complaints'], no=month['untimely'], known=month['known'],
                         peer_no=month['peer_untimely'], peer_known=month['peer_known']) for month in focal['diagnostics']]
    cases.append(dict(id='focal_monthly', query=query, expectedRows=expected_rows, keyColumns=['month']))
    baseline = next(case['expected'] for case in plan['cases'] if case['id'] == 'all_100')
    cases.append(dict(id='focal_keeps_population_counts', query=f'''EVALUATE CALCULATETABLE(
        ROW("eligible", [Eligible Window Count], "qualifying", [Qualifying Window Count],
            "segments", [Qualifying Segment Count], "stable", [Stable Window Count]),
        'Review Selection'[Selection Key] = {key})''', expected=dict(eligible=baseline['eligible_windows'],
            qualifying=baseline['qualifying_windows'], segments=baseline['qualifying_segments'], stable=baseline['stable_windows'])))
    cases.append(dict(id='partial_month_rejected', query=f'''EVALUATE CALCULATETABLE(
        ROW("qualifies", [Window Qualifies]), 'Review Selection'[Selection Key] = {key},
        'Date'[Date] >= DATE(2025,10,15))''', expected=dict(qualifies=0)))
    cases.append(dict(id='missing_selected_day_rejected', query=f'''EVALUATE CALCULATETABLE(
        ROW("qualifies", [Window Qualifies]), 'Review Selection'[Selection Key] = {key},
        FILTER(ALL('Date'), 'Date'[Date] <> DATE(2025,11,15)))''', expected=dict(qualifies=0)))
    cases.append(dict(id='ambiguous_minimum_unavailable', query='''EVALUATE CALCULATETABLE(
        ROW("eligible", [Eligible Window Count], "qualifying", [Qualifying Window Count]),
        TREATAS({50,200}, 'Review Minimum'[Minimum]))''', expected=dict(eligible=None, qualifying=None)))
    cases.append(dict(id='august_boundary_rejected', query='''EVALUATE CALCULATETABLE(
        ROW("eligible", [Eligible Window Count], "qualifying", [Qualifying Window Count]),
        TREATAS({DATE(2023,8,1),DATE(2023,9,1),DATE(2023,10,1)}, 'Review Window'[Window End]))''', expected=dict(eligible=0, qualifying=0)))
    cases.append(dict(id='no_focus_unavailable', query='''EVALUATE ROW("rate", [Focused Monthly Untimely Share],
        "result", [Sensitivity Result])''', expected=dict(rate=None, result='Unavailable')))
    for name, predicate in [
        ('global_partial_window_rejected', "'Date'[Date] >= DATE(2025,10,15)"),
        ('global_missing_day_rejected', "'Date'[Date] >= DATE(2025,10,1) && 'Date'[Date] <> DATE(2025,11,15)"),
    ]:
        cases.append(dict(id=name, query=f'''EVALUATE CALCULATETABLE(
            ROW("eligible", [Eligible Window Count], "qualifying", [Qualifying Window Count]),
            FILTER(ALL('Date'), {predicate}))''', expected=dict(eligible=0, qualifying=0)))
    return cases


def main():
    source = json.loads((ROOT / 'outputs/live_priority_plan.json').read_text())
    cases = [arithmetic_case(), *focused_cases(source)]
    (ROOT / 'outputs/live_edge_plan.json').write_text(json.dumps(dict(cases=cases), indent=2) + '\n')
    print(f'Generated {len(cases)} focused/arithmetic cases')


if __name__ == '__main__':
    main()
